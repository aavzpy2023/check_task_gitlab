# backend/main.py
import enum
import os

import re
import sys
import tempfile
import time
import urllib.parse
import calendar
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from threading import Thread
from typing import Dict, List, Optional
from collections import defaultdict
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime, timezone

import pandas as pd
import pypandoc
import requests
import urllib3
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Header
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    String,
    create_engine,
    func,
    Integer,
    Boolean,
    UniqueConstraint,
    case,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, declarative_base, sessionmaker

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- Configuración ---
GITLAB_URL = os.getenv("GITLAB_URL")
PRIVATE_TOKEN = os.getenv("GITLAB_TOKEN")
# SSS: CORRECCION TYPO (POSTGRES_PASSWORD)
DATABASE_URL = f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST', 'postgres_chatbot')}:5432/{os.getenv('POSTGRES_DB')}"
SYNC_INTERVAL_SECONDS = int(os.getenv("SYNC_INTERVAL_SECONDS", 3600))
PROJECTS_CSV_PATH = "./projects.csv"
SYNC_IN_PROGRESS = False
AUDIT_SYNC_IN_PROGRESS = False
_raw_pass = os.getenv("CONFIG_TAB_PASS", "")
CONFIG_TAB_PASS = _raw_pass.strip() if _raw_pass else None

# --- SQLAlchemy Setup ---
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- Modelos ---
class TaskStatus(str, enum.Enum):
    IN_PROGRESS = "En Ejecucion"
    QA_REVIEW = "PARA REVISIÓN"
    FUNCTIONAL_REVIEW = "Revision Funcional"

LABEL_MAPPING = {
    TaskStatus.IN_PROGRESS: ['A EJECUCIÓN', 'A ejecución', 'EN EJECUCIÓN', 'Ejecución', 'En Ejecución'],
    TaskStatus.QA_REVIEW: ['PARA REVISION', 'PARA REVISIÓN', 'Para Revisión'],
    TaskStatus.FUNCTIONAL_REVIEW: ['REVISION FUNCIONAL', 'REVISIÓN FUNCIONAL', 'Revisión Funcional'],
}

class AuditEventType(str, enum.Enum):
    ISSUE_RAISED = "ISSUE_RAISED"
    ISSUE_REVIEWED = "ISSUE_REVIEWED"
    UC_CREATED = "UC_CREATED"
    UC_UPDATED = "UC_UPDATED"
    MANUAL_CREATED = "MANUAL_CREATED"
    MANUAL_UPDATED = "MANUAL_UPDATED"
    PUSH_EVENT = "PUSH_EVENT"

class SystemMetadata(Base):
    __tablename__ = "system_metadata"
    key = Column(String(50), primary_key=True, default="singleton")
    last_sync_time = Column(DateTime(timezone=True), server_default=func.now())

class MonitoredProject(Base):
    __tablename__ = "monitored_projects"
    project_id = Column(BigInteger, primary_key=True, index=True)
    project_name = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, server_default=text('true'), nullable=False)

class GitLabTaskDB(Base):
    __tablename__ = "gitlab_tasks"
    task_id = Column(BigInteger, primary_key=True)
    project_id = Column(BigInteger, ForeignKey("monitored_projects.project_id"), nullable=False, index=True)
    task_status_label = Column(String(50), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True))
    raw_data = Column(JSONB)
    cycle_metrics = Column(JSONB, default={}) 


class AuditEventDB(Base):
    __tablename__ = "audit_events"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    project_id = Column(BigInteger, ForeignKey("monitored_projects.project_id"), nullable=False, index=True)
    username = Column(String(255), nullable=False, index=True)
    event_date = Column(DateTime(timezone=True), nullable=False)
    event_month = Column(Integer, nullable=False)
    event_year = Column(Integer, nullable=False)
    event_type = Column(String(50), nullable=False)
    is_on_time = Column(Boolean, nullable=True)
    reference_id = Column(String(255), nullable=False)

    __table_args__ = (
        UniqueConstraint('project_id', 'event_type', 'reference_id', 'username', name='uix_audit_event_idemp'),
    )

class CycleMetrics(BaseModel):
    execution_days: int = 0
    review_days: int = 0
    functional_days: int = 0

class TimeStats(BaseModel):
    human_time_estimate: Optional[str] = None
    human_total_time_spent: Optional[str] = None

class Task(BaseModel):
    project_id: int
    title: str
    description: Optional[str] = None
    author: str
    url: str
    assignee: Optional[str] = None
    milestone: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    labels: List[str] = []
    time_stats: TimeStats = Field(default_factory=TimeStats)
    cycle_metrics: CycleMetrics = Field(default_factory=CycleMetrics) 

class TaskWithProject(Task):
    project_name: str

class ProjectSummary(BaseModel):
    id: int
    name: str
    review_task_count: int


class AuthRequest(BaseModel):
    password: str

class ConfigProject(BaseModel):
    id: int
    name: str
    is_active: bool

