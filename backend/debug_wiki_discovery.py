import os
import requests
import json
import urllib3
from datetime import datetime
from dotenv import load_dotenv

# Configuración básica
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

GITLAB_URL = os.getenv("GITLAB_URL")
PRIVATE_TOKEN = os.getenv("GITLAB_TOKEN")

if not GITLAB_URL or not PRIVATE_TOKEN:
    print("❌ ERROR: No se cargaron las variables de entorno GITLAB_URL o GITLAB_TOKEN.")
    exit(1)


def analyze_project_events(project_id):
    print(f"\n🔬 --- DIAGNÓSTICO PROFUNDO PARA PROYECTO ID: {project_id} ---")
    headers = {"PRIVATE-TOKEN": PRIVATE_TOKEN}

    # 1. Estrategia "Pesca de Arrastre": Traer TODO sin filtrar por tipo
    # Esto elimina la posibilidad de que el filtro 'wiki_page' esté rompiendo la query.
    print("📡 1. Descargando últimos 100 eventos SIN filtros de tipo...")
    url = f"{GITLAB_URL}/api/v4/projects/{project_id}/events"
    params = {"per_page": 100}

    try:
        resp = requests.get(url, headers=headers, params=params, verify=False, timeout=10)
        resp.raise_for_status()
        events = resp.json()
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        return

    print(f"📊 Total eventos recuperados: {len(events)}")

    wiki_candidates = []

    # 2. Búsqueda manual en la respuesta
    for e in events:
        # Normalizamos para comparar
        t_type = str(e.get("target_type", "")).lower()
        action = str(e.get("action_name", "")).lower()

        # ¿Huele a Wiki?
        if "wiki" in t_type or "wiki" in action:
            wiki_candidates.append(e)

    if not wiki_candidates:
        print("⚠️  RESULTADO: No se encontró NINGÚN evento de Wiki en los últimos 100 movimientos.")
        print("   -> Posible causa: No ha habido ediciones recientes o el Project ID es incorrecto.")
        return

    print(f"✅  ÉXITO: Se encontraron {len(wiki_candidates)} eventos relacionados con Wiki.")

    # 3. Análisis Forense del Primer Candidato
    example = wiki_candidates[0]
    print("\n🧐 --- ANÁLISIS DEL PRIMER EVENTO ENCONTRADO ---")
    print(f"🆔  Event ID: {example.get('id')}")
    print(f"🏷️  Target Type (Raw): '{example.get('target_type')}'  <-- ESTO ES LO QUE IMPORTA")
    print(f"⚡  Action Name: '{example.get('action_name')}'")
    print(f"📝  Target Title: '{example.get('target_title')}'")

    # 4. Validación de Heurísticas del Backend
    title = str(example.get("target_title", "")).lower()
    norm_title = title.replace('_', ' ').replace('-', ' ')

    print("\n🕵️ --- SIMULACIÓN DE LÓGICA DEL BACKEND (main.py) ---")

    # Check 1: Target Type
    # En main.py se valida: if e.get("target_type") != "WikiPage":
    backend_type_check = (example.get("target_type") == "WikiPage")
    print(
        f"1. Validación de Tipo (Debe ser 'WikiPage'): {'✅ PASA' if backend_type_check else '❌ FALLA (El backend ignorará esto)'}")

    # Check 2: Heurística de Título
    is_manual = "manual" in norm_title or "guia" in norm_title or "guía" in norm_title
    is_cu = "caso" in norm_title or "use case" in norm_title or "cu" in norm_title.split() or ".cu" in title
    if not is_cu:
        is_cu = any(f"cu{i}" in title for i in range(10))

    if is_manual:
        print(f"2. Clasificación: 🟢 DETECTADO COMO MANUAL")
    elif is_cu:
        print(f"2. Clasificación: 🟢 DETECTADO COMO CASO DE USO")
    else:
        print(f"2. Clasificación: 🔴 NO RECONOCIDO (Se ignorará en métricas)")
        print(f"   -> Título normalizado analizado: '{norm_title}'")

    print("\n💾 --- DUMP RAW JSON (Para referencia) ---")
    print(json.dumps(example, indent=2))


if __name__ == "__main__":
    # Preguntar ID interactivamente
    pid = input("Ingrese el ID del Proyecto a diagnosticar: ")
    if pid.isdigit():
        analyze_project_events(int(pid))
    else:
        print("ID inválido.")