# backend/main.py
import enum
import os
import sys
import tempfile
import time
import urllib.parse
from contextlib import asynccontextmanager
from threading import Thread
from typing import Dict, List, Optional
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
# SSS: CORRECCION TYPO (POSTGRES_PASSWORD)
DATABASE_URL = f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST', 'postgres_chatbot')}:5432/{os.getenv('POSTGRES_DB')}"
SYNC_INTERVAL_SECONDS = int(os.getenv("SYNC_INTERVAL_SECONDS", 3600))
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
def gitlab_api_request(method: str, endpoint: str, **kwargs) -> Optional[requests.Response]:
    if not PRIVATE_TOKEN: return None
    headers = {"PRIVATE-TOKEN": PRIVATE_TOKEN}
    api_url = f"{GITLAB_URL}/api/v4/{endpoint}"
    try:
        response = requests.request(method, api_url, headers=headers, verify=False, timeout=15, **kwargs)
        return response
    except requests.exceptions.RequestException:
        return None

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
            tasks_to_insert.append({"task_id": task_id, "project_id": final_task_data["project_id"], "task_status_label": chosen_state.value, "updated_at": final_task_data["updated_at"], "raw_data": final_task_data})

    if tasks_to_insert:
        db.execute(pg_insert(GitLabTaskDB).values(tasks_to_insert))

def run_full_sync(db: Session):
    global SYNC_IN_PROGRESS
    if SYNC_IN_PROGRESS: return
    try:
        SYNC_IN_PROGRESS = True
        with db.begin():
            projects = db.query(MonitoredProject).all()
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
    results = db.query(MonitoredProject.project_id, MonitoredProject.project_name, func.count(GitLabTaskDB.task_id).label("task_count")).join(GitLabTaskDB, MonitoredProject.project_id == GitLabTaskDB.project_id).filter(GitLabTaskDB.task_status_label == label.value).group_by(MonitoredProject.project_id, MonitoredProject.project_name).order_by(func.count(GitLabTaskDB.task_id).desc()).all()
    return [ProjectSummary(id=pid, name=pname, review_task_count=count) for pid, pname, count in results]

@app.get("/tasks/all_by_label", response_model=List[TaskWithProject], tags=["Task Dashboard (DB)"])
def get_all_tasks_by_label(label: TaskStatus = Query(...), db: Session = Depends(get_db)):
    db_tasks = db.query(GitLabTaskDB, MonitoredProject.project_name).join(MonitoredProject, GitLabTaskDB.project_id == MonitoredProject.project_id).filter(GitLabTaskDB.task_status_label == label.value).order_by(MonitoredProject.project_name, GitLabTaskDB.updated_at.desc()).all()
    task_list = []
    for db_task, project_name in db_tasks:
        issue = db_task.raw_data; assignee = issue.get("assignees", [{}])[0].get("name") if issue.get("assignees") else None; milestone = issue.get("milestone", {}).get("title") if issue.get("milestone") else None; raw_time_stats = issue.get("time_stats", {}) or {}; time_stats_obj = TimeStats(human_time_estimate=raw_time_stats.get("human_time_estimate"), human_total_time_spent=raw_time_stats.get("human_total_time_spent"))
        task_list.append(TaskWithProject(project_id=issue.get("project_id"), title=issue.get("title", "N/A"), description=issue.get("description"), author=issue.get("author", {}).get("name", "N/A"), url=issue.get("web_url", "#"), assignee=assignee, milestone=milestone, project_name=project_name, created_at=issue.get("created_at"), labels=issue.get("labels", []), time_stats=time_stats_obj))
    return task_list

# Endpoints Wiki omitidos por brevedad si no son usados, o se asume que están. 
# (Si los necesitas, avísame, pero el error actual es de arranque, no de estos endpoints)