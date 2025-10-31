// frontend-react/src/App.jsx
import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './App.css';

function App() {
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    // La llamada a la API ahora se hace a una ruta relativa.
    // Nginx se encargará de redirigirla al backend.
    axios.get('/api/wiki/projects')
      .then(response => {
        setProjects(response.data);
        setLoading(false);
      })
      .catch(error => {
        console.error("Error fetching projects:", error);
        setError("No se pudieron cargar los proyectos. Verifique la consola del navegador y los logs del backend.");
        setLoading(false);
      });
  }, []); // El array vacío asegura que esto se ejecute solo una vez

  return (
    <div className="app-container">
      <header>
        <h1>📖 Portal de Documentación y Tareas</h1>
      </header>
      <main>
        <h2>Proyectos con Wiki Activa</h2>
        {loading && <p>Cargando proyectos...</p>}
        {error && <p className="error">{error}</p>}
        <ul>
          {projects.map(project => (
            <li key={project.id}>{project.name} (ID: {project.id})</li>
          ))}
        </ul>
        <hr />
        <p>
          <a href="/api/docs" target="_blank" rel="noopener noreferrer">
            Probar la documentación de la API (Swagger UI)
          </a>
        </p>
      </main>
    </div>
  );
}

export default App;