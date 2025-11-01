import os
import sys
import tempfile
import time
from contextlib import asynccontextmanager
from threading import Thread
from typing import Any, Dict, List, Optional

import pandas as pd
import pypandoc
import requests
import urllib3
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
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
LABEL_TO_TRACK = "PARA REVISIÓN"
DATABASE_URL = f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@postgres_chatbot:5432/{os.getenv('POSTGRES_DB')}"
SYNC_INTERVAL_SECONDS = int(os.getenv("SYNC_INTERVAL_SECONDS", 600))
PROJECTS_CSV_PATH = "./projects.csv"

# --- SQLAlchemy Setup ---
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# --- Modelos SQLAlchemy (sin cambios) ---
class MonitoredProject(Base):
    __tablename__ = "monitored_projects"
    project_id = Column(BigInteger, primary_key=True, index=True)
    project_name = Column(String(255), nullable=False)


class GitLabTaskDB(Base):
    __tablename__ = "gitlab_tasks"
    task_id = Column(BigInteger, primary_key=True)
    project_id = Column(
        BigInteger,
        ForeignKey("monitored_projects.project_id"),
        nullable=False,
        index=True,
    )
    updated_at = Column(DateTime(timezone=True))
    raw_data = Column(JSONB)


# --- Modelos Pydantic (sin cambios) ---


class TimeStats(BaseModel):
    human_time_estimate: Optional[str] = None
    human_total_time_spent: Optional[str] = None


class Task(BaseModel):
    title: str
    description: Optional[str]
    author: str
    url: str
    assignee: Optional[str]
    milestone: Optional[str]
    created_at: Optional[str] = None
    labels: List[str] = []
    time_stats: TimeStats = Field(default_factory=TimeStats)


class ProjectSummary(BaseModel):
    id: int
    name: str
    review_task_count: int


# --- SSS: LÓGICA DE SINCRONIZACIÓN AUTOMÁTICA ---
def sync_all_projects_periodically(interval_seconds: int):
    """Esta función se ejecuta en un hilo de fondo de forma continua."""
    while True:
        print(
            f"--- [SYNC THREAD] Iniciando ciclo de sincronización a las {time.ctime()} ---"
        )
        db = SessionLocal()
        try:
            projects = db.query(MonitoredProject).all()
            if not projects:
                print(
                    "--- [SYNC THREAD] No hay proyectos monitoreados para sincronizar."
                )
            else:
                print(f"--- [SYNC THREAD] Se sincronizarán {len(projects)} proyectos.")
                for project in projects:
                    sync_single_project(project.project_id, db)
        except Exception as e:
            print(
                f"--- [SYNC THREAD] 🚨 ERROR CRÍTICO durante el ciclo de sincronización: {e}"
            )
        finally:
            db.close()
        print(
            f"--- [SYNC THREAD] Ciclo completado. Esperando {interval_seconds} segundos. ---"
        )
        time.sleep(interval_seconds)


def sync_single_project(project_id: int, db: Session):
    try:
        tasks_json = gitlab_api_request(
            "get",
            f"projects/{project_id}/issues?labels={LABEL_TO_TRACK}&state=opened&per_page=100",
        ).json()
        db.query(GitLabTaskDB).filter(GitLabTaskDB.project_id == project_id).delete(
            synchronize_session=False
        )
        if not tasks_json:
            db.commit()
            print(
                f"--- [SYNC] ✅ Proyecto {project_id}: No se encontraron tareas. BD actualizada."
            )
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
            for t in tasks_json
        ]
        if tasks_to_insert:
            db.execute(pg_insert(GitLabTaskDB).values(tasks_to_insert))
        db.commit()
        print(
            f"--- [SYNC] ✅ Proyecto {project_id}: Sincronización exitosa. {len(tasks_to_insert)} tareas procesadas."
        )
        return {
            "message": f"Sincronización exitosa. {len(tasks_to_insert)} tareas procesadas."
        }
    except Exception as e:
        print(f"--- [SYNC] 🚨 FALLO para proyecto {project_id}: {e}")
        db.rollback()
        return {"message": f"Fallo al sincronizar proyecto {project_id}."}