class TesterAuditMetrics(BaseModel):
    username: str
    issues_raised: int = 0
    issues_reviewed: int = 0
    issues_reviewed_on_time: int = 0
    uc_created: int = 0
    uc_updated: int = 0
    manual_created: int = 0
    manual_updated: int = 0
    total_pushes: int = 0


# --- Lógica de Sincronización ---
def gitlab_api_request(method: str, endpoint: str, **kwargs) -> Optional[requests.Response]:
    if not PRIVATE_TOKEN: return None
    headers = {"PRIVATE-TOKEN": PRIVATE_TOKEN}
    api_url = f"{GITLAB_URL}/api/v4/{endpoint}"
    try:
        response = requests.request(method, api_url, headers=headers, verify=False, timeout=15, **kwargs)
        return response
    except requests.exceptions.RequestException:
        return None

def calculate_cycle_metrics_logic(issue_data, project_id, issue_iid):
    """
    Consulta el historial de eventos para calcular días en cada etapa.
    """
    # 1. Obtener eventos de etiquetas (Requiere llamada extra a API)
    # Nota: Usamos el endpoint de resource_label_events
    events_resp = gitlab_api_request("get", f"projects/{project_id}/issues/{issue_iid}/resource_label_events")
    events = events_resp.json() if events_resp else []

    # 2. Definir hitos temporales
    created_at = datetime.fromisoformat(issue_data['created_at'].replace('Z', '+00:00'))
    now = datetime.now(timezone.utc)
    
    t_start_review = None
    t_start_functional = None

    # 3. Buscar cuándo ocurrieron los cambios de estado (tomamos el PRIMER evento)
    # Buscamos variaciones de etiquetas definidas en LABEL_MAPPING
    review_labels = set(l for sublist in LABEL_MAPPING[TaskStatus.QA_REVIEW] for l in sublist)
    func_labels = set(l for sublist in LABEL_MAPPING[TaskStatus.FUNCTIONAL_REVIEW] for l in sublist)

    # Ordenar eventos cronológicamente
    events.sort(key=lambda x: x['created_at'])

    for e in events:
        if e['action'] == 'add' and e.get('label'):
            label_name = e['label']['name']
            event_time = datetime.fromisoformat(e['created_at'].replace('Z', '+00:00'))
            
            if label_name in review_labels and t_start_review is None:
                t_start_review = event_time
            
            if label_name in func_labels and t_start_functional is None:
                t_start_functional = event_time

    # 4. Calcular deltas en DÍAS
    metrics = {"execution_days": 0, "review_days": 0, "functional_days": 0}

    # Calculo Ejecución (Creación -> Revisión)
    end_execution = t_start_review if t_start_review else now
    metrics["execution_days"] = (end_execution - created_at).days

    # Calculo Revisión (Revisión -> Funcional)
    if t_start_review:
        end_review = t_start_functional if t_start_functional else now
        # Si t_start_functional es anterior a t_start_review (error de flujo), asumimos 0
        if end_review > t_start_review:
            metrics["review_days"] = (end_review - t_start_review).days

    # Calculo Funcional (Funcional -> Ahora)
    if t_start_functional:
        metrics["functional_days"] = (now - t_start_functional).days

    return metrics


