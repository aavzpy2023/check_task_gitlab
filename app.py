# app.py - Frontend Streamlit
import requests
import streamlit as st

# --- Configuración ---
API_BASE_URL = "http://127.0.0.1:8008"  # URL donde corre nuestro backend FastAPI

st.set_page_config(page_title="Monitor de Tareas GitLab", layout="wide")
st.title("📊 Monitor de Tareas en Revisión de GitLab")

# --- Lógica de la Aplicación ---


def show_project_list():
    """Muestra la lista de proyectos y sus contadores."""
    st.subheader("Selecciona un Proyecto")
    try:
        response = requests.get(f"{API_BASE_URL}/projects/")
        response.raise_for_status()
        projects = response.json()

        if not projects:
            st.warning("No hay proyectos configurados en el backend.")
            return

        cols = st.columns(3)  # Organizar proyectos en 3 columnas
        for i, project in enumerate(projects):
            col = cols[i % 3]
            # Usamos un botón para cada proyecto. Al hacer clic, guardamos el ID en el estado de la sesión.
            if col.button(
                f"{project['name']} ({project['review_task_count']} en revisión)",
                key=project["id"],
                use_container_width=True,
            ):
                st.session_state["selected_project_id"] = project["id"]
                st.session_state["selected_project_name"] = project["name"]
                st.rerun()  # Volver a ejecutar el script para mostrar la vista de detalles

    except requests.exceptions.RequestException:
        st.error(
            "❌ No se pudo conectar con el backend. Asegúrate de que el servidor FastAPI esté corriendo."
        )


def show_task_details(project_id, project_name):
    """Muestra los detalles de las tareas para un proyecto seleccionado."""
    st.subheader(f"Tareas en Revisión para: {project_name}")

    if st.button("⬅️ Volver a la lista de proyectos"):
        # Limpiar el estado de la sesión para volver a la vista principal
        del st.session_state["selected_project_id"]
        del st.session_state["selected_project_name"]
        st.rerun()

    try:
        response = requests.get(f"{API_BASE_URL}/projects/{project_id}/review_tasks/")
        response.raise_for_status()
        tasks = response.json()

        if not tasks:
            st.info("¡Felicidades! No hay tareas en revisión para este proyecto.")
            return

        for task in tasks:
            with st.container(border=True):
                st.markdown(f"#### {task['title']}")
                st.caption(f"Autor: {task['author']}")

                with st.expander("Ver Descripción"):
                    # Usamos st.markdown para renderizar el formato de GitLab (negritas, etc.)
                    st.markdown(
                        task["description"]
                        if task["description"]
                        else "_Sin descripción._"
                    )

                # Crear un enlace clickeable a la tarea en GitLab
                st.link_button("🔗 Ir a la Tarea en GitLab", url=task["url"])

    except requests.exceptions.RequestException:
        st.error(
            f"❌ No se pudieron obtener las tareas para el proyecto {project_name}."
        )


# --- Flujo Principal de la Interfaz ---
# Usamos el estado de la sesión para decidir qué vista mostrar
if "selected_project_id" in st.session_state:
    show_task_details(
        st.session_state["selected_project_id"],
        st.session_state["selected_project_name"],
    )
else:
    show_project_list()
