# backend/main.py
# SSS v4.2.0 - Backend de Producción v4.2 (Limpio y Desduplicado)

import csv
import os
import sys
import tempfile
from contextlib import asynccontextmanager
from typing import Any, Dict, List
from urllib.parse import unquote

import pypandoc
import requests
import urllib3
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import BigInteger, Column, DateTime, create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- Configuración ---
GITLAB_URL = os.getenv("GITLAB_URL")
PRIVATE_TOKEN = os.getenv("GITLAB_TOKEN")
LABEL_TO_TRACK = "PARA REVISIÓN"
PROJECTS: dict[str, str] = {}

DATABASE_URL = f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@postgres_chatbot:5432/{os.getenv('POSTGRES_DB')}"

# --- SQLAlchemy Setup ---
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# --- Modelos ---
class GitLabTaskDB(Base):
    __tablename__ = "gitlab_tasks"
    task_id = Column(BigInteger, primary_key=True)
    project_id = Column(BigInteger, nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True))
    raw_data = Column(JSONB)


class Task(BaseModel):
    title: str
    description: str | None
    author: str
    url: str
    assignee: str | None
    milestone: str | None


class ProjectSummary(BaseModel):
    id: str
    name: str
    review_task_count: int


# --- Lógica de la API de GitLab (ÚNICA FUNCIÓN) ---
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