def fetch_and_store_wiki_events(project_id: int, month: int, year: int, db: Session):
    _, last_day = calendar.monthrange(year, month)
    start_date = datetime(year, month, 1, tzinfo=timezone.utc)
    end_date = datetime(year, month, last_day, 23, 59, 59, tzinfo=timezone.utc)

    db.query(AuditEventDB).filter(
        AuditEventDB.project_id == project_id,
        AuditEventDB.event_month == month,
        AuditEventDB.event_year == year,
        AuditEventDB.event_type.in_([
            AuditEventType.UC_CREATED.value, AuditEventType.UC_UPDATED.value,
            AuditEventType.MANUAL_CREATED.value, AuditEventType.MANUAL_UPDATED.value,
            AuditEventType.PUSH_EVENT.value
        ])
    ).delete(synchronize_session=False)
    db.commit()

    page = 1
    while True:
        # Petición a Eventos: Solo del mes seleccionado y sin filtrar target_type
        resp = gitlab_api_request("get", f"projects/{project_id}/events", params={
            "after": start_date.strftime("%Y-%m-%d"),
            "before": (end_date + timedelta(days=1)).strftime("%Y-%m-%d"),
            "per_page": 100,
            "page": page
        })

        if not resp or not resp.json():
            break

        events = resp.json()
        if not events:
            break

        for e in events:
            # 0. Defensa absoluta contra eventos corruptos
            if not isinstance(e, dict):
                continue

            # 1. Filtro flexible de tipo (Wiki o Push)
            target_type = str(e.get("target_type", "")).lower()
            action = str(e.get("action_name", "")).lower()

            is_push = "pushed" in action
            is_wiki = "wiki" in target_type or "wiki" in action

            if not is_push and not is_wiki:
                continue

            # 2. Extracción de Fecha
            created_at_str = e.get("created_at")
            if not created_at_str:
                continue
            event_date = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))

            # 3. Extracción robusta del autor
            author_data = e.get("author") or {}
            author = e.get("author_username") or author_data.get("username")
            if not author:
                continue

                # --- NUEVO: MANEJO DE PUSH EVENTS (Terminal) ---
            if is_push:
                push_data = e.get("push_data") or {}
                ref = push_data.get("ref", "rama_desconocida")
                commit_count = push_data.get("commit_count", 1)

                # Extraemos el mensaje del commit para aplicarle heurística
                commit_title_raw = push_data.get("commit_title") or "Sin mensaje"
                commit_title = commit_title_raw.lower()

                # 1. Filtro Anti-Desarrollador (Código):
                # Si la rama o el commit mencionan correcciones, bloqueamos la clasificación de documentación.
                is_code_smell = re.search(r'\b(incidencia|bug|fix|hotfix|error|exception|refactor|merge)\b',
                                          commit_title) or any(
                    x in ref.lower() for x in ['hotfix', 'bugfix', 'fix/', 'feature/'])

                # 2. Heurística estricta usando RegEx:
                is_manual_match = re.search(r'\b(manual|guia|guía)\b', commit_title)

                # Exige que 'cu' esté pegado a un número (ej. cu07, cu 08, 12cu, 02.29.cu07.2.5)
                # para evitar atrapar extensiones de dominio como '.cu' en gitlab.azcuba.cu
                is_cu_match = re.search(
                    r'\b(caso de uso|casos de uso|casos de usos|use case)\b|\b\d+[\.\-_]?cu\b|\bcu[\.\-_\s]?\d+',
                    commit_title)

                # 3. Clasificación dinámica:
                is_manual = bool(is_manual_match) and not is_code_smell
                is_cu = bool(is_cu_match) and not is_code_smell

                # --- NUEVA REGLA: ¿Es Creación o Actualización? ---
                is_creation = bool(re.search(r'\b(nuevo|cread|add|agregar|añadir)\b', commit_title))
                # Clasificación dinámica basada en el mensaje
                if is_manual:
                    evt_type = AuditEventType.MANUAL_CREATED.value if is_creation else AuditEventType.MANUAL_UPDATED.value
                    # Extraemos el slug exacto para agrupar múltiples ediciones de consola en una sola
                    ref_id = is_manual_match.group(0).lower().replace(' ', '-')
                elif is_cu:
                    evt_type = AuditEventType.UC_CREATED.value if is_creation else AuditEventType.UC_UPDATED.value
                    ref_id = is_cu_match.group(0).lower().replace(' ', '-')
                else:
                    evt_type = AuditEventType.PUSH_EVENT.value
                    ref_id = f"[Push: General] {commit_title_raw} ({commit_count} commits -> {ref})"

                stmt = pg_insert(AuditEventDB).values(
                    project_id=project_id, username=author, event_date=event_date,
                    event_month=month, event_year=year, event_type=evt_type,
                    reference_id=ref_id
                ).on_conflict_do_update(
                    index_elements=['project_id', 'event_type', 'reference_id', 'username'],
                    set_={'event_date': event_date}
                )
                db.execute(stmt)
                continue

            # 4. Fusión Semántica y DEFENSA CONTRA NULL (CONTINÚA WIKI)
            title = (e.get("target_title") or "").lower()

            # EL FIX: Si wiki_page es null en el JSON, Python lo vuelve None.
            # `or {}` fuerza a que vuelva a ser un diccionario vacío seguro.
            wiki_page_data = e.get("wiki_page") or {}
            slug = (wiki_page_data.get("slug") or "").lower()

            combined_text = f"{title} {slug}".replace('_', ' ').replace('-', ' ').replace('/', ' ')
            is_manual = bool(re.search(r'\b(manual|guia|guía)\b', combined_text))
            is_cu = bool(
                re.search(r'\b(caso de uso|casos de uso|casos de usos|use case)\b|\b\d+[\.\-_]?cu\b|\bcu[\.\-_\s]?\d+',
                          combined_text))
            if is_manual:
                evt_type = AuditEventType.MANUAL_CREATED.value if action == "created" else AuditEventType.MANUAL_UPDATED.value
            elif is_cu:
                evt_type = AuditEventType.UC_CREATED.value if action == "created" else AuditEventType.UC_UPDATED.value
            else:
                continue

            ref_id = slug if slug else (title if title else str(e.get("id")))

            # 5. Guardado idempotente en BD
            stmt = pg_insert(AuditEventDB).values(
                project_id=project_id, username=author, event_date=event_date,
                event_month=month, event_year=year, event_type=evt_type,
                reference_id=ref_id
            ).on_conflict_do_update(
                index_elements=['project_id', 'event_type', 'reference_id', 'username'],
                set_={'event_date': event_date}
            )
            db.execute(stmt)

        page += 1
        db.execute(text("""
                DELETE FROM audit_events a
                USING audit_events b
                WHERE a.project_id = b.project_id
                  AND a.username = b.username
                  AND a.event_month = b.event_month
                  AND a.event_year = b.event_year
                  AND a.reference_id = b.reference_id
                  AND ((a.event_type = 'UC_UPDATED' AND b.event_type = 'UC_CREATED') 
                    OR (a.event_type = 'MANUAL_UPDATED' AND b.event_type = 'MANUAL_CREATED'))
                  AND a.project_id = :pid
                  AND a.event_month = :month
                  AND a.event_year = :year
            """), {"pid": project_id, "month": month, "year": year})
    db.commit()


