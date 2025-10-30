# frontend/pages/2_Documentation_Portal.py
import streamlit as st
import requests

# --- Configuración ---
API_BASE_URL = "http://backend:8001"
st.set_page_config(page_title="Portal de Documentación", layout="wide")

st.title("📖 Portal de Documentación")
st.divider()

# --- Funciones de la API ---
@st.cache_data(ttl=600) # Cache para 10 minutos
def get_wiki_projects():
    try:
        response = requests.get(f"{API_BASE_URL}/wiki/projects")
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        return None

@st.cache_data(ttl=300) # Cache para 5 minutos
def get_wiki_pages(project_id):
    try:
        response = requests.get(f"{API_BASE_URL}/wiki/projects/{project_id}/pages")
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        return []

@st.cache_data(ttl=60) # Cache para 1 minuto
def get_page_content(project_id, slug):
    try:
        response = requests.get(f"{API_BASE_URL}/wiki/projects/{project_id}/pages/{slug}")
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        return {"content": "Error al cargar el contenido.", "title": "Error"}

# --- Interfaz de Usuario ---
projects = get_wiki_projects()

if not projects:
    st.error("No se pudieron cargar los proyectos desde el backend.")
else:
    project_names = {p['name']: p['id'] for p in projects}
    selected_project_name = st.selectbox("Seleccione un Proyecto:", options=project_names.keys())
    
    if selected_project_name:
        project_id = project_names[selected_project_name]
        
        with st.spinner(f"Cargando páginas de la wiki para {selected_project_name}..."):
            pages = get_wiki_pages(project_id)

        if not pages:
            st.warning("Este proyecto no tiene páginas de wiki o no se pudieron cargar.")
        else:
            left_col, right_col = st.columns([1, 3])
            
            with left_col:
                st.subheader("Páginas")
                page_slugs = {p['title']: p['slug'] for p in pages}
                
                # Usar st.session_state para mantener la página seleccionada
                if 'selected_page_slug' not in st.session_state:
                    st.session_state.selected_page_slug = pages[0]['slug']

                for title, slug in page_slugs.items():
                    if st.button(title, key=slug, use_container_width=True):
                        st.session_state.selected_page_slug = slug
                        # No es necesario st.rerun() si la lógica de renderizado está debajo
            
            with right_col:
                if 'selected_page_slug' in st.session_state:
                    slug = st.session_state.selected_page_slug
                    with st.spinner(f"Cargando contenido de '{slug}'..."):
                        content_data = get_page_content(project_id, slug)

                    st.header(content_data['title'])
                    
                    # Enlace de descarga de PDF
                    st.download_button(
                        label="⬇️ Descargar como PDF",
                        data=requests.get(f"{API_BASE_URL}/wiki/projects/{project_id}/generate_pdf/{slug}").content,
                        file_name=f"{slug}.pdf",
                        mime="application/pdf",
                    )
                    
                    st.divider()
                    st.markdown(content_data['content'], unsafe_allow_html=True)