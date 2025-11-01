import os
from datetime import datetime

# --- CONFIGURACIÓN ---
# Directorios base para escanear de forma recursiva.
DIRECTORIES_TO_SCAN = [
    ".",
]

# Extensiones de archivo que el script buscará y exportará.
FILE_EXTENSIONS_TO_INCLUDE = (
    ".py",
    ".yml",
    ".sh",
    ".env",
    ".conf",
    ".txt",  # Añadido para incluir los archivos de logs que proporcionaste
    ".md",
    ".json",
    ".html",
    "Dockerfile",
    ".jsx",
    ".css",
    ".conf",
    ".js",
    # Añade aquí otras extensiones si es necesario
)

# --- INICIO DE LA MODIFICACIÓN (NUEVA SECCIÓN) ---
# --- CONFIGURACIÓN DE EXCLUSIÓN ---
# Lista de rutas (archivos o directorios) a excluir de la exportación.
# Para directorios, asegúrese de que terminen con un separador (p. ej., '.git/').
PATHS_TO_EXCLUDE = [
    ".git/",
    "__pycache__/",
    ".venv/",
    ".vscode/",
    "frontend/node_modules/",
    "frontend/build/",
    ".mypy_cache/",
    # Excluir los archivos generados por este propio script
    "full_project_content_export.txt",
    "project_structure_tree.txt",
    "export_project.py",
    "volumes/",
    ".zed/",
    ".pytest_cache/",
    "documents/",
    "tree.txt",
]
# --- FIN DE LA MODIFICACIÓN ---

OUTPUT_FILE = "full_project_content_export.txt"
PROJECT_TREE_FILE = "project_structure_tree.txt"


def generate_project_tree(start_dir, files_to_process):
    """
    Genera un árbol de directorios y archivos para los archivos que serán procesados.
    """
    tree_lines = [
        f"Árbol de directorios para los archivos a exportar desde: {start_dir}\n"
    ]
    processed_files_set = {os.path.normpath(f) for f in files_to_process}

    for root, dirs, files in os.walk(start_dir, topdown=True):
        # --- MODIFICACIÓN: Excluir directorios del recorrido de os.walk ---
        dirs[:] = [
            d
            for d in dirs
            if os.path.normpath(os.path.join(root, d) + os.sep)
            not in [
                os.path.normpath(p)
                for p in PATHS_TO_EXCLUDE
                if p.endswith("/") or p.endswith("\\")
            ]
        ]

        level = root.replace(start_dir, "").count(os.sep)
        indent = "│   " * level
        if level == 0:
            tree_lines.append(f"├── {os.path.basename(root) or './'}\n")
        else:
            tree_lines.append(f"{indent}├── {os.path.basename(root)}/\n")

        sub_indent = "│   " * (level + 1)

        display_files = [
            f
            for f in files
            if os.path.normpath(os.path.join(root, f)) in processed_files_set
        ]

        for f in sorted(display_files):
            tree_lines.append(f"{sub_indent}├── {f}\n")

    return "".join(tree_lines)


def find_project_files(base_directories, extensions_to_include):
    """
    Escanea recursivamente los directorios especificados y devuelve una lista
    de rutas de archivos que coinciden con las extensiones dadas.
    """
    found_files = []
    print("\nBuscando archivos en los directorios especificados...")
    for base_dir in base_directories:
        if not os.path.isdir(base_dir):
            print(
                f"  [ADVERTENCIA] Directorio base no encontrado, se omitirá: {base_dir}"
            )
            continue

        for root, _, files in os.walk(base_dir):
            for file in files:
                if file.endswith(extensions_to_include):
                    full_path = os.path.join(root, file)
                    found_files.append(full_path)

    print(
        f"Se encontraron {len(found_files)} archivos candidatos antes de la exclusión."
    )
    return sorted(found_files)