def fetch_and_store_issue_raised(project_id: int, month: int, year: int, db: Session):
    _, last_day = calendar.monthrange(year, month)
    start_date = datetime(year, month, 1, tzinfo=timezone.utc)
    end_date = datetime(year, month, last_day, 23, 59, 59, tzinfo=timezone.utc)

    page = 1
    while True:
        resp = gitlab_api_request("get", f"projects/{project_id}/events", params={
            "action": "created",
            "target_type": "issue",  # FIX: Minúsculas requeridas por la API
            "after": start_date.strftime("%Y-%m-%d"),
            "before": (end_date + timedelta(days=1)).strftime("%Y-%m-%d"),
            "per_page": 100, "page": page
        })
        if not resp or not resp.json(): break

        for e in resp.json():
            # Doble validación en Python (el JSON sí devuelve la primera en Mayúscula)
            if e.get("target_type") != "Issue":
                continue

            author = e.get("author_username")
            created_at_str = e.get("created_at")
            issue_iid = str(e.get("target_iid"))
            if not author or not created_at_str or not issue_iid: continue

            event_date = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
            stmt = pg_insert(AuditEventDB).values(
                project_id=project_id, username=author, event_date=event_date,
                event_month=month, event_year=year,
                event_type=AuditEventType.ISSUE_RAISED.value,
                reference_id=issue_iid
            ).on_conflict_do_nothing()
            db.execute(stmt)
        page += 1
    db.commit()


def fetch_and_store_issue_reviews(project_id: int, month: int, year: int, db: Session):
    _, last_day = calendar.monthrange(year, month)
    start_date = datetime(year, month, 1, tzinfo=timezone.utc)
    end_date = datetime(year, month, last_day, 23, 59, 59, tzinfo=timezone.utc)
    func_labels = set(LABEL_MAPPING[TaskStatus.FUNCTIONAL_REVIEW])

    page = 1
    while True:
        resp = gitlab_api_request("get", f"projects/{project_id}/issues", params={
            "updated_after": start_date.isoformat(),
            "updated_before": end_date.isoformat(),
            "per_page": 100, "page": page
        })
        if not resp or not resp.json(): break

        for issue in resp.json():
            issue_iid = str(issue["iid"])
            issue_created_at = datetime.fromisoformat(issue["created_at"].replace('Z', '+00:00'))

            ev_resp = gitlab_api_request("get", f"projects/{project_id}/issues/{issue_iid}/resource_label_events")
            if not ev_resp: continue

            for e in ev_resp.json():
                if e.get("action") == "add" and e.get("label") and e["label"]["name"] in func_labels:
                    event_date = datetime.fromisoformat(e["created_at"].replace('Z', '+00:00'))
                    if event_date.month == month and event_date.year == year:
                        author = e["user"]["username"]
                        is_on_time = (event_date - issue_created_at).days <= 3

                        stmt = pg_insert(AuditEventDB).values(
                            project_id=project_id, username=author, event_date=event_date,
                            event_month=month, event_year=year,
                            event_type=AuditEventType.ISSUE_REVIEWED.value,
                            is_on_time=is_on_time, reference_id=issue_iid
                        ).on_conflict_do_update(
                            index_elements=['project_id', 'event_type', 'reference_id', 'username'],
                            set_={'is_on_time': is_on_time, 'event_date': event_date}
                        )
                        db.execute(stmt)
        page += 1
    db.commit()


