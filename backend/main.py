import csv
import os
import tempfile
from contextlib import asynccontextmanager
from typing import Any, Dict, List
from urllib.parse import unquote

import pypandoc
import requests
import urllib3

# SSS: Importar BackgroundTasks para la limpieza segura de archivos
from fastapi import BackgroundTasks, FastAPI, HTTPException

# SSS: Importar FileResponse para un envío de archivos eficiente
from fastapi.responses import FileResponse
from pydantic import BaseModel

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# --- Data Models (Pydantic) ---
# Defines the data structure for API responses, ensuring type safety.
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


# --- Configuration ---
# Load sensitive data and configuration from environment variables.
GITLAB_URL = os.getenv("GITLAB_URL", "https://gitlab.azcuba.cu")
PRIVATE_TOKEN = os.getenv("GITLAB_TOKEN")
LABEL_TO_TRACK = "PARA REVISIÓN"
PROJECTS: dict[str, str] = {}


# --- Lifespan Management ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager. Code here runs on application startup.
    Loads the project list from the CSV file into memory.
    """
    print("--- [STARTUP] Loading projects from CSV... ---")
    load_projects_from_csv()
    yield
    print("--- [SHUTDOWN] Application is shutting down. ---")


def load_projects_from_csv():
    """
    Reads the projects.csv file and populates the global PROJECTS dictionary.
    Handles potential file errors gracefully.
    """
    global PROJECTS
    try:
        with open("projects.csv", mode="r", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                project_id = row.get("project_id")
                project_name = row.get("project_name")
                if project_id and project_name:
                    PROJECTS[project_id.strip()] = project_name.strip()
            print(f"✅ Projects loaded successfully: {len(PROJECTS)} found.")
    except Exception as e:
        print(
            f"🚨 FATAL ERROR: Could not read 'projects.csv'. The application may not function correctly. Error: {e}"
        )


def gitlab_api_request(
    method: str, endpoint: str, raise_for_status: bool = True, **kwargs
):
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
        # Errores de API (4xx, 5xx)
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Error de GitLab API: {e.response.text}",
        )
    except requests.exceptions.RequestException as e:
        # Errores de red/conexión
        raise HTTPException(
            status_code=502, detail=f"Error de red al comunicar con GitLab API: {e}"
        )


app = FastAPI(title="GitLab Task Monitor API", version="1.0.0", lifespan=lifespan)


# --- Business Logic (GitLab API Interaction) ---
def get_issues_from_gitlab(project_id: str) -> List[dict] | None:
    """
    Fetches open issues with a specific label from a GitLab project.
    Designed for robustness, handling both API and network errors.

    Args:
        project_id (str): The ID of the GitLab project.

    Returns:
        List[dict] | None: A list of issue objects if successful, None on failure.
    """
    if not PRIVATE_TOKEN:
        raise HTTPException(
            status_code=500, detail="GitLab token is not configured on the server."
        )

    headers = {"PRIVATE-TOKEN": PRIVATE_TOKEN}
    params = {"state": "opened", "labels": LABEL_TO_TRACK}
    api_url = f"{GITLAB_URL}/api/v4/projects/{project_id}/issues"

    try:
        # verify=False is used for self-hosted GitLab instances with self-signed certs.
        response = requests.get(
            api_url, headers=headers, params=params, verify=False, timeout=10
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        print(
            f"    - ⚠️ API Warning: Call failed for project {project_id}. Status: {http_err.response.status_code}"
        )
        return None
    except requests.exceptions.RequestException as e:
        print(
            f"    - ⚠️ Network Warning: Call failed for project {project_id}. Error: {e}"
        )
        return None


# --- API Endpoints ---
@app.get("/projects/", response_model=List[ProjectSummary])
def get_projects_summary():
    """
    Returns a summary of all configured projects, including the count of tasks for review.
    It gracefully skips any projects where the GitLab API call fails.
    """
    if not PROJECTS:
        return []

    summary_list = []
    print("\n--- [LOG] Starting project scan... ---")
    for project_id, project_name in PROJECTS.items():
        print(f"  - Processing: '{project_name}' (ID: {project_id})")
        issues = get_issues_from_gitlab(project_id)
        if issues is None:
            continue

        summary_list.append(
            ProjectSummary(
                id=project_id, name=project_name, review_task_count=len(issues)
            )
        )
    print("--- [LOG] Project scan finished. ---\n")
    return summary_list


@app.get("/projects/{project_id}/review_tasks/", response_model=List[Task])
def get_project_review_tasks(project_id: str):
    """
    Retrieves all issues marked for review for a specific GitLab project.

    This endpoint queries the GitLab API for a given project ID and transforms
    the raw issue data into a structured list of Task objects. It is designed
    to be resilient, returning an empty list if the upstream API call fails,
    thus preventing errors in the frontend.

    Args:
        project_id (str): The ID of the GitLab project to query.

    Raises:
        HTTPException(404): If the provided project_id is not found in the
                            server's configured list of projects.

    Returns:
        List[Task]: A list of Task objects, each representing an issue
                    marked for review. Returns an empty list if no tasks
                    are found or if the GitLab API call fails.
    """
    if project_id not in PROJECTS:
        raise HTTPException(status_code=404, detail="Project not found.")

    issues = get_issues_from_gitlab(project_id)

    # Graceful handling of API failures.
    if issues is None:
        return []

    task_list = []
    for issue in issues:
        # Safely extract nested data, providing defaults to prevent crashes.
        assignee_name = (
            issue["assignees"][0].get("name") if issue.get("assignees") else None
        )
        milestone_title = (
            issue["milestone"].get("title") if issue.get("milestone") else None
        )

        task_list.append(
            Task(
                title=issue.get("title", "N/A"),
                description=issue.get("description"),
                author=issue.get("author", {}).get("name", "N/A"),
                url=issue.get("web_url", "#"),
                assignee=assignee_name,
                milestone=milestone_title,
            )
        )
    return task_list


# --- Lógica Auxiliar de la API de GitLab ---
def gitlab_api_get(endpoint: str):
    """Función auxiliar para realizar llamadas GET a la API de GitLab."""
    if not PRIVATE_TOKEN:
        raise HTTPException(status_code=500, detail="GitLab token no configurado.")
    headers = {"PRIVATE-TOKEN": PRIVATE_TOKEN}
    api_url = f"{GITLAB_URL}/api/v4/{endpoint}"
    try:
        response = requests.get(api_url, headers=headers, verify=False, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        raise HTTPException(
            status_code=502, detail=f"Error al comunicar con GitLab API: {e}"
        )


# --- Endpoints del Portal de Documentación ---


@app.get("/wiki/projects")
async def list_wiki_projects():
    """Devuelve SOLO los proyectos que tienen una wiki con al menos una página."""
    if not PROJECTS:
        return []

    active_wiki_projects = []
    print(
        "\n--- [LOG] Verificando proyectos con Wikis activas (Método GET Robusto) ---"
    )
    for pid, pname in PROJECTS.items():
        try:
            # SSS: Corrección Definitiva - Revertimos al método GET que sabemos que funciona.
            # Pedimos la lista de páginas de la wiki.
            response = gitlab_api_request(
                "get", f"projects/{pid}/wikis", raise_for_status=True
            )

            # Si la llamada tiene éxito (no lanza excepción) y la lista de páginas no está vacía...
            if response.json():
                print(f"  - ✅ Encontrada Wiki activa en: '{pname}' (ID: {pid})")
                active_wiki_projects.append({"id": pid, "name": pname})
            else:
                print(
                    f"  - ❌ Omitiendo proyecto con Wiki vacía: '{pname}' (ID: {pid})"
                )
        except HTTPException as e:
            # Captura errores como 404 (el proyecto no tiene wiki) o 403.
            print(
                f"  - ❌ Omitiendo proyecto (API Error): '{pname}' (ID: {pid}, Detalle: {e.detail})"
            )

    return active_wiki_projects


@app.get("/wiki/projects/{project_id}/pages/tree")
async def get_wiki_pages_tree(project_id: int) -> List[Dict[str, Any]]:
    """Obtiene las páginas de la wiki y las devuelve como una estructura de árbol correcta y completa."""
    response = gitlab_api_request("get", f"projects/{project_id}/wikis")
    if response.status_code != 200:
        return []
    pages = response.json()

    # SSS: Lógica de construcción de árbol final y robusta
    tree_root = {}
    for page in pages:
        path_parts = page["slug"].split("/")
        current_level = tree_root

        for part in path_parts[:-1]:  # Navegar o crear carpetas
            if part not in current_level:
                current_level[part] = {"type": "folder", "title": part, "children": {}}
            current_level = current_level[part]["children"]

        # Añadir el archivo al nivel actual
        file_name = path_parts[-1]
        current_level[file_name] = {
            "type": "file",
            "title": page["title"],
            "slug": page["slug"],
        }

    def convert_tree_to_list(tree_dict: dict):
        """Convierte recursivamente los diccionarios del árbol a listas ordenadas."""
        node_list = []
        for key, node in tree_dict.items():
            if node["type"] == "folder":
                node["children"] = convert_tree_to_list(node["children"])
                # Ordenar hijos: carpetas primero, luego archivos por título
                node["children"].sort(key=lambda x: (x["type"] != "folder", x["title"]))
            node_list.append(node)
        return node_list

    final_list = convert_tree_to_list(tree_root)
    # Ordenar el nivel raíz: carpetas primero, luego archivos por título
    final_list.sort(key=lambda x: (x["type"] != "folder", x["title"]))

    return final_list


@app.get("/wiki/projects/{project_id}/generate_pdf/{slug:path}")
async def generate_pdf_on_demand(
    project_id: int, slug: str, background_tasks: BackgroundTasks
):
    """
    Genera un PDF usando un archivo temporal y una tarea en segundo plano
    para una limpieza segura y sin condiciones de carrera.
    """
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
        )
        markdown_content = markdown_content.replace(
            "(uploads/", f"({base_wiki_url}uploads/"
        )

    # SSS: Corrección Crítica - Usar un archivo temporal que controlamos manualmente
    temp_pdf = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    output_filename = temp_pdf.name
    temp_pdf.close()

    try:
        pypandoc.convert_text(
            markdown_content,
            "pdf",
            format="md",
            outputfile=output_filename,  # Especificar el archivo de salida
            extra_args=["--pdf-engine=xelatex"],
        )

        # Añadir la tarea de limpieza. Se ejecutará DESPUÉS de que la respuesta se envíe.
        background_tasks.add_task(os.remove, output_filename)

        return FileResponse(
            path=output_filename,
            media_type="application/pdf",
            filename=f"{decoded_slug.split('/')[-1]}.pdf",
        )
    except Exception as e:
        error_message = f"Error de Pandoc: {str(e)}"
        print(f"ERROR: Fallo al generar PDF para '{decoded_slug}': {error_message}")
        os.remove(output_filename)  # Limpieza en caso de error
        raise HTTPException(status_code=500, detail=error_message)


@app.get("/wiki/projects/{project_id}/pages")
async def list_wiki_pages(project_id: int):
    """Obtiene la lista de todas las páginas en la wiki de un proyecto."""
    return gitlab_api_get(f"projects/{project_id}/wikis")


@app.get("/wiki/projects/{project_id}/pages/{slug:path}")
async def get_wiki_page_content(project_id: int, slug: str):
    """Obtiene el contenido raw de una página de la wiki específica."""
    # El slug llega codificado, lo decodificamos por si acaso
    decoded_slug = unquote(slug)
    page_data = gitlab_api_request(
        "get", f"projects/{project_id}/wikis/{decoded_slug}"
    ).json()
    return {
        "content": page_data.get("content", ""),
        "title": page_data.get("title", ""),
    }
