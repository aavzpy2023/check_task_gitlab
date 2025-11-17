import os
import sys
from collections import defaultdict
from pprint import pprint


import pandas as pd
import requests
import urllib3

# --- SSS: Copia de la infraestructura necesaria de main.py ---
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Cargar variables de entorno (asume que se ejecuta en el mismo entorno que la app)
from dotenv import load_dotenv

load_dotenv()

GITLAB_URL = os.getenv("GITLAB_URL")
PRIVATE_TOKEN = os.getenv("GITLAB_TOKEN")
PROJECTS_CSV_PATH = "./projects.csv"


def gitlab_api_request(method: str, endpoint: str, **kwargs) -> requests.Response:
    if not PRIVATE_TOKEN:
        raise ValueError("GitLab token no configurado.")
    headers = {"PRIVATE-TOKEN": PRIVATE_TOKEN}
    api_url = f"{GITLAB_URL}/api/v4/{endpoint}"
    try:
        response = requests.request(
            method, api_url, headers=headers, verify=False, timeout=15, **kwargs
        )
        response.raise_for_status()
        return response
    except requests.exceptions.RequestException as e:
        print(
            f"ERROR: Fallo en la petición a GitLab API ({api_url}): {e}",
            file=sys.stderr,
        )
        return None

def discover_labels():
    """
    Audita todos los proyectos monitoreados, descubre variaciones de etiquetas
    y genera un diccionario de mapeo para la aplicación principal.
    """
    print("--- [AUDITORÍA DE ETIQUETAS] Iniciando escaneo... ---")

    # Palabras clave para identificar cada categoría (en minúsculas)
    KEYWORDS = {
        "FUNCTIONAL_REVIEW": ["funcional"],
        "QA_REVIEW": ["revisión", "revision"],
        "IN_PROGRESS": ["ejecucion", "ejecución"],
    }

    if not os.path.exists(PROJECTS_CSV_PATH):
        print(
            f"FATAL: No se encontró el archivo '{PROJECTS_CSV_PATH}'.", file=sys.stderr
        )
        return

    try:
        projects_df = pd.read_csv(PROJECTS_CSV_PATH)
        project_ids = projects_df["project_id"].tolist()
    except Exception as e:
        print(f"FATAL: Error al leer '{PROJECTS_CSV_PATH}': {e}", file=sys.stderr)
        return

    print(f"Se auditarán {len(project_ids)} proyectos.")

    discovered_labels = defaultdict(set)

    for project_id in project_ids:
        print(f"  -> Escaneando Proyecto ID: {project_id}...")
        response = gitlab_api_request(
            "get", f"projects/{project_id}/labels?per_page=100"
        )
        if not response:
            continue

        project_labels = response.json()
        for label in project_labels:
            name_lower = label["name"].lower()

            # La lógica debe ir de lo más específico a lo más general
            if any(keyword in name_lower for keyword in KEYWORDS["FUNCTIONAL_REVIEW"]):
                discovered_labels["FUNCTIONAL_REVIEW"].add(label["name"])
            elif any(keyword in name_lower for keyword in KEYWORDS["QA_REVIEW"]):
                discovered_labels["QA_REVIEW"].add(label["name"])
            elif any(keyword in name_lower for keyword in KEYWORDS["IN_PROGRESS"]):
                discovered_labels["IN_PROGRESS"].add(label["name"])

    print("\n--- [AUDITORÍA COMPLETA] Descubrimiento finalizado. ---")
    if not discovered_labels:
        print("No se encontraron etiquetas que coincidan con las palabras clave.")
        return

    # Generar el diccionario de Python final
    final_mapping = {
        "TaskStatus.IN_PROGRESS": sorted(list(discovered_labels["IN_PROGRESS"])),
        "TaskStatus.QA_REVIEW": sorted(list(discovered_labels["QA_REVIEW"])),
        "TaskStatus.FUNCTIONAL_REVIEW": sorted(
            list(discovered_labels["FUNCTIONAL_REVIEW"])
        ),
    }

    print(
        "\nCOPIE Y PEGUE EL SIGUIENTE BLOQUE EN 'backend/main.py' REEMPLAZANDO 'LABEL_MAPPING':\n"
    )
    print("LABEL_MAPPING = {")
    for key, labels in final_mapping.items():
        print(f"    {key}: {labels},")
    print("}")
    print("\n--- [FIN DEL SCRIPT] ---")


if __name__ == "__main__":
    discover_labels()
