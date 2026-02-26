import os
from pathlib import Path
import requests
import json
import urllib3
from dotenv import load_dotenv

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- CORRECCIÓN CRÍTICA ---
# Forzar la carga del .env que está en la RAÍZ del proyecto (un nivel arriba de backend)
base_dir = Path(__file__).resolve().parent.parent
env_path = base_dir / '.env'

print(f"Intentando cargar .env desde: {env_path}")
load_dotenv(dotenv_path=env_path)

GITLAB_URL = os.getenv("GITLAB_URL")
GITLAB_TOKEN = os.getenv("GITLAB_TOKEN")
USERNAME = "alianay.marcilla"


def run_diagnostic():
    if not GITLAB_URL or not GITLAB_TOKEN:
        print("❌ ERROR FATAL: Las variables siguen vacías.")
        print("Asegúrate de que el archivo .env en la raíz contenga GITLAB_URL y GITLAB_TOKEN")
        return

    headers = {"PRIVATE-TOKEN": GITLAB_TOKEN}

    print(f"🔍 Buscando ID de usuario para: {USERNAME}...")
    user_resp = requests.get(f"{GITLAB_URL}/api/v4/users?username={USERNAME}", headers=headers, verify=False)

    if user_resp.status_code != 200 or not user_resp.json():
        print(f"❌ ERROR: No se pudo encontrar el usuario {USERNAME}. Código: {user_resp.status_code}")
        return

    user_id = user_resp.json()[0]["id"]
    print(f"✅ Usuario encontrado. ID: {user_id}")

    print("📡 Extrayendo últimos 100 eventos globales del usuario...")
    events_resp = requests.get(
        f"{GITLAB_URL}/api/v4/users/{user_id}/events?per_page=100",
        headers=headers,
        verify=False
    )

    if events_resp.status_code != 200:
        print(f"❌ ERROR al extraer eventos: {events_resp.status_code}")
        return

    all_events = events_resp.json()
    print(f"📊 Total de eventos extraídos en esta página: {len(all_events)}")

    # Filtrar heurísticamente todo lo que huela a Wiki
    wiki_events = []
    for e in all_events:
        target_type = str(e.get("target_type", "")).lower()
        action_name = str(e.get("action_name", "")).lower()

        if "wiki" in target_type or "wiki" in action_name:
            wiki_events.append(e)

    if not wiki_events:
        print("⚠️ No se encontró NINGÚN evento relacionado con wikis en los últimos 100 eventos.")
    else:
        print(f"\n🎯 ¡ÉXITO! Se encontraron {len(wiki_events)} eventos de Wiki.")
        print("\n---[ INICIO RAW JSON DATA (Primeros 3 eventos) ] ---")
        print(json.dumps(wiki_events[:3], indent=2, ensure_ascii=False))
        print("--- [ FIN RAW JSON DATA ] ---\n")

        print("🧐 REVISIÓN DE FILTROS ACTUALES EN EL BACKEND:")
        for w in wiki_events:
            title = str(w.get("target_title", "")).lower()
            norm_title = title.replace('_', ' ').replace('-', ' ')
            matched = "🔴 IGNORADO (Título no coincide con reglas de CU/Manuales)"

            if "manual" in norm_title or "guia" in norm_title or "guía" in norm_title:
                matched = "🟢 RECONOCIDO COMO: MANUAL"
            elif "caso" in norm_title or "cu" in norm_title.split() or "use case" in norm_title:
                matched = "🟢 RECONOCIDO COMO: CASO DE USO"

            print(
                f" - Título Original: '{w.get('target_title')}' | Target Type: '{w.get('target_type')}' | Match: {matched}")


if __name__ == "__main__":
    run_diagnostic()