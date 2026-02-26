import os
import requests
import json
import urllib3
from datetime import datetime, timezone
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import insert as pg_insert

# Cargar dependencias de tu proyecto
from main import AuditEventDB, AuditEventType, gitlab_api_request

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

# Configuración BD
DATABASE_URL = f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST', 'postgres_chatbot')}:5432/{os.getenv('POSTGRES_DB')}"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def run_sync_debug(project_id: int, month: int, year: int):
    print(f"\n🚀 INICIANDO SYNC DE WIKI EN MODO DEBUG PARA PROYECTO {project_id} | {month}/{year}")
    db = SessionLocal()

    page = 1
    total_events_scanned = 0
    wiki_events_found = 0
    inserted_count = 0

    try:
        while page <= 10:  # Escanear hasta 1000 eventos para no saturar
            print(f"📡 Descargando página {page} de eventos...")
            resp = gitlab_api_request("get", f"projects/{project_id}/events", params={
                "per_page": 100,
                "page": page
            })

            if not resp or not resp.json():
                print("⚠️ No hay más eventos o error de red.")
                break

            events = resp.json()
            total_events_scanned += len(events)

            for e in events:
                target_type = str(e.get("target_type", "")).lower()
                action = str(e.get("action_name", "")).lower()

                # ¿Es de la wiki?
                if "wiki" not in target_type and "wiki" not in action:
                    continue

                wiki_events_found += 1
                created_at_str = e.get("created_at")
                event_date = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))

                # Imprimir el evento encontrado
                title = (e.get("target_title") or "").lower()
                slug = (e.get("wiki_page", {}).get("slug") or "").lower()
                author_data = e.get("author") or {}
                author = e.get("author_username") or author_data.get("username", "DESCONOCIDO")

                print(f"\n🧐 [EVENTO WIKI ENCONTRADO]")
                print(f"   -> Fecha: {event_date.strftime('%Y-%m-%d')}")
                print(f"   -> Autor: {author}")
                print(f"   -> Título: '{title}'")
                print(f"   -> Slug: '{slug}'")

                # Verificar mes/año
                if event_date.month != month or event_date.year != year:
                    print(f"   ❌ Ignorado: No pertenece a {month}/{year}.")
                    continue

                if author == "DESCONOCIDO":
                    print(f"   ❌ Ignorado: Autor no identificado en el JSON.")
                    continue

                # Heurística
                combined_text = f"{title} {slug}".replace('_', ' ').replace('-', ' ').replace('/', ' ')
                words = combined_text.split()

                is_manual = "manual" in combined_text or "guia" in combined_text or "guía" in combined_text
                is_cu = "caso" in words or "casos" in words or "use case" in combined_text or "cu" in words or ".cu" in combined_text
                if not is_cu:
                    is_cu = any(f"cu{i}" in combined_text for i in range(10))

                if is_manual:
                    evt_type = AuditEventType.MANUAL_CREATED.value if action == "created" else AuditEventType.MANUAL_UPDATED.value
                    print(f"   ✅ Clasificado como: MANUAL ({evt_type})")
                elif is_cu:
                    evt_type = AuditEventType.UC_CREATED.value if action == "created" else AuditEventType.UC_UPDATED.value
                    print(f"   ✅ Clasificado como: CASO DE USO ({evt_type})")
                else:
                    print(f"   🔴 Ignorado: El título/slug no coincide con las reglas de CU o Manual.")
                    continue

                # Intento de Inserción en BD
                ref_id = slug if slug else (title if title else str(e.get("id")))

                print(f"   💾 Intentando guardar en Base de Datos...")
                try:
                    stmt = pg_insert(AuditEventDB).values(
                        project_id=project_id, username=author, event_date=event_date,
                        event_month=month, event_year=year, event_type=evt_type,
                        reference_id=ref_id
                    ).on_conflict_do_update(
                        index_elements=['project_id', 'event_type', 'reference_id', 'username'],
                        set_={'event_date': event_date}
                    )
                    db.execute(stmt)
                    db.commit()
                    inserted_count += 1
                    print("   🟢 GUARDADO EXITOSO.")
                except Exception as db_err:
                    db.rollback()
                    print(f"   🛑 ERROR DE BASE DE DATOS AL GUARDAR: {db_err}")

            page += 1

        print(f"\n📊 --- RESUMEN DE EJECUCIÓN ---")
        print(f"Total Eventos Escaneados: {total_events_scanned}")
        print(f"Total Eventos de Wiki Vistos: {wiki_events_found}")
        print(f"Total Guardados en BD para {month}/{year}: {inserted_count}")

    except Exception as fatal_err:
        print(f"\n💥 ERROR FATAL EN EL SCRIPT: {fatal_err}")
    finally:
        db.close()


if __name__ == "__main__":
    run_sync_debug(project_id=92, month=2, year=2026)  # Cambia el año si estamos en 2024