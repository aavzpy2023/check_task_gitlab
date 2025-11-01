-- SSS v4.2.0 - Script de Inicialización v2.0 (con tabla de proyectos)

-- Tabla para almacenar las tareas de GitLab
CREATE TABLE IF NOT EXISTS gitlab_tasks (
    task_id         BIGINT PRIMARY KEY,
    project_id      BIGINT NOT NULL,
    updated_at      TIMESTAMPTZ,
    raw_data        JSONB
);
CREATE INDEX IF NOT EXISTS idx_gitlab_tasks_project_id ON gitlab_tasks(project_id);

-- --- NUEVA TABLA ---
-- Tabla para almacenar los proyectos a monitorear, reemplazando projects.csv
CREATE TABLE IF NOT EXISTS monitored_projects (
    project_id      BIGINT PRIMARY KEY,
    project_name    VARCHAR(255) NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
\echo '✅ Script de inicialización de la base de datos v2.0 ejecutado.'