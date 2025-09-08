# main.py - Backend FastAPI (versión con carga desde CSV)
import csv
import os
from contextlib import asynccontextmanager
from typing import List

import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


# --- Modelos de Datos (Pydantic) ---
class Task(BaseModel):
    title: str
    description: str | None
    author: str
    url: str


class ProjectSummary(BaseModel):
    id: str
    name: str
    review_task_count: int


# --- Configuración ---
GITLAB_URL = os.getenv("GITLAB_URL", "https://gitlab.azcuba.cu")
PRIVATE_TOKEN = os.getenv("GITLAB_TOKEN")
LABEL_TO_TRACK = "PARA REVISIÓN"

# Variable global que será poblada desde el CSV al iniciar.
PROJECTS = {}


def load_projects_from_csv():
    """Carga la configuración de proyectos desde projects.csv."""
    global PROJECTS
    try:
        with open("projects.csv", mode="r", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                project_id = row.get("project_id")
                project_name = row.get("project_name")
                if project_id and project_name:
                    PROJECTS[project_id.strip()] = project_name.strip()
            print(
                f"✅ Proyectos cargados exitosamente desde CSV: {len(PROJECTS)} encontrados."
            )
    except FileNotFoundError:
        print(
            "⚠️ Advertencia: No se encontró el archivo 'projects.csv'. La lista de proyectos estará vacía."
        )
    except Exception as e:
        print(f"🚨 Error al leer 'projects.csv': {e}")


# 'lifespan' es la forma moderna en FastAPI para manejar eventos de inicio/apagado.
@asynccontextmanager
async def lifespan(app: FastAPI):
    load_projects_from_csv()
    yield


app = FastAPI(
    title="GitLab Task Monitor API",
    description="API para monitorear Issues en revisión en proyectos de GitLab.",
    version="1.0.0",
    lifespan=lifespan,
)


# --- Lógica de Negocio (Comunicación con GitLab) ---
def get_issues_from_gitlab(project_id: str) -> List[dict]:
    """Función central para obtener los issues en revisión de un proyecto."""
    if not PRIVATE_TOKEN:
        raise HTTPException(
            status_code=500,
            detail="El token de GitLab no está configurado en el servidor.",
        )

    headers = {"PRIVATE-TOKEN": PRIVATE_TOKEN}
    params = {"state": "opened", "labels": LABEL_TO_TRACK}
    api_url = f"{GITLAB_URL}/api/v4/projects/{project_id}/issues"

    try:
        response = requests.get(api_url, headers=headers, params=params, verify=False)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        raise HTTPException(
            status_code=503, detail=f"Error al contactar la API de GitLab: {e}"
        )


# --- Endpoints de la API ---
@app.get("/projects/", response_model=List[ProjectSummary])
def get_projects_summary():
    """
    Devuelve un resumen de todos los proyectos monitoreados y su cantidad
    de tareas en revisión.
    """
    if not PROJECTS:
        return []

    summary_list = []
    for project_id, project_name in PROJECTS.items():
        issues = get_issues_from_gitlab(project_id)
        summary_list.append(
            ProjectSummary(
                id=project_id, name=project_name, review_task_count=len(issues)
            )
        )
    return summary_list


@app.get("/projects/{project_id}/review_tasks/", response_model=List[Task])
def get_project_review_tasks(project_id: str):
    """
    Devuelve una lista detallada de las tareas en revisión para un proyecto específico.
    """
    if project_id not in PROJECTS:
        raise HTTPException(
            status_code=404,
            detail="Proyecto no encontrado o no configurado en projects.csv.",
        )

    issues = get_issues_from_gitlab(project_id)

    task_list = []
    for issue in issues:
        task_list.append(
            Task(
                title=issue.get("title", "N/A"),
                description=issue.get("description", "Sin descripción."),
                author=issue.get("author", {}).get("name", "N/A"),
                url=issue.get("web_url", "#"),
            )
        )
    return task_list
