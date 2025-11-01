import React, { useState, useEffect } from 'react';
import axios from 'axios';

function ProjectsPage() {
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [newProjectId, setNewProjectId] = useState('');
  const [newProjectName, setNewProjectName] = useState('');
  const [formError, setFormError] = useState('');

  const fetchProjects = () => { /* ... (código de la respuesta anterior, es correcto) ... */ };
  useEffect(() => { fetchProjects(); }, []);
  const handleAddProject = (e) => { /* ... (código de la respuesta anterior, es correcto) ... */ };

  return (
    <div>
      <h2>Gestión de Proyectos Monitoreados</h2>
      <div className="project-management-container">
        <div className="add-project-form">
          <h3>Añadir Nuevo Proyecto</h3>
          <form onSubmit={handleAddProject}>
            <input type="number" value={newProjectId} onChange={(e) => setNewProjectId(e.target.value)} placeholder="ID del Proyecto" required />
            <input type="text" value={newProjectName} onChange={(e) => setNewProjectName(e.target.value)} placeholder="Nombre del Proyecto" required />
            <button type="submit">Añadir Proyecto</button>
            {formError && <p className="error-message">{formError}</p>}
          </form>
        </div>
        <div className="project-list">
          <h3>Proyectos Actuales</h3>
          {loading && <p>Cargando...</p>}
          {error && <p className="error-message">{error}</p>}
          <table>
            <thead><tr><th>ID</th><th>Nombre</th></tr></thead>
            <tbody>{projects.map(p => (<tr key={p.project_id}><td>{p.project_id}</td><td>{p.project_name}</td></tr>))}</tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
export default ProjectsPage;