# --- Dependency Injection y Lifespan ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def load_projects_from_csv():
    global PROJECTS
    try:
        with open("projects.csv", mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            PROJECTS = {
                row["project_id"].strip(): row["project_name"].strip() for row in reader
            }
            print(f"✅ Proyectos cargados desde CSV: {len(PROJECTS)} encontrados.")
    except Exception as e:
        print(f"🚨 ADVERTENCIA: No se pudo leer 'projects.csv'. Error: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("--- [STARTUP] Verificando conexión a BD y cargando proyectos... ---")
    try:
        with engine.connect():
            print("✅ Conexión a la base de datos establecida.")
    except Exception as e:
        print(
            f"🚨 FATAL: No se pudo conectar a la base de datos. El servicio se detendrá. Error: {e}"
        )
        sys.exit(1)
    load_projects_from_csv()
    yield


app = FastAPI(
    title="Portal de Documentación y Tareas API",
    version="4.4.0",
    lifespan=lifespan,
    root_path="/api",
)

# === API Endpoints ===


# --- Endpoints del Dashboard de Tareas ---
@app.get("/api/projects/", response_model=List[ProjectSummary], tags=["Task Dashboard"])
def get_projects_summary():
    if not PROJECTS:
        return []
    summary_list = []
    for pid, pname in PROJECTS.items():
        try:
            issues = gitlab_api_request(
                "get", f"projects/{pid}/issues?labels={LABEL_TO_TRACK}&state=opened"
            ).json()
            summary_list.append(
                ProjectSummary(id=pid, name=pname, review_task_count=len(issues))
            )
        except:
            summary_list.append(ProjectSummary(id=pid, name=pname, review_task_count=0))
    return summary_list


@app.get(
    "/api/projects/{project_id}/review_tasks/",
    response_model=List[Task],
    tags=["Task Dashboard"],
)
def get_project_review_tasks(project_id: str):
    if project_id not in PROJECTS:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado.")
    issues = gitlab_api_request(
        "get", f"projects/{project_id}/issues?labels={LABEL_TO_TRACK}&state=opened"
    ).json()
    task_list = []
    for issue in issues:
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


# --- Endpoint de Sincronización con BD ---
@app.post("/api/sync/project/{project_id}", status_code=200, tags=["Database Sync"])
def sync_project_tasks(
    project_id: str, db: Session = Depends(get_db)
):  # Tipo corregido a str
    tasks = gitlab_api_request(
        "get",
        f"projects/{project_id}/issues?labels={LABEL_TO_TRACK}&state=opened&per_page=100",
    ).json()
    if not tasks:
        return {"message": "No se encontraron tareas."}
    tasks_to_upsert = [
        {
            "task_id": t["id"],
            "project_id": t["project_id"],
            "updated_at": t["updated_at"],
            "raw_data": t,
        }
        for t in tasks
    ]
    stmt = pg_insert(GitLabTaskDB).values(tasks_to_upsert)
    stmt = stmt.on_conflict_do_update(
        index_elements=["task_id"],
        set_={
            "updated_at": stmt.excluded.updated_at,
            "raw_data": stmt.excluded.raw_data,
        },
    )
    db.execute(stmt)
    db.commit()
    return {
        "message": f"Sincronización exitosa. {len(tasks_to_upsert)} tareas procesadas."
    }


# --- Endpoints del Portal de Documentación ---
@app.get("/api/wiki/projects", tags=["Documentation Portal"])
def list_wiki_projects():
    if not PROJECTS:
        return []
    active_wikis = []
    for pid, pname in PROJECTS.items():
        try:
            resp = gitlab_api_request(
                "head", f"projects/{pid}/wikis/home", raise_for_status=False
            )
            if resp.status_code == 200:
                active_wikis.append({"id": pid, "name": pname})
        except:
            continue
    return active_wikis


@app.get("/api/wiki/projects/{project_id}/pages/tree", tags=["Documentation Portal"])
def get_wiki_pages_tree(project_id: str):  # Tipo corregido a str
    response = gitlab_api_request("get", f"projects/{project_id}/wikis")
    pages = response.json()
    tree_root = {}
    for page in pages:
        path_parts = page["slug"].split("/")
        current_level = tree_root
        for part in path_parts[:-1]:
            if part not in current_level:
                current_level[part] = {"type": "folder", "title": part, "children": {}}
            current_level = current_level[part]["children"]
        file_name = path_parts[-1]
        current_level[file_name] = {
            "type": "file",
            "title": page["title"],
            "slug": page["slug"],
        }

    def convert_tree_to_list(tree_dict: dict):
        node_list = []
        for key, node in tree_dict.items():
            if node["type"] == "folder":
                node["children"] = convert_tree_to_list(node["children"])
                node["children"].sort(key=lambda x: (x["type"] != "folder", x["title"]))
            node_list.append(node)
        return node_list

    final_list = convert_tree_to_list(tree_root)
    final_list.sort(key=lambda x: (x["type"] != "folder", x["title"]))
    return final_list


@app.get(
    "/api/wiki/projects/{project_id}/pages/{slug:path}", tags=["Documentation Portal"]
)
def get_wiki_page_content(project_id: str, slug: str):  # Tipo corregido a str
    decoded_slug = unquote(slug)
    page_data = gitlab_api_request(
        "get", f"projects/{project_id}/wikis/{decoded_slug}"
    ).json()
    return {
        "content": page_data.get("content", ""),
        "title": page_data.get("title", ""),
    }


@app.get(
    "/api/wiki/projects/{project_id}/generate_pdf/{slug:path}",
    tags=["Documentation Portal"],
)
def generate_pdf_on_demand(
    project_id: str, slug: str, background_tasks: BackgroundTasks
):  # Tipo corregido a str
    decoded_slug = unquote(slug)
    page_data = gitlab_api_request(
        "get", f"projects/{project_id}/wikis/{decoded_slug}"
    ).json()
    project_data = gitlab_api_request("get", f"projects/{project_id}").json()
    markdown_content = page_data.get("content")
    project_web_url = project_data.get("web_url")
    if not markdown_content:
        raise HTTPException(status_code=404, detail="No se encontró contenido.")
    if project_web_url:
        base_wiki_url = f"{project_web_url}/-/wikis/"
        markdown_content = markdown_content.replace(
            'src="uploads/', f'src="{base_wiki_url}uploads/'
        ).replace("(uploads/", f"({base_wiki_url}uploads/")
    temp_pdf = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    output_filename = temp_pdf.name
    temp_pdf.close()
    try:
        pypandoc.convert_text(
            markdown_content,
            "pdf",
            format="md",
            outputfile=output_filename,
            extra_args=["--pdf-engine=xelatex"],
        )
        background_tasks.add_task(os.remove, output_filename)
        return FileResponse(
            path=output_filename,
            media_type="application/pdf",
            filename=f"{decoded_slug.split('/')[-1]}.pdf",
        )
    except Exception as e:
        print(f"ERROR: Fallo al generar PDF para '{decoded_slug}': {str(e)}")
        os.remove(output_filename)
        raise HTTPException(status_code=500, detail=f"Error de Pandoc: {str(e)}")
