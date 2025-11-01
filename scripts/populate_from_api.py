"""
SSS v4.2.0 - Script de Población de Proyectos vía API

Propósito:
  Lee proyectos desde `projects.csv` y los registra en la aplicación
  a través del endpoint POST /api/monitored_projects. Este método
  es robusto y no requiere acceso directo a la BD desde el host ni
  dependencias complejas.

Uso:
  1. Asegúrese de que todos los contenedores Docker estén en ejecución.
  2. Coloque `projects.csv` en la raíz del proyecto.
  3. Ejecute desde la raíz del proyecto:
     pip install requests python-dotenv
  4. Ejecute el script:
     python scripts/populate_from_api.py
"""

import csv
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

CSV_FILE_PATH = PROJECT_ROOT / "projects.csv"
API_BASE_URL = "http://localhost:8503/api"  # Usamos la URL del proxy Nginx


def main():
    print("--- SSS: Iniciando población de proyectos vía API ---")

    if not CSV_FILE_PATH.exists():
        print(f"🚨 FATAL: No se encontró 'projects.csv' en la raíz del proyecto.")
        sys.exit(1)

    with open(CSV_FILE_PATH, mode="r", encoding="utf-8") as infile:
        reader = csv.DictReader(infile)
        for row in reader:
            try:
                project_id = int(row["project_id"])
                project_name = str(row["project_name"]).strip()

                endpoint = f"{API_BASE_URL}/monitored_projects"
                params = {"project_id": project_id, "project_name": project_name}

                response = requests.post(endpoint, params=params)

                if response.status_code == 201:
                    print(f"✅ Añadido: ID={project_id}, Nombre='{project_name}'")
                elif response.status_code == 409:  # Conflict
                    print(
                        f"⚪ Omitido (ya existe): ID={project_id}, Nombre='{project_name}'"
                    )
                else:
                    response.raise_for_status()

            except (ValueError, KeyError) as e:
                print(
                    f"⚠️  Advertencia: Saltando fila inválida en CSV: {row}. Error: {e}"
                )
            except requests.exceptions.RequestException as e:
                print(
                    f"🚨 ERROR de API: No se pudo añadir el proyecto ID={row.get('project_id')}. Detalle: {e}"
                )

    print("\n--- SSS: Script de población finalizado. ---")


if __name__ == "__main__":
    main()
