CREATE TABLE IF NOT EXISTS gitlab_tasks (
    -- Columnas clave para indexación y búsqueda rápida
    task_id         BIGINT PRIMARY KEY,
    project_id      BIGINT NOT NULL,
    updated_at      TIMESTAMPTZ,
    
    -- Columna JSONB para almacenar el objeto completo de la API.
    -- Es flexible y a prueba de futuros cambios en la API de GitLab.
    raw_data        JSONB,

    -- Timestamps de nuestro sistema
    first_seen_at   TIMESTAMPTZ DEFAULT NOW(),
    last_synced_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Índices para un rendimiento óptimo
CREATE INDEX IF NOT EXISTS idx_gitlab_tasks_project_id ON gitlab_tasks(project_id);
CREATE INDEX IF NOT EXISTS idx_gitlab_tasks_updated_at ON gitlab_tasks(updated_at);

-- Índice GIN para poder consultar eficientemente dentro del campo JSONB
CREATE INDEX IF NOT EXISTS idx_gitlab_tasks_raw_data_gin ON gitlab_tasks USING GIN (raw_data);

\echo '✅ Script de inicialización de la base de datos (esquema JSONB) ejecutado.'