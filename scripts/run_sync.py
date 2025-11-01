"""
SSS v4.2.0 - Orquestador de Sincronización de Tareas

Propósito:
  Este script se ejecuta de forma continua para mantener la base de datos
  actualizada con el estado de las tareas de GitLab. Obtiene la lista de
  proyectos monitoreados y dispara el proceso de sincronización para cada uno.

Uso:
  1. Ejecute este script en una terminal separada después de poblar los proyectos.
     python scripts/run_sync.py
  2. Se ejecutará indefinidamente, sincronizando cada X segundos.
"""

import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

API_BASE_URL = "http://localhost:8503/api"
SYNC_INTERVAL_SECONDS = int(
    os.getenv("SYNC_INTERVAL_SECONDS", 600)
)  # 10 minutos por defecto


def sync_all_projects():
    """Obtiene todos los proyectos y los sincroniza uno por uno."""
    print(f"--- [SYNC] Iniciando ciclo de sincronización a las {time.ctime()} ---")
    try:
        # 1. Obtener la lista de proyectos a monitorear desde nuestra BD
        projects_resp = requests.get(f"{API_BASE_URL}/monitored_projects")
        projects_resp.raise_for_status()
        projects = projects_resp.json()

        if not projects:
            print("--- [SYNC] No hay proyectos monitoreados en la BD. Saltando ciclo.")
            return

        print(f"--- [SYNC] Se sincronizarán {len(projects)} proyectos.")

        # 2. Sincronizar cada proyecto
        for project in projects:
            project_id = project["project_id"]
            project_name = project["project_name"]
            print(f"--- [SYNC] Procesando '{project_name}' (ID: {project_id})...")
            try:
                sync_resp = requests.post(f"{API_BASE_URL}/sync/project/{project_id}")
                sync_resp.raise_for_status()
                print(
                    f"--- [SYNC] ✅ Éxito para '{project_name}': {sync_resp.json().get('message')}"
                )
            except requests.exceptions.RequestException as e:
                print(f"--- [SYNC] 🚨 FALLO para '{project_name}': {e}")

    except requests.exceptions.RequestException as e:
        print(
            f"--- [SYNC] 🚨 ERROR CRÍTICO: No se pudo obtener la lista de proyectos. {e}"
        )


def main():
    while True:
        sync_all_projects()
        print(
            f"--- [SYNC] Ciclo completado. Esperando {SYNC_INTERVAL_SECONDS} segundos para el próximo ciclo. ---"
        )
        time.sleep(SYNC_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
