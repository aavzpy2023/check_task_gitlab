import React from 'react';
import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom';
import Navbar from './components/Navbar';

// Importación de Páginas
import TaskDashboardPage from './pages/TaskDashboardPage';
import DocumentationPage from './pages/DocumentationPage';
import ProjectsPage from './pages/ProjectsPage';
import AuditPage from './pages/AuditPage';

// Importación de Estilos Globales
import './App.css';

// Componente de Depuración (Caja Roja)
const DebugLocation = () => {
  const location = useLocation();
  return (
    <div style={{ 
      background: 'rgba(220, 53, 69, 0.9)', 
      color: 'white', 
      padding: '8px 12px', 
      fontWeight: 'bold',
      fontSize: '14px', 
      position: 'fixed', 
      bottom: '10px', 
      right: '10px', 
      zIndex: 9999,
      borderRadius: '4px',
      fontFamily: 'monospace'
    }}>
      Ruta Actual: [{location.pathname}]
    </div>
  );
};

// SSS: ESTA LÍNEA ES LA QUE FALTABA. NO LA BORRES.
function App() {
  return (
    <BrowserRouter basename="/tareas">
      <div className="app-container">
        
        {/* Marca de versión v9.4 */}
        <div style={{display:'none'}}>v9.4-syntax-fixed</div>
        
        <DebugLocation />
        <Navbar />
        
        <div className="content-container">
          <Routes>
            {/* Ruta Principal */}
            <Route path="/" element={<TaskDashboardPage />} />
            
            {/* Rutas Secundarias (Sin slash inicial) */}
            <Route path="docs" element={<DocumentationPage />} />
            <Route path="projects" element={<ProjectsPage />} />
            
            {/* Ruta de Auditoría */}
            <Route path="audit" element={<AuditPage />} />
            
            {/* Ruta Wildcard */}
            <Route path="*" element={<TaskDashboardPage />} />
          </Routes>
        </div>
      </div>
    </BrowserRouter>
  );
}

export default App;