# --- INICIO DE LA MODIFICACIÓN (NUEVA FUNCIÓN) ---
def filter_excluded_paths(file_list, exclusion_list):
    """
    Filtra una lista de archivos, excluyendo aquellos que coincidan con la
    lista de exclusión (tanto archivos individuales como directorios).
    """
    # Normalizar las rutas de exclusión para una comparación robusta
    normalized_exclusions = [os.path.normpath(p) for p in exclusion_list]

    excluded_dirs = [
        p
        for p in normalized_exclusions
        if p.endswith(os.sep) or (os.path.isdir(p) and not os.path.islink(p))
    ]
    excluded_files = {p for p in normalized_exclusions if p not in excluded_dirs}

    filtered_list = []
    for file_path in file_list:
        normalized_file_path = os.path.normpath(file_path)

        if normalized_file_path in excluded_files:
            print(f"  [EXCLUIDO - Archivo] {file_path}")
            continue

        is_in_excluded_dir = False
        for dir_path in excluded_dirs:
            # Asegurarse de que dir_path termine con un separador para la comparación startswith
            dir_prefix = dir_path if dir_path.endswith(os.sep) else dir_path + os.sep
            if normalized_file_path.startswith(dir_prefix):
                print(
                    f"  [EXCLUIDO - Directorio] {file_path} (contenido en {dir_path})"
                )
                is_in_excluded_dir = True
                break

        if not is_in_excluded_dir:
            filtered_list.append(file_path)

    return filtered_list


# --- FIN DE LA MODIFICACIÓN ---


def export_project_content(project_files_list):
    """
    Recorre la lista de archivos del proyecto, lee su contenido y lo escribe
    en un único archivo de salida.
    """
    print(f"\nIniciando la exportación del contenido a '{OUTPUT_FILE}'...")
    try:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as outfile:
            outfile.write(
                f"--- Contenido del Proyecto Exportado el {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n"
            )
            processed_count = 0
            for file_path in project_files_list:
                header = f"\n\n// --- {file_path} ---\n\n"
                outfile.write(header)
                try:
                    with open(file_path, "r", encoding="utf-8") as infile:
                        content = infile.read()
                        outfile.write(content)
                    print(f"  [OK] Procesado: {file_path}")
                    processed_count += 1
                except Exception as e:
                    error_message = (
                        f"  [ERROR] No se pudo leer el archivo {file_path}: {e}"
                    )
                    outfile.write(
                        f"*** ERROR AL LEER EL ARCHIVO: {file_path} | Motivo: {e} ***\n"
                    )
                    print(error_message)
            print(
                f"\nExportación de contenido completada. Se procesaron {processed_count} archivos."
            )

    except IOError as e:
        print(
            f"[ERROR CRÍTICO] No se pudo escribir en el archivo de salida '{OUTPUT_FILE}': {e}"
        )


def write_project_tree(tree_content):
    """Escribe el contenido del árbol de proyecto a un archivo separado."""
    try:
        with open(PROJECT_TREE_FILE, "w", encoding="utf-8") as treefile:
            treefile.write(tree_content)
        print(f"El árbol de directorios ha sido guardado en '{PROJECT_TREE_FILE}'.")
    except IOError as e:
        print(
            f"[ERROR CRÍTICO] No se pudo escribir el archivo del árbol '{PROJECT_TREE_FILE}': {e}"
        )


if __name__ == "__main__":
    all_project_files = find_project_files(
        DIRECTORIES_TO_SCAN, FILE_EXTENSIONS_TO_INCLUDE
    )

    # --- INICIO DE LA MODIFICACIÓN (INTEGRACIÓN DEL FILTRADO) ---
    print("\nAplicando filtros de exclusión...")
    files_to_process = filter_excluded_paths(all_project_files, PATHS_TO_EXCLUDE)
    print(
        f"Total de archivos a procesar después de la exclusión: {len(files_to_process)}"
    )
    # --- FIN DE LA MODIFICACIÓN ---

    if not files_to_process:
        print(
            "\nNo se encontraron archivos que procesar después de la exclusión. Saliendo."
        )
    else:
        project_tree = generate_project_tree(
            DIRECTORIES_TO_SCAN[0] if DIRECTORIES_TO_SCAN else os.getcwd(),
            files_to_process,
        )
        write_project_tree(project_tree)
        export_project_content(files_to_process)
