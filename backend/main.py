import enum
import os
import sys
import tempfile
import time
from contextlib import asynccontextmanager
from threading import Thread
from typing import Any, Dict, List, Optional
from collections import defaultdict

import pandas as pd
import pypandoc
import requests
import urllib3
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query
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
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, declarative_base, sessionmaker

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- Configuración ---
GITLAB_URL = os.getenv("GITLAB_URL")
PRIVATE_TOKEN = os.getenv("GITLAB_TOKEN")
DATABASE_URL = f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@postgres_chatbot:5432/{os.getenv('POSTGRES_DB')}"
SYNC_INTERVAL_SECONDS = int(os.getenv("SYNC_INTERVAL_SECONDS", 600))
PROJECTS_CSV_PATH = "./projects.csv"
SYNC_IN_PROGRESS = False

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

class SystemMetadata(Base):
    __tablename__ = "system_metadata"
    key = Column(String(50), primary_key=True, default="singleton")
    last_sync_time = Column(DateTime(timezone=True), server_default=func.now())

class MonitoredProject(Base):
    __tablename__ = "monitored_projects"
    project_id = Column(BigInteger, primary_key=True, index=True)
    project_name = Column(String(255), nullable=False)

class GitLabTaskDB(Base):
    __tablename__ = "gitlab_tasks"
    task_id = Column(BigInteger, primary_key=True)
    project_id = Column(BigInteger, ForeignKey("monitored_projects.project_id"), nullable=False, index=True)
    task_status_label = Column(String(50), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True))
    raw_data = Column(JSONB)

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
    labels: List[str] = []
    time_stats: TimeStats = Field(default_factory=TimeStats)

class TaskWithProject(Task):
    project_name: str

class ProjectSummary(BaseModel):
    id: int
    name: str
    review_task_count: int

# --- Lógica de Sincronización ---
def sync_single_project(project_id: int, db: Session):
    try:
        db.query(GitLabTaskDB).filter(GitLabTaskDB.project_id == project_id).delete(synchronize_session=False)
        tasks_found = defaultdict(list)
        for status_enum, label_variations in LABEL_MAPPING.items():
            for label in label_variations:
                print(f"--- [SYNC] Proyecto {project_id}: Consultando etiqueta '{label}'...")
                try:
                    tasks_json = gitlab_api_request("get", f"projects/{project_id}/issues?labels={label}&state=opened&per_page=100").json()
                    if tasks_json:
                        for task in tasks_json:
                            tasks_found[task['id']].append({"status": status_enum, "data": task})
                except Exception: continue
        tasks_to_insert = []
        for task_id, found_states in tasks_found.items():
            chosen_state = None
            if any(s['status'] == TaskStatus.FUNCTIONAL_REVIEW for s in found_states): chosen_state = TaskStatus.FUNCTIONAL_REVIEW
            elif any(s['status'] == TaskStatus.QA_REVIEW for s in found_states): chosen_state = TaskStatus.QA_REVIEW
            elif any(s['status'] == TaskStatus.IN_PROGRESS for s in found_states): chosen_state = TaskStatus.IN_PROGRESS
            if chosen_state:
                final_task_data = next(s['data'] for s in found_states if s['status'] == chosen_state)
                tasks_to_insert.append({"task_id": task_id, "project_id": final_task_data["project_id"], "task_status_label": chosen_state.value, "updated_at": final_task_data["updated_at"], "raw_data": final_task_data})
        if tasks_to_insert:
            db.execute(pg_insert(GitLabTaskDB).values(tasks_to_insert))
        db.commit()
        print(f"--- [SYNC] ✅ Proyecto {project_id}: Sincronización exitosa. {len(tasks_to_insert)} tareas únicas procesadas.")
    except Exception as e:
        print(f"--- [SYNC] 🚨 FALLO para proyecto {project_id}: {e}")
        db.rollback()

def run_full_sync(db: Session):
    global SYNC_IN_PROGRESS
    if SYNC_IN_PROGRESS:
        print("--- [SYNC] Advertencia: Se intentó iniciar una sincronización mientras otra ya estaba en curso.")
        return
    
    try:
        SYNC_IN_PROGRESS = True
        print(f"--- [SYNC] Iniciando ciclo... ---")
        projects = db.query(MonitoredProject).all()
        if not projects:
            print("--- [SYNC] No hay proyectos para sincronizar.")
            return
        
        for project in projects:
            sync_single_project(project.project_id, db)
        
        stmt = pg_insert(SystemMetadata).values(key="singleton", last_sync_time=func.now()).on_conflict_do_update(index_elements=['key'], set_={'last_sync_time': func.now()})
        db.execute(stmt)
        db.commit()
        print(f"--- [SYNC] ✅ Ciclo completado. Hora actualizada. ---")
    finally:
        SYNC_IN_PROGRESS = False
        print(f"--- [SYNC] Finalizando ciclo. Lock liberado. ---")

