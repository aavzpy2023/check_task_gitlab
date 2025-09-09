# app.py - Frontend Streamlit (Diseño Final v14 - Ajuste Fino)
import requests
import streamlit as st
import pandas as pd
import datetime

# --- Configuración ---
API_BASE_URL = "http://backend:8001"
st.set_page_config(page_title="Dashboard de Tareas", layout="wide", initial_sidebar_state="collapsed")

# --- Estilos CSS Personalizados ---
st.markdown("""
<style>
    /* Ocultar elementos de Streamlit no deseados */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* Contenedor principal */
    .main .block-container {
        padding-top: 1rem; padding-bottom: 1rem;
        padding-left: 1rem; padding-right: 1rem;
    }

    /* Menú lateral Fijo (Sticky) */
    div[data-testid="stHorizontalBlock"] > div:nth-child(1) > div {
        position: sticky;
        top: 2.5rem;
        background-color: #0E1117;
        z-index: 100;
    }

    /* Estilo de los botones del menú */
    .stButton button {
        background-color: transparent; border: 1px solid #333; text-align: left;
        font-weight: normal; padding: 0.5rem 0.75rem; border-radius: 0.5rem;
        transition: background-color 0.2s ease-in-out; margin-bottom: 0.5rem;
        display: flex; justify-content: space-between;
    }
    .stButton button:hover {background-color: #2a2a2a; border-color: #444;}
    .stButton button:focus {box-shadow: none !important;}
    .stButton button[kind="primary"] {
        background-color: #27ae60; border-color: #27ae60;
        font-weight: bold; color: white;
    }

    /* Título de la tarea (h5) */
    div[data-testid="stVerticalBlock"] h5 {
        margin: 0;
        padding-top: 0.1rem; /* Alineación vertical fina */
        font-weight: 500;
        font-size: 1.1rem; /* Tamaño de fuente reducido */
        color: #FAFAFA;
    }

    /* Estilo para que el expansor no tenga su propio recuadro */
    [data-testid="stExpander"] {
        border: none !important;
        background-color: transparent !important;
        padding: 0 !important;
        margin: 0 !important;
    }
    [data-testid="stExpander"] summary {
        padding-left: 0;
        font-size: 0.9em;
        color: #aaa;
    }

</style>
""", unsafe_allow_html=True)

# --- Funciones ---
@st.cache_data(ttl=300)
def get_projects_data():
    try:
        response = requests.get(f"{API_BASE_URL}/projects/")
        response.raise_for_status()
        projects = response.json()
        if not projects: return None
        return pd.DataFrame(projects)
    except requests.exceptions.RequestException:
        return None

def show_task_details(column, project_id, project_name):
    column.header(f"Detalles para: {project_name}")
    with st.spinner("Cargando tareas..."):
        try:
            response = requests.get(f"{API_BASE_URL}/projects/{project_id}/review_tasks/")
            response.raise_for_status()
            tasks = response.json()
            if not tasks:
                column.success("✅ ¡Felicidades! No hay tareas en revisión para este proyecto.")
                return

            for task in tasks:
                with st.container(border=True):
                    # --- DISEÑO FINAL DE TARJETA CON AJUSTE FINO ---
                    c1, c2 = st.columns([1, 20]) # Dar más espacio al título

                    with c1:
                        st.markdown(f"<a href='{task['url']}' target='_blank' style='white-space: nowrap;'>[LINK]</a>", unsafe_allow_html=True)

                    with c2:
                        # Usar markdown con h5 para un tamaño de fuente menor
                        st.markdown(f"<h5>{task['title']}</h5>", unsafe_allow_html=True)

                    with st.expander("Ver Descripción y Detalles"):
                        st.markdown(task["description"] if task["description"] else "_Sin descripción._")
                        st.markdown("---")
                        st.caption(f"✍️ **Autor:** {task['author']}")
                        if task.get('assignee'):
                            st.caption(f"👤 **Asignado a:** {task['assignee']}")
                        if task.get('milestone'):
                            st.caption(f"🎯 **Milestone:** {task['milestone']}")

        except requests.exceptions.RequestException:
            column.error(f"❌ No se pudieron obtener las tareas para el proyecto {project_name}.")

# --- Flujo Principal de la Interfaz ---
st.title("📈 Dashboard de Tareas en Revisión")
st.divider()
projects_df = get_projects_data()

if projects_df is None:
    st.error("❌ No se pudo conectar con el backend o no hay proyectos configurados.")
else:
    projects_df.sort_values(by='review_task_count', ascending=False, inplace=True)
    active_projects_df = projects_df[projects_df['review_task_count'] > 0].copy()

    left_col, right_col = st.columns([1, 3])

    if "selected_project_id" not in st.session_state and not active_projects_df.empty:
        default_project = active_projects_df.iloc[0]
        st.session_state['selected_project_id'] = default_project['id']
        st.session_state['selected_project_name'] = default_project['name']

    with left_col:
        tod = datetime.datetime.now()
        st.subheader("Proyectos Activos")
        # st.subheader(str(tod.day()) + "/" + str(tod.month()) + "/" + str(tod.year()))
        st.divider()

        for index, row in active_projects_df.iterrows():
            project_id, project_name, task_count = row['id'], row['name'], row['review_task_count']
            is_selected = (st.session_state.get("selected_project_id") == project_id)
            button_type = "primary" if is_selected else "secondary"

            button_label = f"{project_name} ({task_count})"
            if st.button(button_label, key=f"btn_{project_id}", use_container_width=True, type=button_type):
                st.session_state['selected_project_id'] = project_id
                st.session_state['selected_project_name'] = project_name
                st.rerun()

    with right_col:
        if not active_projects_df.empty and "selected_project_id" in st.session_state:
            show_task_details(
                right_col,
                st.session_state["selected_project_id"],
                st.session_state["selected_project_name"],
            )
        elif active_projects_df.empty:
             right_col.success("🎉 ¡Excelente trabajo! No hay tareas en revisión en ningún proyecto.")
        else:
            right_col.info("⬅️ Selecciona un proyecto del menú para ver los detalles de sus tareas.")