def sync_single_project(project_id: int, db: Session):
    tasks_found = defaultdict(list)
    for status_enum, label_variations in LABEL_MAPPING.items():
        for label in label_variations:
            response = gitlab_api_request("get", f"projects/{project_id}/issues?labels={urllib.parse.quote_plus(label)}&state=opened&per_page=100")
            if response is not None and response.status_code == 200:
                try:
                    tasks_json = response.json()
                    if tasks_json:
                        for task in tasks_json:
                            tasks_found[task['id']].append({"status": status_enum, "data": task})
                except requests.exceptions.JSONDecodeError:
                    continue
    
    # Borrar datos antiguos solo si vamos a actualizar o si no se encontró nada
    # (Nota: La lógica simplificada asume que si no hay error de red, la ausencia de tareas es real)
    try:
        db.query(GitLabTaskDB).filter(GitLabTaskDB.project_id == project_id).delete(synchronize_session=False)
    except Exception as e:
        print(f"Error borrando tareas antiguas: {e}")

    if not tasks_found:
        return
    
    tasks_to_insert = []
    for task_id, found_states in tasks_found.items():
        chosen_state = None
        if any(s['status'] == TaskStatus.FUNCTIONAL_REVIEW for s in found_states): chosen_state = TaskStatus.FUNCTIONAL_REVIEW
        elif any(s['status'] == TaskStatus.QA_REVIEW for s in found_states): chosen_state = TaskStatus.QA_REVIEW
        elif any(s['status'] == TaskStatus.IN_PROGRESS for s in found_states): chosen_state = TaskStatus.IN_PROGRESS
             
        if chosen_state:
            final_task_data = next(s['data'] for s in found_states if s['status'] == chosen_state)
            issue_iid = final_task_data.get("iid")
            metrics = calculate_cycle_metrics_logic(final_task_data, project_id, issue_iid)
            tasks_to_insert.append({"task_id": task_id, "project_id": final_task_data["project_id"], "task_status_label": chosen_state.value, "updated_at": final_task_data["updated_at"], "raw_data": final_task_data, "cycle_metrics": metrics})
        
    
    if tasks_to_insert:
        db.execute(pg_insert(GitLabTaskDB).values(tasks_to_insert))

def run_single_project_sync_wrapper(project_id: int):
    global SYNC_IN_PROGRESS
    if SYNC_IN_PROGRESS:
        print(f"--- [SYNC] Salto: Sincronización en progreso. No se puede iniciar para proyecto {project_id}.")
        return

    try:
        SYNC_IN_PROGRESS = True
        print(f"--- [SYNC] Iniciando sincronización ÚNICA para proyecto {project_id}... ---")
        
        # Creamos una sesión dedicada para esta tarea
        db = SessionLocal()
        try:
            # Usamos una transacción explícita
            with db.begin():
                sync_single_project(project_id, db)
                
                # Actualizamos la marca de tiempo global también para reflejar actividad
                stmt = pg_insert(SystemMetadata).values(key="singleton", last_sync_time=func.now()).on_conflict_do_update(index_elements=['key'], set_={'last_sync_time': func.now()})
                db.execute(stmt)
        except Exception as e:
            print(f"--- [SYNC] 🚨 Error en sincronización de proyecto {project_id}: {e}")
        finally:
            db.close()
            
        print(f"--- [SYNC] ✅ Sincronización de proyecto {project_id} finalizada.")
    finally:
        SYNC_IN_PROGRESS = False

def run_full_sync(db: Session):
    global SYNC_IN_PROGRESS
    if SYNC_IN_PROGRESS: return
    try:
        SYNC_IN_PROGRESS = True
        with db.begin():
            projects = db.query(MonitoredProject).filter(MonitoredProject.is_active == True).all()
            if projects:
                for project in projects:
                    sync_single_project(project.project_id, db)
            stmt = pg_insert(SystemMetadata).values(key="singleton", last_sync_time=func.now()).on_conflict_do_update(index_elements=['key'], set_={'last_sync_time': func.now()})
            db.execute(stmt)
    except Exception as e:
        print(f"Error en ciclo de sync: {e}")
        # El rollback es automático con 'with db.begin()'
    finally:
        SYNC_IN_PROGRESS = False

def run_full_sync_wrapper():
    db = SessionLocal()
    try:
        run_full_sync(db)
    finally:
        db.close()

def sync_all_projects_periodically(interval_seconds: int):
    while True:
        run_full_sync_wrapper()
        time.sleep(interval_seconds)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("--- [STARTUP] Iniciando Backend... ---")
    for i in range(15): # Intentos de conexión
        try:
            db_check = SessionLocal(); db_check.execute(func.now()); db_check.close()
            print("--- [STARTUP] DB Conectada. ---")
            break
        except Exception as e:
            print(f"--- [STARTUP] Esperando DB ({i})... {e}")
            time.sleep(2)
    else:
        print("--- [STARTUP] Error Fatal: No DB Connection ---")
        # No lanzamos excepción aquí para permitir que el contenedor viva y arroje logs,
        # aunque la app no funcione correctamente.
    
    db = SessionLocal()
    try:
        Base.metadata.create_all(bind=engine)
        db.execute(text("ALTER TABLE monitored_projects ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;"))
        db.commit()

        if os.path.exists(PROJECTS_CSV_PATH):
            df = pd.read_csv(PROJECTS_CSV_PATH)
            for _, row in df.iterrows():
                stmt = pg_insert(MonitoredProject).values(project_id=row['project_id'], project_name=row['project_name']).on_conflict_do_update(index_elements=['project_id'], set_={'project_name': row['project_name']})
                db.execute(stmt)
            db.commit()
    except Exception as e:
         print(f"--- [STARTUP] Error poblando proyectos: {e}")
    finally:
        db.close()

    Thread(target=run_full_sync_wrapper, daemon=True).start()
    Thread(target=sync_all_projects_periodically, args=(SYNC_INTERVAL_SECONDS,), daemon=True).start()
    yield

app = FastAPI(title="Portal API v6.7.0", version="6.7.0", lifespan=lifespan, root_path="/api")

