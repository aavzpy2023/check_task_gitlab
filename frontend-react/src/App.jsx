// ./frontend-react/src/App.jsx
import React, { useState, useEffect } from 'react';
// import { getActiveProjects, getAllTasksByLabel, forceSyncAll, getLastSyncTime, getSyncStatus } from './services/api';
import { getAllTasksByLabel, forceSyncAll, forceSyncProject, getLastSyncTime, getSyncStatus } from './services/api';
import ProjectList from './components/ProjectList';
import TaskDetails from './components/TaskDetails';
import './App.css';

const TABS = {
  'Ejecución': 'En Ejecucion',
  'Revisión': 'PARA REVISIÓN',
  'Rev. Funcional': 'Revision Funcional',
};

function App() {
  const [projects, setProjects] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState(TABS['Revisión']);
  const [selectedProjectId, setSelectedProjectId] = useState(null);
  const [lastSyncTime, setLastSyncTime] = useState(null);
  const [isBackendSyncing, setIsBackendSyncing] = useState(false);

  const fetchData = async () => {
    setIsLoading(true);
    setError('');
    try {
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
  
  // Hook para polling de estado
  useEffect(() => {
    const pollSyncStatus = async () => {
      try {
        const status = await getSyncStatus();
        const isCurrentlySyncing = status.is_syncing;
        if (isBackendSyncing && !isCurrentlySyncing) {
          fetchData();
        }
        setIsBackendSyncing(isCurrentlySyncing);
      } catch (pollError) {
        console.error("Error en el polling de estado de sincronización:", pollError);
        setIsBackendSyncing(false);
      }
    };
    pollSyncStatus();
    const intervalId = setInterval(pollSyncStatus, 3000);
    return () => clearInterval(intervalId);
  }, [isBackendSyncing]);

  // Hook para cargar datos cuando cambia la pestaña
  useEffect(() => {
    fetchData();
  }, [activeTab]);

  // SSS: CORRECCIÓN DE UX FINAL
  // Este nuevo hook se ejecuta DESPUÉS de que los proyectos han sido actualizados
  useEffect(() => {
    if (projects && projects.length > 0) {
      setSelectedProjectId(projects[0].id); // Seleccionar siempre el primer proyecto
    } else {
      setSelectedProjectId(null); // Si no hay proyectos, deseleccionar
    }
  }, [projects]); // Dependencia: la lista de proyectos

  const handleForceSync = async () => {
    setError('');
    setIsSyncing(true); // Feedback inmediato UI
    try {
      if (selectedProjectId) {
        console.log(`Iniciando sincronización para proyecto único: ${selectedProjectId}`);
        await forceSyncProject(selectedProjectId);
      } else {
        console.log("Iniciando sincronización global (Todos los proyectos)");
        await forceSyncAll();
      }
    } catch (err) {
      console.error(err);
      setError("Fallo al iniciar la sincronización. Verifique si ya hay una en curso.");
      setIsSyncing(false);
    }
  };
  
  const handleSelectProject = (projectId) => {
    if (selectedProjectId === projectId) {
      setSelectedProjectId(null);
    } else {
      setSelectedProjectId(projectId);
    }
  };

  const filteredTasks = selectedProjectId
    ? tasks.filter(task => task.project_id === selectedProjectId)
    : []; // SSS: Si no hay proyecto seleccionado, no mostrar ninguna tarea inicialmente.
  
  const getCategoryName = () => {
      return Object.keys(TABS).find(key => TABS[key] === activeTab) || 'Desconocida';
  }

  const getProjectName = () => {
      // SSS: CORRECCIÓN - Mostrar "Seleccione un proyecto" si no hay ninguno seleccionado.
      if (!selectedProjectId) return "Seleccione un proyecto";
      return projects.find(p => p.id === selectedProjectId)?.name || "Proyecto Desconocido";
  }

  const renderContent = () => {
    if (isLoading && !isBackendSyncing) {
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
    <div className="container">
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
      {renderContent()}
    </div>
  );
}

export default App;