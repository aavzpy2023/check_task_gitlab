import json
import os

import requests

# --- CONFIGURACIÓN (Secretos y Parámetros) ---
GITLAB_URL = "https://gitlab.azcuba.cu"
PROJECT_ID = "117"
PRIVATE_TOKEN = os.getenv("GITLAB_TOKEN")
LABEL_TO_TRACK = "PARA REVISIÓN"


def get_review_tasks_from_gitlab():
    """
    Etapa de Adquisición de Contexto: Llama a la API de GitLab.
    """
    if not PRIVATE_TOKEN:
        print("Error: La variable de entorno GITLAB_TOKEN no está configurada.")
        return None

    headers = {"PRIVATE-TOKEN": PRIVATE_TOKEN}
    params = {"state": "opened", "labels": LABEL_TO_TRACK}

    api_url = f"{GITLAB_URL}/api/v4/projects/{PROJECT_ID}/issues"

    print(f"Llamando a la API: {api_url}")

    try:
        response = requests.get(api_url, headers=headers, params=params, verify=False)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error al contactar la API de GitLab: {e}")
        return None


def format_tasks_for_llm(tasks_json):
    """
    Etapa de Formateado de Contexto: Procesa el JSON a un formato de texto simple.
    """
    if not tasks_json:
        return "No se encontraron tareas en revisión."

    formatted_text = ""
    for task in tasks_json:
        # --- MODIFICACIÓN APLICADA AQUÍ ---
        title = task.get("title", "N/A")
        description = task.get(
            "description", "No hay descripción."
        )  # Se extrae la descripción.
        author = task.get("author", {}).get("name", "N/A")
        url = task.get("web_url", "N/A")
        # Se añade la descripción al texto formateado.
        formatted_text += f"- Título: {title}\n  Descripción: {description}\n  Autor: {author}\n  URL: {url}\n\n"

    return formatted_text.strip()


def build_prompt_with_context(context, user_question):
    """
    Etapa de Inyección de Contexto: Ensambla el prompt final para el LLM.
    """
    system_prompt = "Eres un asistente de DevOps. Tu tarea es analizar el contexto proporcionado dentro de la etiqueta <gitlab_tasks> y responder a la pregunta del usuario."

    user_prompt = f"""
<gitlab_tasks>
{context}
</gitlab_tasks>

Pregunta: {user_question}
"""
    print("--- PROMPT FINAL PARA EL LLM ---")
    print(f"System Prompt: {system_prompt}")
    print(f"User Prompt: {user_prompt}")
    return system_prompt, user_prompt


# --- Orquestación Principal ---
if __name__ == "__main__":
    tasks_data = get_review_tasks_from_gitlab()

    if tasks_data is not None:
        formatted_context = format_tasks_for_llm(tasks_data)
        user_question = (
            "¿Puedes darme un resumen de las tareas que están en revisión ahora mismo?"
        )
        system_prompt, user_prompt = build_prompt_with_context(
            formatted_context, user_question
        )

        print("\n--- RESPUESTA SIMULADA DEL LLM ---")
        if "No se encontraron tareas" in formatted_context:
            print("Actualmente no hay ninguna tarea en revisión.")
        else:
            print(
                f"Claro, aquí tienes un resumen de las {len(tasks_data)} tareas en revisión:"
            )
            print(formatted_context)