# --- Endpoints ---
def http_gitlab_api_request(method: str, endpoint: str, **kwargs) -> requests.Response:
    if not PRIVATE_TOKEN: raise HTTPException(status_code=500, detail="GitLab token no configurado.")
    headers = {"PRIVATE-TOKEN": PRIVATE_TOKEN}
    api_url = f"{GITLAB_URL}/api/v4/{endpoint}"
    try:
        response = requests.request(method, api_url, headers=headers, verify=False, timeout=10, **kwargs)
        response.raise_for_status()
        return response
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Error de red: {e}")

@app.get("/sync/status", response_model=Dict[str, bool], tags=["Database Sync"])
def get_sync_status(): return {"is_syncing": SYNC_IN_PROGRESS}

@app.post("/sync/all", status_code=202, tags=["Database Sync"])
def force_full_sync(background_tasks: BackgroundTasks):
    if SYNC_IN_PROGRESS: raise HTTPException(status_code=409, detail="Una sincronización ya está en progreso.")
    background_tasks.add_task(run_full_sync_wrapper)
    return {"message": "La sincronización completa ha sido iniciada en segundo plano."}

@app.get("/sync/last_time", response_model=Dict[str, Optional[str]], tags=["Database Sync"])
def get_last_sync_time(db: Session = Depends(get_db)):
    metadata = db.query(SystemMetadata).filter(SystemMetadata.key == "singleton").first()
    return {"last_sync_time": metadata.last_sync_time.isoformat() if metadata and metadata.last_sync_time else None}

@app.get("/projects/active_from_db", response_model=List[ProjectSummary], tags=["Task Dashboard (DB)"])
def get_active_projects_from_db(label: TaskStatus = Query(...), db: Session = Depends(get_db)):
    results = db.query(MonitoredProject.project_id, MonitoredProject.project_name, func.count(GitLabTaskDB.task_id).label("task_count")).join(GitLabTaskDB, MonitoredProject.project_id == GitLabTaskDB.project_id).filter(GitLabTaskDB.task_status_label == label.value, MonitoredProject.is_active == True).group_by(MonitoredProject.project_id, MonitoredProject.project_name).order_by(func.count(GitLabTaskDB.task_id).desc()).all()
    return [ProjectSummary(id=pid, name=pname, review_task_count=count) for pid, pname, count in results]

@app.get("/tasks/all_by_label", response_model=List[TaskWithProject], tags=["Task Dashboard (DB)"])
def get_all_tasks_by_label(label: TaskStatus = Query(...), db: Session = Depends(get_db)):
    # 1. Consulta optimizada y formateada para legibilidad
    db_tasks = db.query(GitLabTaskDB, MonitoredProject.project_name)\
        .join(MonitoredProject, GitLabTaskDB.project_id == MonitoredProject.project_id)\
        .filter(GitLabTaskDB.task_status_label == label.value, MonitoredProject.is_active == True)\
        .order_by(MonitoredProject.project_name, GitLabTaskDB.updated_at.desc())\
        .all()
    
    task_list = []
    for db_task, project_name in db_tasks:
        issue = db_task.raw_data
        
        # 2. Extracción de datos limpia (Evitamos una sola línea gigante)
        assignee = issue.get("assignees", [{}])[0].get("name") if issue.get("assignees") else None
        milestone = issue.get("milestone", {}).get("title") if issue.get("milestone") else None
        
        raw_time_stats = issue.get("time_stats", {}) or {}
        time_stats_obj = TimeStats(
            human_time_estimate=raw_time_stats.get("human_time_estimate"), 
            human_total_time_spent=raw_time_stats.get("human_total_time_spent")
        )

        # 3. Construcción del objeto de respuesta
        task_list.append(TaskWithProject(
            project_id=issue.get("project_id"), 
            title=issue.get("title", "N/A"), 
            description=issue.get("description"), 
            author=issue.get("author", {}).get("name", "N/A"), 
            url=issue.get("web_url", "#"), 
            assignee=assignee, 
            milestone=milestone, 
            project_name=project_name, 
            created_at=issue.get("created_at"), 
            updated_at=issue.get("updated_at"), 
            labels=issue.get("labels", []), 
            time_stats=time_stats_obj, 
            
            # --- CORRECCIÓN CRÍTICA ---
            # Antes: b_task.cycle_metrics (Error)
            # Ahora: db_task.cycle_metrics (Correcto)
            # Explicación: Usamos 'db_task' que es la variable definida en el 'for'
            cycle_metrics=db_task.cycle_metrics or {"execution_days": 0, "review_days": 0, "functional_days": 0}
        ))
        
    return task_list

@app.post("/sync/project/{project_id}", status_code=202, tags=["Database Sync"])
def force_single_project_sync(project_id: int, background_tasks: BackgroundTasks):
    if SYNC_IN_PROGRESS: 
        raise HTTPException(status_code=409, detail="Una sincronización ya está en progreso.")
    
    background_tasks.add_task(run_single_project_sync_wrapper, project_id)
    return {"message": f"Sincronización iniciada para el proyecto {project_id}."}