def sync_all_projects_periodically(interval_seconds: int):
    while True:
        db = SessionLocal()
        try:
            run_full_sync(db)
        except Exception as e:
            print(f"--- [SYNC THREAD] 🚨 ERROR CRÍTICO durante el ciclo: {e}")
        finally:
            db.close()
        print(f"--- [SYNC THREAD] Esperando {interval_seconds} segundos. ---")
        time.sleep(interval_seconds)

def gitlab_api_request(method: str, endpoint: str, raise_for_status: bool = True, **kwargs) -> requests.Response:
    if not PRIVATE_TOKEN:
        raise HTTPException(status_code=500, detail="GitLab token no configurado.")
    headers = {"PRIVATE-TOKEN": PRIVATE_TOKEN}
    api_url = f"{GITLAB_URL}/api/v4/{endpoint}"
    try:
        response = requests.request(method, api_url, headers=headers, verify=False, timeout=10, **kwargs)
        if raise_for_status:
            response.raise_for_status()
        return response
    except requests.exceptions.HTTPError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"Error de GitLab API: {e.response.text}")
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Error de red: {e}")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("--- [STARTUP] Iniciando ciclo de vida de la aplicación... ---")
    db = SessionLocal()
    try:
        print("--- [STARTUP] Verificando y creando esquema de base de datos...")
        Base.metadata.create_all(bind=engine)
        print("--- [STARTUP] ✅ Esquema de BD verificado.")
        if db.query(MonitoredProject).count() == 0:
            print("--- [STARTUP] ℹ️ La tabla de proyectos está vacía. Intentando auto-poblar desde 'projects.csv'...")
            if not os.path.exists(PROJECTS_CSV_PATH):
                print(f"--- [STARTUP] ⚠️ ADVERTENCIA: No se encontró '{PROJECTS_CSV_PATH}'.")
            else:
                try:
                    df = pd.read_csv(PROJECTS_CSV_PATH)
                    projects_to_add = [MonitoredProject(project_id=int(row.project_id), project_name=str(row.project_name).strip()) for row in df.itertuples(index=False)]
                    db.add_all(projects_to_add)
                    db.commit()
                    print(f"--- [STARTUP] ✅ Se poblaron {len(projects_to_add)} proyectos desde el CSV usando Pandas.")
                except Exception as e:
                    print(f"--- [STARTUP] 🚨 ERROR al leer o procesar CSV con Pandas: {e}")
                    db.rollback()
        else:
            print("--- [STARTUP] ℹ️ La base de datos ya contiene proyectos. Saltando la fase de población.")
        sync_thread = Thread(target=sync_all_projects_periodically, args=(SYNC_INTERVAL_SECONDS,), daemon=True)
        sync_thread.start()
        print("--- [STARTUP] ✅ Hilo de sincronización iniciado.")
    except Exception as e:
        print(f"🚨 FATAL durante el arranque: {e}")
        db.rollback()
    finally:
        db.close()
    yield
    print("--- [SHUTDOWN] La aplicación se está apagando. ---")

app = FastAPI(title="Portal API v6.2", version="6.2.0", lifespan=lifespan, root_path="/api")

