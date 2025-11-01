import React, { useState, useEffect } from 'react';
import { getActiveProjects, getTasksForProject } from './services/api';
import ProjectList from './components/ProjectList';
import TaskDetails from './components/TaskDetails';
import './App.css'; // Archivo principal de estilos

function App() {
  const [projects, setProjects] = useState([]);
  const [selectedProject, setSelectedProject] = useState({ id: null, name: '' });
  const [tasks, setTasks] = useState([]);
  const [isLoadingTasks, setIsLoadingTasks] = useState(false);
  const [error, setError] = useState('');

  // Efecto para cargar la lista de proyectos al montar el componente
  useEffect(() => {
    const fetchProjects = async () => {
      try {
        const activeProjects = await getActiveProjects();
        setProjects(activeProjects);
        // Si hay proyectos, selecciona el primero por defecto
        if (activeProjects && activeProjects.length > 0) {
          setSelectedProject({ id: activeProjects[0].id, name: activeProjects[0].name });
        }
      } catch (err) {
        setError('No se pudo cargar la lista de proyectos.');
      }
    };
    fetchProjects();
  }, []); // El array vacío asegura que se ejecute solo una vez

  // Efecto para cargar las tareas cuando cambia el proyecto seleccionado
  useEffect(() => {
    const fetchTasks = async () => {
      if (!selectedProject.id) return;
      setIsLoadingTasks(true);
      setError('');
      try {
        const projectTasks = await getTasksForProject(selectedProject.id);
        setTasks(projectTasks);
      } catch (err) {
        setError(`No se pudieron cargar las tareas para ${selectedProject.name}.`);
      } finally {
        setIsLoadingTasks(false);
      }
    };
    fetchTasks();
  }, [selectedProject.id]); // Se ejecuta cada vez que selectedProject.id cambia

  const handleSelectProject = (projectId, projectName) => {
    setSelectedProject({ id: projectId, name: projectName });
  };

  if (error && projects.length === 0) {
    return <div className="container error-message">{error}</div>;
  }
  
  if (projects.length === 0 && !error) {
      return (
        <div className="container success-message">
            <h1>🎉 ¡Excelente trabajo!</h1>
            <p>No hay tareas en revisión en ningún proyecto monitoreado.</p>
        </div>
      );
  }

  return (
    <div className="container">
      <header>
        <h1>📈 Dashboard de Tareas en Revisión</h1>
      </header>
      <main className="dashboard-layout">
        <aside className="left-panel">
          <ProjectList
            projects={projects}
            selectedProjectId={selectedProject.id}
            onSelectProject={handleSelectProject}
          />
        </aside>
        <section className="right-panel">
          <TaskDetails
            tasks={tasks}
            projectName={selectedProject.name}
            isLoading={isLoadingTasks}
          />
        </section>
      </main>
    </div>
  );
}

export default App;