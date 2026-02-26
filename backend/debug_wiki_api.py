import os
import requests
import json
import urllib3
import urllib.parse
from dotenv import load_dotenv

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Cargar variables
load_dotenv()
GITLAB_URL = os.getenv("GITLAB_URL")
PRIVATE_TOKEN = os.getenv("GITLAB_TOKEN")

if not GITLAB_URL or not PRIVATE_TOKEN:
    print("❌ ERROR: GITLAB_URL o GITLAB_TOKEN no configurados.")
    exit(1)


def explore_wiki_api(project_id):
    headers = {"PRIVATE-TOKEN": PRIVATE_TOKEN}
    print(f"\n🔍 --- DIAGNÓSTICO DE API DE WIKI | PROYECTO ID: {project_id} ---")

    # 1. TEST: Endpoint de Lista de Wikis
    list_url = f"{GITLAB_URL}/api/v4/projects/{project_id}/wikis"
    print(f"\n📡 GET {list_url}")

    try:
        resp_list = requests.get(list_url, headers=headers, verify=False, timeout=10)
        resp_list.raise_for_status()
        pages = resp_list.json()
    except Exception as e:
        print(f"❌ Error al consultar la lista de wikis: {e}")
        return

    print(f"✅ Total de páginas encontradas: {len(pages)}")

    if not pages:
        print("⚠️ No hay páginas en la wiki de este proyecto.")
        return

    # Buscar una página que parezca CU o Manual para el test
    test_page = None
    for p in pages:
        slug_lower = p.get("slug", "").lower()
        if "cu" in slug_lower or "manual" in slug_lower:
            test_page = p
            break

    if not test_page:
        test_page = pages[0]  # Fallback a la primera

    print("\n📦 --- JSON RAW: ELEMENTO DE LA LISTA (/wikis) ---")
    print(json.dumps(test_page, indent=2, ensure_ascii=False))

    # 2. TEST: Endpoint de Detalle de Wiki
    slug = test_page.get("slug")
    safe_slug = urllib.parse.quote(slug, safe='')
    detail_url = f"{GITLAB_URL}/api/v4/projects/{project_id}/wikis/{safe_slug}"

    print(f"\n📡 GET {detail_url}")

    try:
        resp_detail = requests.get(detail_url, headers=headers, verify=False, timeout=10)
        resp_detail.raise_for_status()
        detail = resp_detail.json()
    except Exception as e:
        print(f"❌ Error al consultar el detalle de la wiki: {e}")
        return

    # Truncamos el contenido para no inundar la consola
    if "content" in detail and len(detail["content"]) > 200:
        detail["content"] = detail["content"][:200] + "... [CONTENIDO TRUNCADO]"

    print("\n📦 --- JSON RAW: DETALLE DE LA PÁGINA (/wikis/{slug}) ---")
    print(json.dumps(detail, indent=2, ensure_ascii=False))

    # 3. ANÁLISIS DE CAMPOS CLAVE
    print("\n🧐 --- ANÁLISIS DE DISPONIBILIDAD DE DATOS ---")
    author_obj = detail.get("author", detail.get("author_username", "No encontrado"))
    print(f"👤 Autor encontrado en el detalle: {author_obj}")

    created_at = detail.get("created_at", test_page.get("created_at", "No encontrado"))
    updated_at = detail.get("updated_at", test_page.get("updated_at", "No encontrado"))
    print(f"📅 Fecha de Creación: {created_at}")
    print(f"📅 Fecha de Actualización: {updated_at}")

    if str(author_obj) == "No encontrado":
        print("\n🚨 ¡ALERTA! La API de Wiki no está devolviendo el autor.")
        print("Esto explica por qué la tabla sale en cero (sin autor, no se puede asignar a un usuario en la tabla).")


if __name__ == "__main__":
    pid = input("Ingrese el ID del Proyecto a diagnosticar: ")
    if pid.isdigit():
        explore_wiki_api(int(pid))
    else:
        print("ID inválido.")