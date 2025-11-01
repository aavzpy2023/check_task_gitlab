<<<<<<< HEAD
from urllib.parse import quote

import requests
import streamlit as st

# --- Configuración ---
API_BASE_URL = "http://backend:8001"
st.set_page_config(page_title="Portal de Documentación", page_icon="📖", layout="wide")
# El tema se configura globalmente

# --- CSS para estilizar la navegación ---
st.markdown(
    """
<style>
    /* Estilo para los contenedores de los botones para poder ocultarlos */
    .stButton > button {
        display: none;
    }
    .nav-link {
        cursor: pointer; display: block; padding: 0.3em 0.5em; border-radius: 0.25rem;
        transition: background-color 0.2s ease-in-out; color: #31333F; text-decoration: none;
    }
    .nav-link:hover {
        background-color: #F0F2F6;
    }
    .nav-link-selected {
        background-color: #0068C9 !important; color: white !important; font-weight: bold;
    }
    [data-testid="stExpander"] div[role="button"] + div {
        padding-left: 20px;
    }
</style>
""",
    unsafe_allow_html=True,
)


# --- Funciones de la API (sin cambios) ---
@st.cache_data(ttl=600)
=======
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
>>>>>>> 934b995f50798a832f6fad9e0f26cfd2865870ba
def get_wiki_projects():
    try:
        response = requests.get(f"{API_BASE_URL}/wiki/projects")
        response.raise_for_status()
        return response.json()
<<<<<<< HEAD
    except:
        return None


@st.cache_data(ttl=300)
def get_wiki_pages_tree(project_id):
    try:
        response = requests.get(f"{API_BASE_URL}/wiki/projects/{project_id}/pages/tree")
        response.raise_for_status()
        return response.json()
    except:
        return []


@st.cache_data(ttl=60)
def get_page_content(project_id, slug):
    try:
        encoded_slug = quote(slug, safe="")
        response = requests.get(
            f"{API_BASE_URL}/wiki/projects/{project_id}/pages/{encoded_slug}"
        )
        response.raise_for_status()
        return response.json()
    except:
        return {"content": "Error al cargar el contenido.", "title": "Error"}


@st.cache_data(ttl=60)
def get_pdf_data(project_id, slug):
    """Función dedicada para obtener los bytes del PDF, con cache."""
    try:
        encoded_slug = quote(slug, safe="")
        pdf_url = (
            f"{API_BASE_URL}/wiki/projects/{project_id}/generate_pdf/{encoded_slug}"
        )
        response = requests.get(pdf_url, verify=False)
        response.raise_for_status()
        return response.content
    except Exception:
        return None


# --- Lógica de la UI (Refactorizada) ---
def update_selected_page(slug):
    """Callback para actualizar el estado de la sesión."""
    st.session_state.selected_page_slug = slug


def render_tree_navigation(nodes, selected_slug):
    """Renderiza la navegación de árbol usando st.expander y st.button para máxima fiabilidad."""
    for node in nodes:
        if node["type"] == "folder":
            with st.expander(f"📁 {node['title']}", expanded=True):
                render_tree_navigation(node["children"], selected_slug)
        else:  # 'file'
            is_selected = node["slug"] == selected_slug
            css_class = "nav-link-selected" if is_selected else "nav-link"
            st.markdown(
                f'<div class="{css_class}" onclick="document.getElementById(\'btn-{node["slug"]}\').click()">{node["title"]}</div>',
                unsafe_allow_html=True,
            )
            st.button(
                "select",
                key=f"btn-{node['slug']}",
                on_click=update_selected_page,
                args=(node["slug"],),
            )


def find_first_file(nodes):
    """Encuentra recursivamente el slug del primer archivo en el árbol."""
    for node in nodes:
        if node["type"] == "file":
            return node["slug"]
        if node["type"] == "folder":
            first_in_folder = find_first_file(node["children"])
            if first_in_folder:
                return first_in_folder
    return None


# --- Flujo Principal de la Página ---
st.title("📖 Portal de Documentación")
st.divider()

projects = get_wiki_projects()

if not projects:
    st.error("No se encontraron proyectos con Wiki activa.")
else:
    project_names = {p["name"]: p["id"] for p in projects}

    # Manejo del estado de la sesión
    if "selected_project_id" not in st.session_state:
        st.session_state.selected_project_id = list(project_names.values())[0]

    def on_project_change():
        st.session_state.selected_project_id = project_names[
            st.session_state.project_selector
        ]
        # Borramos el slug seleccionado para que la nueva lógica lo determine
        if "selected_page_slug" in st.session_state:
            del st.session_state["selected_page_slug"]

    project_ids = list(project_names.values())
    try:
        current_project_index = project_ids.index(st.session_state.selected_project_id)
    except ValueError:
        current_project_index = 0

    st.selectbox(
        "Seleccione un Proyecto:",
        options=project_names.keys(),
        key="project_selector",
        index=current_project_index,
        on_change=on_project_change,
    )

    project_id = st.session_state.selected_project_id
    pages_tree = get_wiki_pages_tree(project_id)

    if not pages_tree:
        st.warning("Esta wiki está vacía o no se pudieron cargar sus páginas.")
    else:
        left_col, right_col = st.columns([1, 3])

        # --- SSS: Lógica de Selección Inteligente de Página por Defecto ---
        if "selected_page_slug" not in st.session_state:
            home_node = next(
                (
                    node
                    for node in pages_tree
                    if node["type"] == "file" and node["slug"] == "home"
                ),
                None,
            )
            if home_node:
                st.session_state.selected_page_slug = "home"
            else:
                st.session_state.selected_page_slug = find_first_file(pages_tree) or ""

        slug_to_load = st.session_state.get("selected_page_slug")

        with left_col:
            st.subheader("Páginas")
            render_tree_navigation(pages_tree, slug_to_load)

        with right_col:
            if not slug_to_load:
                st.info("Seleccione una página de la izquierda para ver su contenido.")
            else:
                content_data = get_page_content(project_id, slug_to_load)

                st.header(content_data.get("title", slug_to_load))

                # Descarga de PDF
                try:
                    response = requests.get(
                        f"{API_BASE_URL}/wiki/projects/{project_id}/generate_pdf/{quote(slug_to_load, safe='')}",
                        verify=False,
                    )
                    response.raise_for_status()
                    st.download_button(
                        label="⬇️ Descargar como PDF",
                        data=response.content,
                        file_name=f"{slug_to_load.split('/')[-1]}.pdf",
                        mime="application/pdf",
                    )
                except requests.exceptions.HTTPError as e:
                    try:
                        error_detail = e.response.json().get("detail", e.response.text)
                    except:
                        error_detail = e.response.text
                    st.error(f"No se pudo generar el PDF: {error_detail}")
                except Exception as e:
                    st.error(f"Error de conexión al generar PDF: {e}")

                st.divider()
                st.markdown(
                    content_data.get("content", "*No se encontró contenido.*"),
                    unsafe_allow_html=True,
                )
=======
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
>>>>>>> 934b995f50798a832f6fad9e0f26cfd2865870ba
