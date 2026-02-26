import axios from 'axios';

const apiClient = axios.create({
  baseURL: '/tareas/api',
});

/**
 * Obtiene la lista de proyectos activos para una etiqueta de estado específica.
 * @param {string} label El nombre canónico de la etiqueta de estado.
 * @returns {Promise<Array>} Una promesa que resuelve a un array de proyectos.
 */
export const getActiveProjects = async (label) => {
  if (!label) return [];
  try {
    // SSS: CORRECCIÓN CRÍTICA Y FINAL
    // La petición DEBE incluir el objeto de configuración { params: ... }
    // para que axios construya la URL correctamente (ej. ...?label=En+Ejecucion)
    const response = await apiClient.get('/projects/active_from_db', { params: { label } });
    return response.data;
  } catch (error) {
    console.error("Error fetching active projects:", error);
    throw error;
  }
};

/**
 * Obtiene las tareas para un ID de proyecto y una etiqueta de estado específicos.
 * @param {number} projectId El ID del proyecto.
 * @param {string} label El nombre canónico de la etiqueta de estado.
 * @returns {Promise<Array>} Una promesa que resuelve a un array de tareas.
 */
export const getTasksForProject = async (projectId, label) => {
  if (!projectId || !label) return [];
  try {
    const response = await apiClient.get(`/projects/${projectId}/tasks_from_db`, { params: { label } });
    return response.data;
  } catch (error) {
    console.error(`Error fetching tasks for project ${projectId} and label ${label}:`, error);
    throw error;
  }
};

/**
 * Obtiene TODAS las tareas para una etiqueta de estado específica, de todos los proyectos.
 * @param {string} label El nombre canónico de la etiqueta de estado.
 * @returns {Promise<Array>} Una promesa que resuelve a un array de tareas enriquecidas.
 */
export const getAllTasksByLabel = async (label) => {
  if (!label) return [];
  try {
    const response = await apiClient.get('/tasks/all_by_label', { params: { label } });
    return response.data;
  } catch (error) {
    console.error(`Error fetching all tasks for label ${label}:`, error);
    throw error;
  }
};

export const forceSyncAll = async () => {
  try {
    const response = await apiClient.post('/sync/all');
    return response.data;
  } catch (error) {
    console.error("Error forcing sync:", error);
    throw error;
  }
};

export const getLastSyncTime = async () => {
  try {
    const response = await apiClient.get('/sync/last_time');
    return response.data;
  } catch (error) {
    console.error("Error fetching last sync time:", error);
    throw error;
  }
};

export const getSyncStatus = async () => {
  try {
    const response = await apiClient.get('/sync/status');
    return response.data;
  } catch (error) {
    console.error("Error fetching sync status:", error);
    return { is_syncing: false };
  }
};

export const forceSyncProject = async (projectId) => {
  if (!projectId) throw new Error("Project ID is required for sync.");
  try {
    const response = await apiClient.post(`/sync/project/${projectId}`);
    return response.data;
  } catch (error) {
    console.error(`Error forcing sync for project ${projectId}:`, error);
    throw error;
  }
};
export const getWikiProjects = async () => {
  try {
    const response = await apiClient.get('/wiki/projects');
    return response.data;
  } catch (error) {
    console.error("Error fetching wiki projects:", error);
    throw error;
  }
};

export const getWikiPages = async (projectId) => {
  try {
    const response = await apiClient.get(`/wiki/projects/${projectId}/pages`);
    return response.data;
  } catch (error) {
    console.error(`Error fetching wiki pages for project ${projectId}:`, error);
    throw error;
  }
};

export const getWikiPageContent = async (projectId, slug) => {
  try {
    // El slug puede venir con espacios, aseguramos codificación
    const encodedSlug = encodeURIComponent(slug);
    const response = await apiClient.get(`/wiki/projects/${projectId}/pages/${slug}`);
    return response.data;
  } catch (error) {
    console.error(`Error fetching page content for ${slug}:`, error);
    throw error;
  }
};

export const getAuditMetrics = async (month, year) => {
  try {
    const response = await apiClient.get('/audit/metrics', {
      params: { month, year }
    });
    return response.data;
  } catch (error) {
    console.error("Error fetching audit metrics:", error);
    throw error;
  }
};

export const forceAuditSync = async (month, year) => {
  try {
    const response = await apiClient.post('/audit/sync', null, {
      params: { month, year }
    });
    return response.data;
  } catch (error) {
    console.error("Error forcing audit sync:", error);
    throw error;
  }
};

export const getAuditSyncStatus = async () => {
  try {
    const response = await apiClient.get('/audit/sync/status');
    return response.data;
  } catch (error) {
    console.error("Error fetching audit sync status:", error);
    return { is_syncing: false };
  }
};

export const getWikiAudit = async (projectId, username, month, year) => {
  try {
    const response = await apiClient.get(`/wiki/projects/${projectId}/audit`, {
      params: { username, month, year }
    });
    return response.data;
  } catch (error) {
    console.error(`Error auditing wiki for ${username}:`, error);
    return { audit_count: 0, events: [] };
  }
};

export const getWikiDetails = async (month, year) => {
  try {
    const response = await apiClient.get('/audit/wiki_details', {
      params: { month, year }
    });
    return response.data;
  } catch (error) {
    console.error("Error fetching wiki details:", error);
    return[];
  }
};

export const verifyConfigAccess = async (password) => {
  try {
    const response = await apiClient.post('/config/auth', { password });
    return response.data;
  } catch (error) {
    throw new Error(error.response?.data?.detail || "Error de conexión");
  }
};

export const getConfigProjects = async (password) => {
  try {
    const response = await apiClient.get('/config/projects', {
      headers: { 'X-Config-Pass': password }
    });
    return response.data;
  } catch (error) {
    throw new Error("No autorizado o sesión expirada");
  }
};

export const toggleProjectState = async (projectId, password) => {
  try {
    const response = await apiClient.patch(`/config/projects/${projectId}/toggle`, {}, {
      headers: { 'X-Config-Pass': password }
    });
    return response.data;
  } catch (error) {
    throw new Error("Fallo al cambiar el estado del proyecto");
  }
};