@app.post("/sync/all", status_code=202, tags=["Database Sync"])
def force_full_sync(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    background_tasks.add_task(run_full_sync, db)
    return {"message": "La sincronización completa ha sido iniciada en segundo plano."}

@app.get("/sync/last_time", response_model=Dict[str, Optional[str]], tags=["Database Sync"])
def get_last_sync_time(db: Session = Depends(get_db)):
    metadata = db.query(SystemMetadata).filter(SystemMetadata.key == "singleton").first()
    if metadata and metadata.last_sync_time:
        return {"last_sync_time": metadata.last_sync_time.isoformat()}
    return {"last_sync_time": None}

@app.get("/projects/active_from_db", response_model=List[ProjectSummary], tags=["Task Dashboard (DB)"])
def get_active_projects_from_db(label: TaskStatus = Query(...), db: Session = Depends(get_db)):
    label_value = label.value
    results = (db.query(MonitoredProject.project_id, MonitoredProject.project_name, func.count(GitLabTaskDB.task_id).label("task_count")).join(GitLabTaskDB, MonitoredProject.project_id == GitLabTaskDB.project_id).filter(GitLabTaskDB.task_status_label == label_value).group_by(MonitoredProject.project_id, MonitoredProject.project_name).order_by(func.count(GitLabTaskDB.task_id).desc()).all())
    return [ProjectSummary(id=pid, name=pname, review_task_count=count) for pid, pname, count in results]

@app.get("/tasks/all_by_label", response_model=List[TaskWithProject], tags=["Task Dashboard (DB)"])
def get_all_tasks_by_label(label: TaskStatus = Query(...), db: Session = Depends(get_db)):
    label_value = label.value
    db_tasks = (db.query(GitLabTaskDB, MonitoredProject.project_name).join(MonitoredProject, GitLabTaskDB.project_id == MonitoredProject.project_id).filter(GitLabTaskDB.task_status_label == label_value).order_by(MonitoredProject.project_name, GitLabTaskDB.updated_at.desc()).all())
    if not db_tasks: return []
    task_list = []
    for db_task, project_name in db_tasks:
        issue = db_task.raw_data
        assignee = issue.get("assignees", [{}])[0].get("name") if issue.get("assignees") else None
        milestone = issue.get("milestone", {}).get("title") if issue.get("milestone") else None
        raw_time_stats = issue.get("time_stats", {}) or {}
        time_stats_obj = TimeStats(human_time_estimate=raw_time_stats.get("human_time_estimate"), human_total_time_spent=raw_time_stats.get("human_total_time_spent"))
        task_list.append(TaskWithProject(project_id=issue.get("project_id"), title=issue.get("title", "N/A"), description=issue.get("description"), author=issue.get("author", {}).get("name", "N/A"), url=issue.get("web_url", "#"), assignee=assignee, milestone=milestone, project_name=project_name, created_at=issue.get("created_at"), labels=issue.get("labels", []), time_stats=time_stats_obj))
    return task_list


@app.get("/projects/{project_id}/tasks_from_db", response_model=List[Task], tags=["Task Dashboard (DB)"])
def get_project_tasks_from_db(project_id: int, label: TaskStatus = Query(...), db: Session = Depends(get_db)):
    label_value = label.value
    db_tasks = db.query(GitLabTaskDB).filter(GitLabTaskDB.project_id == project_id, GitLabTaskDB.task_status_label == label_value).all()
    if not db_tasks: return []
    task_list = []
    for db_task in db_tasks:
        issue = db_task.raw_data
        assignee = issue["assignees"][0].get("name") if issue.get("assignees") else None
        milestone = issue["milestone"].get("title") if issue.get("milestone") else None
        task_list.append(Task(title=issue.get("title", "N/A"), description=issue.get("description"), author=issue.get("author", {}).get("name", "N/A"), url=issue.get("web_url", "#"), assignee=assignee, milestone=milestone))
    return task_list



# === Endpoints de Sincronización y Gestión ===


@app.post("/sync/project/{project_id}", status_code=200, tags=["Database Sync"])
def sync_project_tasks(project_id: int, db: Session = Depends(get_db)):
    try:
        tasks = gitlab_api_request(
            "get",
            f"projects/{project_id}/issues?labels={LABEL_TO_TRACK}&state=opened&per_page=100",
        ).json()
    except HTTPException as e:
        print(
            f"ADVERTENCIA: No se pudo obtener tareas para el proyecto {project_id}. Razón: {e.detail}"
        )
        db.query(GitLabTaskDB).filter(GitLabTaskDB.project_id == project_id).delete(
            synchronize_session=False
        )
        db.commit()
        return {
            "message": f"No se pudieron obtener tareas para el proyecto {project_id}. Limpiando de la BD."
        }
    db.query(GitLabTaskDB).filter(GitLabTaskDB.project_id == project_id).delete(
        synchronize_session=False
    )
    if not tasks:
        db.commit()
        return {
            "message": "No se encontraron tareas en revisión. La base de datos ha sido actualizada."
        }
    tasks_to_insert = [
        {
            "task_id": t["id"],
            "project_id": t["project_id"],
            "updated_at": t["updated_at"],
            "raw_data": t,
        }
        for t in tasks
    ]
    if tasks_to_insert:
        db.execute(pg_insert(GitLabTaskDB).values(tasks_to_insert))
    db.commit()
    return {
        "message": f"Sincronización exitosa. {len(tasks_to_insert)} tareas procesadas."
    }


@app.get("/monitored_projects", tags=["Project Management"])
def get_monitored_projects(db: Session = Depends(get_db)):
    return db.query(MonitoredProject).order_by(MonitoredProject.project_name).all()


@app.post("/monitored_projects", status_code=201, tags=["Project Management"])
def add_monitored_project(project_id: int, project_name: str, db: Session = Depends(get_db)):
    existing_project = (
        db.query(MonitoredProject)
        .filter(MonitoredProject.project_id == project_id)
        .first()
    )
    if existing_project:
        raise HTTPException(
            status_code=409, detail="El proyecto ya está siendo monitoreado."
        )
    new_project = MonitoredProject(project_id=project_id, project_name=project_name)
    db.add(new_project)
    db.commit()
    db.refresh(new_project)
    return new_project


# === Endpoints de Sincronización con Gestión de Estado ===
@app.get("/sync/status", response_model=Dict[str, bool], tags=["Database Sync"])
def get_sync_status():
    """Consulta si un proceso de sincronización está actualmente en curso."""
    return {"is_syncing": SYNC_IN_PROGRESS}

@app.post("/sync/all", status_code=202, tags=["Database Sync"])
def force_full_sync(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Inicia una sincronización completa si no hay otra en curso."""
    if SYNC_IN_PROGRESS:
        raise HTTPException(status_code=409, detail="Una sincronización ya está en progreso.")
    
    background_tasks.add_task(run_full_sync, db)
    return {"message": "La sincronización completa ha sido iniciada en segundo plano."}