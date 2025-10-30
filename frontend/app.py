# app.py - Frontend Streamlit (Diseño Final v14 - Ajuste Fino)
import datetime

import pandas as pd
import requests
import streamlit as st

# --- Configuration ---
API_BASE_URL = "http://backend:8001"
st.set_page_config(
    page_title="Task Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="auto",
)


# --- Functions ---
def load_css(file_name: str):
    """
    Loads a local CSS file into the Streamlit application.

    Args:
        file_name (str): The path to the CSS file.
    """
    with open(file_name) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


# Load custom CSS
load_css("static/style.css")


@st.cache_data(ttl=300)
def get_projects_data():
    try:
        response = requests.get(f"{API_BASE_URL}/projects/")
        response.raise_for_status()
        projects = response.json()
        if not projects:
            return None
        return pd.DataFrame(projects)
    except requests.exceptions.RequestException:
        return None


def show_task_details(column, project_id, project_name):
    column.header(f"Detalles para: {project_name}")
    with st.spinner("Cargando tareas..."):
        try:
            response = requests.get(
                f"{API_BASE_URL}/projects/{project_id}/review_tasks/"
            )
            response.raise_for_status()
            tasks = response.json()
            if not tasks:
                column.success(
                    "✅ Congratulations! There is not task to check in this project"
                )
                return

            for task in tasks:
                with st.container(border=True):
                    c1, c2 = st.columns([1, 20])

                    with c1:
                        st.markdown(
                            f"<a href='{task['url']}' target='_blank' style='white-space: nowrap;'>[LINK]</a>",
                            unsafe_allow_html=True,
                        )

                    with c2:
                        # Usar markdown con h5 para un tamaño de fuente menor
                        st.markdown(f"<h5>{task['title']}</h5>", unsafe_allow_html=True)

                    with st.expander("Ver Descripción y Detalles"):
                        st.markdown(
                            task["description"]
                            if task["description"]
                            else "_Sin descripción._"
                        )
                        st.markdown("---")
                        st.caption(f"✍️ **Autor:** {task['author']}")
                        if task.get("assignee"):
                            st.caption(f"👤 **Asignado a:** {task['assignee']}")
                        if task.get("milestone"):
                            st.caption(f"🎯 **Milestone:** {task['milestone']}")

        except requests.exceptions.RequestException:
            column.error(f"❌ None task could be taken {project_name}.")


# --- Main flow of the app ---
st.title("📈 Dashboard of Task to check")
st.divider()
projects_df = get_projects_data()

if projects_df is None:
    st.error(
        "❌ There is not project configured and the connection with backend could not be established"
    )
else:
    projects_df.sort_values(by="review_task_count", ascending=False, inplace=True)
    active_projects_df = projects_df[projects_df["review_task_count"] > 0].copy()

    left_col, right_col = st.columns([1, 3])

    if "selected_project_id" not in st.session_state and not active_projects_df.empty:
        default_project = active_projects_df.iloc[0]
        st.session_state["selected_project_id"] = default_project["id"]
        st.session_state["selected_project_name"] = default_project["name"]

    with left_col:
        tod = datetime.datetime.now()
        st.subheader("Proyectos Activos")
        # st.subheader(str(tod.day()) + "/" + str(tod.month()) + "/" + str(tod.year()))
        st.divider()

        for index, row in active_projects_df.iterrows():
            project_id, project_name, task_count = (
                row["id"],
                row["name"],
                row["review_task_count"],
            )
            is_selected = st.session_state.get("selected_project_id") == project_id
            button_type = "primary" if is_selected else "secondary"

            button_label = f"{project_name} ({task_count})"
            if st.button(
                button_label,
                key=f"btn_{project_id}",
                use_container_width=True,
                type=button_type,
            ):
                st.session_state["selected_project_id"] = project_id
                st.session_state["selected_project_name"] = project_name
                st.rerun()

    with right_col:
        if not active_projects_df.empty and "selected_project_id" in st.session_state:
            show_task_details(
                right_col,
                st.session_state["selected_project_id"],
                st.session_state["selected_project_name"],
            )
        elif active_projects_df.empty:
            right_col.success(
                "🎉 ¡Excelente trabajo! No hay tareas en revisión en ningún proyecto."
            )
        else:
            right_col.info(
                "⬅️ Selecciona un proyecto del menú para ver los detalles de sus tareas."
            )
