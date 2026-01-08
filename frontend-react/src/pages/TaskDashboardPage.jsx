// frontend-react/src/pages/TaskDashboardPage.jsx
import React, { useState, useEffect } from 'react';
import { 
  getActiveProjects, 
  getAllTasksByLabel, 
  forceSyncAll, 
  forceSyncProject, 
  getLastSyncTime, 
  getSyncStatus 
} from '../services/api';
import ProjectList from '../components/ProjectList';
import TaskDetails from '../components/TaskDetails';
import '../App.css'; // Mantenemos los estilos globales por ahora

const TABS = {
  'Ejecución': 'En Ejecucion',
  'Revisión': 'PARA REVISIÓN',
  'Rev. Funcional': 'Revision Funcional',
};

function TaskDashboardPage() {
  const [projects, setProjects] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState(TABS['Revisión']);
  const [selectedProjectId, setSelectedProjectId] = useState(null);
  const [lastSyncTime, setLastSyncTime] = useState(null);
  const [isBackendSyncing, setIsBackendSyncing] = useState(false);

  // --- Lógica de Carga de Datos ---
  const fetchData = async () => {
    setIsLoading(true);
    setError('');
    try {
      // Nota: getActiveProjects ya está importado correctamente arriba
      const [projectsData, tasksData, syncTimeData] = await Promise.all([
        getActiveProjects(activeTab),
        getAllTasksByLabel(activeTab),
        getLastSyncTime()
      ]);
      
      setProjects(projectsData);
      setTasks(tasksData);
      setLastSyncTime(syncTimeData.last_sync_time);
      
    } catch (err) {
      console.error("Error en fetchData:", err);
      setError(`Fallo al cargar los datos. Verifique la conexión con la API.`);
    } finally {
      setIsLoading(false);
    }
  };
  
  // --- Polling de Estado de Sincronización ---
  useEffect(() => {
    const pollSyncStatus = async () => {
      try {
        const status = await getSyncStatus();
        const isCurrentlySyncing = status.is_syncing;
        
        // Si terminó de sincronizar, recargamos los datos automáticamente
        if (isBackendSyncing && !isCurrentlySyncing) {
          fetchData();
        }
        setIsBackendSyncing(isCurrentlySyncing);
      } catch (pollError) {
        console.error("Error polling sync status:", pollError);
      }
    };
    
    pollSyncStatus(); // Check inicial
    const intervalId = setInterval(pollSyncStatus, 3000); // Check cada 3s
    return () => clearInterval(intervalId);
  }, [isBackendSyncing]);

  // --- Efecto al cambiar de pestaña ---
  useEffect(() => {
    fetchData();
  }, [activeTab]);

  // --- Efecto de Selección Automática de Proyecto ---
  useEffect(() => {
    if (projects && projects.length > 0) {
      // Si el proyecto seleccionado ya no existe en la lista, seleccionar el primero
      const exists = projects.find(p => p.id === selectedProjectId);
      if (!selectedProjectId || !exists) {
        setSelectedProjectId(projects[0].id);
      }
    } else {
      setSelectedProjectId(null);
    }
  }, [projects]);

  // --- Handlers ---
  const handleForceSync = async () => {
    setError('');
    setIsBackendSyncing(true); // Feedback UI inmediato
    try {
      if (selectedProjectId) {
        await forceSyncProject(selectedProjectId);
      } else {
        await forceSyncAll();
      }
    } catch (err) {
      console.error(err);
      setError("Fallo al iniciar la sincronización. Verifique si ya hay una en curso.");
      setIsBackendSyncing(false); // Revertir estado si falla el inicio
    }
  };
  
  const handleSelectProject = (projectId) => {
    setSelectedProjectId(prev => (prev === projectId ? null : projectId));
  };

  // --- Filtrado de Tareas ---
  const filteredTasks = selectedProjectId
    ? tasks.filter(task => task.project_id === selectedProjectId)
    : [];
  
  const getCategoryName = () => {
      return Object.keys(TABS).find(key => TABS[key] === activeTab) || 'Desconocida';
  }

  const getProjectName = () => {
      if (!selectedProjectId) return "Seleccione un proyecto";
      return projects.find(p => p.id === selectedProjectId)?.name || "Proyecto Desconocido";
  }

  // --- Renderizado Condicional del Contenido Principal ---
  const renderMainContent = () => {
    if (isLoading && !isBackendSyncing && tasks.length === 0) {
      return <div className="status-message">Cargando datos...</div>;
    }
    if (error) {
      return <div className="status-message error">{error}</div>;
    }
    return (
      <main className="dashboard-layout">
        <aside className="left-panel">
          <ProjectList
            projects={projects}
            selectedProjectId={selectedProjectId}
            onSelectProject={handleSelectProject}
            disabled={isBackendSyncing}
          />
        </aside>
        <section className="right-panel">
          <TaskDetails
            tasks={filteredTasks}
            categoryName={`${getCategoryName()} en: ${getProjectName()}`}
            isLoading={isLoading || isBackendSyncing}
          />
        </section>
      </main>
    );
  };

  return (
    <div className="dashboard-container">
      <header>
        <h1>📈 Dashboard de Tareas GitLab</h1>
        <div className="header-controls">
          <div className="tabs-container">
            {Object.entries(TABS).map(([displayName, canonicalName]) => (
              <button
                key={canonicalName}
                className={`tab-button ${activeTab === canonicalName ? 'active' : ''}`}
                onClick={() => setActiveTab(canonicalName)}
                disabled={isBackendSyncing}
              >
                {displayName}
              </button>
            ))}
          </div>
          <div className="sync-container">
            <button onClick={handleForceSync} disabled={isBackendSyncing} className="sync-button">
              {isBackendSyncing ? 'Sincronizando...' : 'Sincronizar Ahora'}
            </button>
            {lastSyncTime && (
              <span className="sync-time">
                Última Sinc: {new Date(lastSyncTime).toLocaleString()}
              </span>
            )}
          </div>
        </div>
      </header>
      {renderMainContent()}
    </div>
  );
}

export default TaskDashboardPage;