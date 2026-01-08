// frontend-react/src/App.jsx
import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Navbar from './components/Navbar';

// Importación de Páginas
import TaskDashboardPage from './pages/TaskDashboardPage';
import DocumentationPage from './pages/DocumentationPage';
import ProjectsPage from './pages/ProjectsPage';

// Importación de Estilos Globales
import './App.css';

function App() {
  return (
    // SSS: 'basename' es CRÍTICO porque la app corre bajo /tareas/ en Nginx
    <BrowserRouter basename="/tareas">
      <div className="app-container">
        <Navbar />
        
        <div className="content-container">
          <Routes>
            {/* Ruta Principal: Dashboard */}
            <Route path="/" element={<TaskDashboardPage />} />
            
            {/* Ruta de Documentación */}
            <Route path="/docs" element={<DocumentationPage />} />
            
            {/* Ruta de Gestión de Proyectos */}
            <Route path="/projects" element={<ProjectsPage />} />
            
            {/* Ruta Wildcard para 404 (Opcional, redirige al home) */}
            <Route path="*" element={<TaskDashboardPage />} />
          </Routes>
        </div>
      </div>
    </BrowserRouter>
  );
}

export default App;