@app.get("/wiki/projects", response_model=List[ProjectSummary], tags=["Wiki"])
def get_projects_with_wiki(db: Session = Depends(get_db)):
    """
    Retorna la lista de proyectos monitoreados para seleccionar cuál wiki ver.
    """
    projects = db.query(MonitoredProject).filter(MonitoredProject.is_active == True).all()
    # Mapeamos al modelo ProjectSummary con review_task_count en 0 ya que no es relevante aquí
    return [ProjectSummary(id=p.project_id, name=p.project_name, review_task_count=0) for p in projects]

@app.get("/wiki/projects/{project_id}/pages", tags=["Wiki"])
def get_wiki_pages_list(project_id: int):
    """
    Obtiene la lista de páginas de la wiki para un proyecto específico.
    """
    response = http_gitlab_api_request("get", f"projects/{project_id}/wikis")
    return response.json()

@app.get("/wiki/projects/{project_id}/pages/{slug}", tags=["Wiki"])
def get_wiki_page_content(project_id: int, slug: str):
    """
    Obtiene el contenido de una página específica.
    """
    # GitLab requiere que el slug sea URL-encoded si contiene espacios o caracteres especiales
    safe_slug = urllib.parse.quote(slug, safe='')
    response = http_gitlab_api_request("get", f"projects/{project_id}/wikis/{safe_slug}")
    return response.json()

@app.get("/wiki/projects/{project_id}/audit", tags=["Wiki"])
def audit_wiki_changes(
    project_id: int, 
    username: str = Query(..., description="Username de GitLab a auditar"),
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2000)
):
    """
    Busca eventos de edición de Wiki realizados por un usuario en un mes específico.
    """
    import datetime
    
    # 1. Definir el rango temporal
    start_date = datetime.date(year, month, 1)
    if month == 12:
        end_date = datetime.date(year + 1, 1, 1)
    else:
        end_date = datetime.date(year, month + 1, 1)

    # 2. Consultar el endpoint de Eventos de GitLab
    # target_type=wiki es el filtro clave aquí
    params = {
        "after": start_date.isoformat(),
        "before": end_date.isoformat(),
        "sort": "desc"
    }
    
    response = http_gitlab_api_request(
        "get", 
        f"projects/{project_id}/events", 
        params=params
    )
    events = response.json()

    # 3. Filtrar por usuario y tipo de objetivo (WikiPage)
    # Nota: Filtramos en Python porque la API de eventos a veces es limitada en queries
    user_wiki_events = [
        {
            "page_title": e.get("target_title"),
            "action": e.get("action_name"),
            "created_at": e.get("created_at"),
            "author": e.get("author_username")
        }
        for e in events 
        if e.get("author_username") == username 
        and e.get("target_type") == "WikiPage"
    ]

    return {
        "project_id": project_id,
        "audit_count": len(user_wiki_events),
        "events": user_wiki_events
    }


def run_audit_sync_wrapper(month: int, year: int):
    global AUDIT_SYNC_IN_PROGRESS
    if AUDIT_SYNC_IN_PROGRESS: return
    try:
        AUDIT_SYNC_IN_PROGRESS = True
        db = SessionLocal()
        try:
            projects = db.query(MonitoredProject).filter(MonitoredProject.is_active == True).all()
            for project in projects:
                try:
                    fetch_and_store_wiki_events(project.project_id, month, year, db)
                    fetch_and_store_issue_raised(project.project_id, month, year, db)
                    fetch_and_store_issue_reviews(project.project_id, month, year, db)
                except Exception as e:
                    print(f"---[AUDIT] Error syncing project {project.project_id}: {e}")
                    db.rollback()  # Contains error to the single project
        finally:
            db.close()
    finally:
        AUDIT_SYNC_IN_PROGRESS = False


@app.post("/audit/sync", status_code=202, tags=["Audit"])
def start_audit_sync(month: int = Query(...), year: int = Query(...), background_tasks: BackgroundTasks = None):
    global AUDIT_SYNC_IN_PROGRESS
    if AUDIT_SYNC_IN_PROGRESS:
        raise HTTPException(status_code=409, detail="Audit sync already in progress.")

    if background_tasks:
        background_tasks.add_task(run_audit_sync_wrapper, month, year)

    return {"message": "Audit synchronization started in background."}


@app.get("/audit/sync/status", response_model=Dict[str, bool], tags=["Audit"])
def get_audit_sync_status():
    return {"is_syncing": AUDIT_SYNC_IN_PROGRESS}


