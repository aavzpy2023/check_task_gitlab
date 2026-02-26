import os
import requests
import json
import urllib3
from dotenv import load_dotenv

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

GITLAB_URL = os.getenv("GITLAB_URL")
PRIVATE_TOKEN = os.getenv("GITLAB_TOKEN")
TARGET_USERNAME = "alianay.marcilla"
PROJECT_ID = 92

if not GITLAB_URL or not PRIVATE_TOKEN:
    print("❌ ERROR: Faltan variables de entorno.")
    exit(1)


def audit_user_events():
    headers = {"PRIVATE-TOKEN": PRIVATE_TOKEN}
    print(f"🔍 1. Buscando ID interno del usuario: {TARGET_USERNAME}...")

    # 1. Obtener ID del usuario
    u_resp = requests.get(f"{GITLAB_URL}/api/v4/users?username={TARGET_USERNAME}", headers=headers, verify=False)
    users = u_resp.json()
    if not users:
        print("❌ Usuario no encontrado en GitLab.")
        return

    user_id = users[0]["id"]
    print(f"✅ Usuario encontrado. ID: {user_id}")

    # 2. Descargar los últimos eventos DEL USUARIO
    print(f"\n📡 2. Descargando sus últimos 100 eventos globales...")
    e_resp = requests.get(
        f"{GITLAB_URL}/api/v4/users/{user_id}/events?project_id={PROJECT_ID}&per_page=100",
        headers=headers, verify=False
    )
    events = e_resp.json()

    print(f"📊 Total de eventos analizados: {len(events)}")

    wiki_count = 0
    push_count = 0

    for e in events:
        tt = str(e.get("target_type", "")).lower()
        an = str(e.get("action_name", "")).lower()

        # ¿Hizo un Git Push directo?
        if "pushed" in an:
            push_count += 1

        # ¿Es un evento de Wiki?
        if "wiki" in tt or "wiki" in an:
            wiki_count += 1
            print(f"\n🎯 [EVENTO WIKI DETECTADO]")
            print(f"   -> Fecha Real: {e.get('created_at')}")
            print(f"   -> Acción: {an}")
            print(f"   -> Título: {e.get('target_title')}")
            wiki_page_data = e.get("wiki_page") or {}
            slug = wiki_page_data.get("slug", "")
            print(f"   -> Slug: {slug}")

            # Prueba de Heurística de CU
            combined = f"{e.get('target_title', '')} {slug}".replace('_', ' ').replace('-', ' ').replace('/',
                                                                                                         ' ').lower()
            words = combined.split()
            is_cu = "caso" in words or "casos" in words or "cu" in words or ".cu" in combined
            if not is_cu:
                is_cu = any(f"cu{i}" in combined for i in range(10))

            print(f"   -> ¿Lo reconoce como CU?: {'✅ SÍ' if is_cu else '🔴 NO (Fallo de heurística)'}")

    print(f"\n🏁 --- RESUMEN ---")
    print(f"Eventos de Wiki encontrados: {wiki_count}")
    print(f"Eventos de Push (Subida masiva por terminal) encontrados: {push_count}")

    if wiki_count == 0:
        print("\n⚠️ CONCLUSIÓN: Alianay no ha generado eventos web de Wiki en sus últimas interacciones.")
        print("Si ves sus documentos en GitLab, es probable que:")
        print("  A) Los haya creado hace mucho tiempo (antes de sus últimos 100 eventos).")
        print("  B) Los subió usando 'git clone' y 'git push' a la wiki, lo cual burla la API de /events de Wiki.")


if __name__ == "__main__":
    audit_user_events()