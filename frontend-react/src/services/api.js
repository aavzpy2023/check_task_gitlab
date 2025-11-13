// ./frontend-react/src/services/api.js
import axios from 'axios';

// SSS: Actualización del baseURL para que coincida con la nueva ruta de la API expuesta por Nginx.
const apiClient = axios.create({
  baseURL: '/tareas/api',
});

/**
 * Obtiene la lista de proyectos que tienen tareas activas en revisión.
 * @returns {Promise<Array>} Una promesa que resuelve a un array de proyectos.
 */
export const getActiveProjects = async () => {
  try {
    const response = await apiClient.get('/projects/active_from_db');
    return response.data;
  } catch (error) {
    console.error("Error fetching active projects:", error);
    throw error;
  }
};

/**
 * Obtiene las tareas para un ID de proyecto específico.
 * @param {number} projectId El ID del proyecto.
 * @returns {Promise<Array>} Una promesa que resuelve a un array de tareas.
 */
export const getTasksForProject = async (projectId) => {
  if (!projectId) return [];
  try {
    const response = await apiClient.get(`/projects/${projectId}/tasks_from_db`);
    return response.data;
  } catch (error) {
    console.error(`Error fetching tasks for project ${projectId}:`, error);
    throw error;
  }
};