@app.get("/audit/metrics", response_model=List[TesterAuditMetrics], tags=["Audit"])
def get_audit_metrics(month: int = Query(...), year: int = Query(...), db: Session = Depends(get_db)):
    results = db.query(
        AuditEventDB.username,
        func.sum(case((AuditEventDB.event_type == AuditEventType.ISSUE_RAISED.value, 1), else_=0)).label(
            'issues_raised'),
        func.sum(case((AuditEventDB.event_type == AuditEventType.ISSUE_REVIEWED.value, 1), else_=0)).label(
            'issues_reviewed'),
        func.sum(case(
            ((AuditEventDB.event_type == AuditEventType.ISSUE_REVIEWED.value) & (AuditEventDB.is_on_time == True), 1),
            else_=0)).label('issues_reviewed_on_time'),
        func.sum(case((AuditEventDB.event_type == AuditEventType.UC_CREATED.value, 1), else_=0)).label('uc_created'),
        func.sum(case((AuditEventDB.event_type == AuditEventType.UC_UPDATED.value, 1), else_=0)).label('uc_updated'),
        func.sum(case((AuditEventDB.event_type == AuditEventType.MANUAL_CREATED.value, 1), else_=0)).label(
            'manual_created'),
        func.sum(case((AuditEventDB.event_type == AuditEventType.MANUAL_UPDATED.value, 1), else_=0)).label(
            'manual_updated'),
        func.sum(case((AuditEventDB.event_type == AuditEventType.PUSH_EVENT.value, 1), else_=0)).label(
            'total_pushes')
    ).join(
        MonitoredProject, AuditEventDB.project_id == MonitoredProject.project_id
    ).filter(
        MonitoredProject.is_active == True,
        AuditEventDB.event_month == month,
        AuditEventDB.event_year == year
    ).group_by(
        AuditEventDB.username
    ).all()

    return [
        TesterAuditMetrics(
            username=r.username,
            issues_raised=r.issues_raised or 0,
            issues_reviewed=r.issues_reviewed or 0,
            issues_reviewed_on_time=r.issues_reviewed_on_time or 0,
            uc_created=r.uc_created or 0,
            uc_updated=r.uc_updated or 0,
            manual_created=r.manual_created or 0,
            manual_updated=r.manual_updated or 0,
            total_pushes=r.total_pushes or 0
        ) for r in results
    ]


class WikiEventDetail(BaseModel):
    username: str
    project_name: str
    event_date: str
    event_type: str
    reference_id: str


@app.get("/audit/wiki_details", response_model=List[WikiEventDetail], tags=["Audit"])
def get_wiki_details(month: int = Query(...), year: int = Query(...), db: Session = Depends(get_db)):
    results = db.query(AuditEventDB, MonitoredProject.project_name) \
        .join(MonitoredProject, AuditEventDB.project_id == MonitoredProject.project_id) \
        .filter(
        MonitoredProject.is_active == True,
        AuditEventDB.event_month == month,
        AuditEventDB.event_year == year,
        AuditEventDB.event_type.in_([
            AuditEventType.UC_CREATED.value, AuditEventType.UC_UPDATED.value,
            AuditEventType.MANUAL_CREATED.value, AuditEventType.MANUAL_UPDATED.value,
            AuditEventType.PUSH_EVENT.value,
            AuditEventType.ISSUE_RAISED.value, AuditEventType.ISSUE_REVIEWED.value
        ])
    ).order_by(AuditEventDB.event_date.desc()).all()

    return [
        WikiEventDetail(
            username=e.username,
            project_name=p_name,
            event_date=e.event_date.isoformat(),
            event_type=e.event_type,
            reference_id=e.reference_id
        )
        for e, p_name in results
    ]


def verify_config_pass(x_config_pass: str = Header(...)):
    if not CONFIG_TAB_PASS:
        raise HTTPException(status_code=500,
                            detail="ERROR DE SERVIDOR: La variable CONFIG_TAB_PASS no está inyectada en el contenedor.")
    if x_config_pass != CONFIG_TAB_PASS:
        raise HTTPException(status_code=401, detail="Acceso denegado: Credenciales inválidas.")



@app.post("/config/auth", tags=["Configuration"])
def authenticate_config(request: AuthRequest):
    if not CONFIG_TAB_PASS:
        raise HTTPException(status_code=500,
                            detail="ERROR DE SERVIDOR: La variable CONFIG_TAB_PASS no está inyectada en el contenedor. Revisa tu docker-compose y el archivo .env raíz.")
    if request.password != CONFIG_TAB_PASS:
        raise HTTPException(status_code=401, detail="Contraseña incorrecta.")
    return {"status": "ok"}


@app.get("/config/projects", response_model=List[ConfigProject], dependencies=[Depends(verify_config_pass)],
         tags=["Configuration"])
def get_config_projects(db: Session = Depends(get_db)):
    projects = db.query(MonitoredProject).order_by(MonitoredProject.project_name).all()
    return [ConfigProject(id=p.project_id, name=p.project_name, is_active=p.is_active) for p in projects]


@app.patch("/config/projects/{project_id}/toggle", dependencies=[Depends(verify_config_pass)], tags=["Configuration"])
def toggle_project_state(project_id: int, db: Session = Depends(get_db)):
    project = db.query(MonitoredProject).filter(MonitoredProject.project_id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    project.is_active = not project.is_active
    db.commit()
    return {"id": project.project_id, "is_active": project.is_active}
