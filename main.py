# main.py - Backend FastAPI (Versión Robusta y con Logs)
import csv
import os
from contextlib import asynccontextmanager
from typing import List

import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# --- Modelos de Datos (sin cambios) ---
class Task(BaseModel):
    title: str; description: str | None; author: str; url: str
    assignee: str | None; milestone: str | None
class ProjectSummary(BaseModel):
    id: str; name: str; review_task_count: int

# --- Configuración (sin cambios) ---
GITLAB_URL = os.getenv("GITLAB_URL", "https://gitlab.azcuba.cu")
PRIVATE_TOKEN = os.getenv("GITLAB_TOKEN")
LABEL_TO_TRACK = "PARA REVISIÓN"
PROJECTS = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    load_projects_from_csv(); yield
def load_projects_from_csv():
    global PROJECTS
    try:
        with open("projects.csv", mode="r", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                project_id = row.get("project_id"); project_name = row.get("project_name")
                if project_id and project_name:
                    PROJECTS[project_id.strip()] = project_name.strip()
            print(f"✅ Proyectos cargados desde CSV: {len(PROJECTS)} encontrados.")
    except Exception as e:
        print(f"🚨 Error al leer 'projects.csv': {e}")

app = FastAPI(title="GitLab Task Monitor API", version="1.0.0", lifespan=lifespan)

# --- Lógica de Negocio (Comunicación con GitLab) ---
def get_issues_from_gitlab(project_id: str) -> List[dict]:
    if not PRIVATE_TOKEN:
        raise HTTPException(status_code=500, detail="El token de GitLab no está configurado.")
    headers = {"PRIVATE-TOKEN": PRIVATE_TOKEN}
    params = {"state": "opened", "labels": LABEL_TO_TRACK}
    api_url = f"{GITLAB_URL}/api/v4/projects/{project_id}/issues"
    try:
        response = requests.get(api_url, headers=headers, params=params, verify=False, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        # Esto es un error esperado (ej. 404 Not Found, 403 Forbidden)
        print(f"    - ⚠️ Aviso: Fallo de API para el proyecto {project_id}. Código: {http_err.response.status_code}")
        return None # Devolver None para indicar el fallo
    except requests.exceptions.RequestException as e:
        # Esto es un error de red (ej. timeout)
        print(f"    - ⚠️ Aviso: Fallo de red para el proyecto {project_id}. Error: {e}")
        return None # Devolver None para indicar el fallo

# --- Endpoints de la API ---
@app.get("/projects/", response_model=List[ProjectSummary])
def get_projects_summary():
    """
    Devuelve un resumen de proyectos, ignorando aquellos que fallen.
    """
    if not PROJECTS: return []
    summary_list = []
    print("\n--- [LOG] Iniciando barrido de proyectos ---")
    for project_id, project_name in PROJECTS.items():
        print(f"  - Procesando proyecto: '{project_name}' (ID: {project_id})")
        issues = get_issues_from_gitlab(project_id)

        # --- LÓGICA DE ROBUSTEZ ---
        # Si la llamada a la API falló (devuelve None), continuamos al siguiente proyecto.
        if issues is None:
            continue

        summary_list.append(
            ProjectSummary(id=project_id, name=project_name, review_task_count=len(issues))
        )
    print("--- [LOG] Barrido de proyectos finalizado ---\n")
    return summary_list

@app.get("/projects/{project_id}/review_tasks/", response_model=List[Task])
def get_project_review_tasks(project_id: str):
    if project_id not in PROJECTS:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado.")
    issues = get_issues_from_gitlab(project_id)
    if issues is None: # Si la API falla para un proyecto específico, devolver una lista vacía.
        return []
    task_list = []
    for issue in issues:
        assignee_name = issue["assignees"][0].get("name") if issue.get("assignees") else None
        milestone_title = issue["milestone"].get("title") if issue.get("milestone") else None
        task_list.append(Task(
            title=issue.get("title", "N/A"), description=issue.get("description"),
            author=issue.get("author", {}).get("name", "N/A"), url=issue.get("web_url", "#"),
            assignee=assignee_name, milestone=milestone_title,
        ))
    return task_list