# --- Lógica API GitLab & Dependencias (sin cambios) ---
def gitlab_api_request(
    method: str, endpoint: str, raise_for_status: bool = True, **kwargs
) -> requests.Response:
    if not PRIVATE_TOKEN:
        raise HTTPException(status_code=500, detail="GitLab token no configurado.")
    headers = {"PRIVATE-TOKEN": PRIVATE_TOKEN}
    api_url = f"{GITLAB_URL}/api/v4/{endpoint}"
    try:
        response = requests.request(
            method, api_url, headers=headers, verify=False, timeout=10, **kwargs
        )
        if raise_for_status:
            response.raise_for_status()
        return response
    except requests.exceptions.HTTPError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Error de GitLab API: {e.response.text}",
        )
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

        # SSS: LÓGICA DE AUTO-POBLACIÓN IDEMPOTENTE (AHORA CON PANDAS)
        if db.query(MonitoredProject).count() == 0:
            print(
                "--- [STARTUP] ℹ️ La tabla de proyectos está vacía. Intentando auto-poblar desde 'projects.csv'..."
            )
            if not os.path.exists(PROJECTS_CSV_PATH):
                print(
                    f"--- [STARTUP] ⚠️ ADVERTENCIA: No se encontró '{PROJECTS_CSV_PATH}'."
                )
            else:
                try:
                    df = pd.read_csv(PROJECTS_CSV_PATH)
                    projects_to_add = [
                        MonitoredProject(
                            project_id=int(row.project_id),
                            project_name=str(row.project_name).strip(),
                        )
                        for row in df.itertuples(index=False)
                    ]
                    db.add_all(projects_to_add)
                    db.commit()
                    print(
                        f"--- [STARTUP] ✅ Se poblaron {len(projects_to_add)} proyectos desde el CSV usando Pandas."
                    )
                except Exception as e:
                    print(
                        f"--- [STARTUP] 🚨 ERROR al leer o procesar CSV con Pandas: {e}"
                    )
                    db.rollback()
        else:
            print(
                "--- [STARTUP] ℹ️ La base de datos ya contiene proyectos. Saltando la fase de población."
            )

        print("--- [STARTUP] Iniciando hilo de sincronización en segundo plano...")
        sync_thread = Thread(
            target=sync_all_projects_periodically,
            args=(SYNC_INTERVAL_SECONDS,),
            daemon=True,
        )
        sync_thread.start()
        print("--- [STARTUP] ✅ Hilo de sincronización iniciado.")
    except Exception as e:
        print(f"🚨 FATAL durante el arranque: {e}")
        db.rollback()
    finally:
        db.close()

    yield
    print("--- [SHUTDOWN] La aplicación se está apagando. ---")


# SSS: root_path gestiona el prefijo /api. Los decoradores NO deben incluirlo.
app = FastAPI(
    title="Portal API v5.3", version="5.3.0", lifespan=lifespan, root_path="/api"
)

# === NUEVOS Endpoints del Dashboard (desde BD) ===


@app.get(
    "/projects/active_from_db",
    response_model=List[ProjectSummary],
    tags=["Task Dashboard (DB)"],
)
def get_active_projects_from_db(db: Session = Depends(get_db)):
    results = (
        db.query(
            MonitoredProject.project_id,
            MonitoredProject.project_name,
            func.count(GitLabTaskDB.task_id).label("task_count"),
        )
        .join(GitLabTaskDB, MonitoredProject.project_id == GitLabTaskDB.project_id)
        .group_by(MonitoredProject.project_id, MonitoredProject.project_name)
        .having(func.count(GitLabTaskDB.task_id) > 0)
        .order_by(func.count(GitLabTaskDB.task_id).desc())
        .all()
    )
    return [
        ProjectSummary(id=pid, name=pname, review_task_count=count)
        for pid, pname, count in results
    ]


@app.get(
    "/projects/{project_id}/tasks_from_db",
    response_model=List[Task],
    tags=["Task Dashboard (DB)"],
)
def get_project_tasks_from_db(project_id: int, db: Session = Depends(get_db)):
    db_tasks = (
        db.query(GitLabTaskDB).filter(GitLabTaskDB.project_id == project_id).all()
    )
    if not db_tasks:
        return []
    task_list = []
    for db_task in db_tasks:
        issue = db_task.raw_data
        assignee = issue["assignees"][0].get("name") if issue.get("assignees") else None
        milestone = issue["milestone"].get("title") if issue.get("milestone") else None
        task_list.append(
            Task(
                title=issue.get("title", "N/A"),
                description=issue.get("description"),
                author=issue.get("author", {}).get("name", "N/A"),
                url=issue.get("web_url", "#"),
                assignee=assignee,
                milestone=milestone,
            )
        )
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
def add_monitored_project(
    project_id: int, project_name: str, db: Session = Depends(get_db)
):
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
