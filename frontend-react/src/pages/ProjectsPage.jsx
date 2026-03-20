
import React, { useState, useEffect } from 'react';
import { verifyConfigAccess, getConfigProjects, toggleProjectState, updateProject } from '../services/api';

function ProjectsPage() {
  const[configPass, setConfigPass] = useState(sessionStorage.getItem('config_pass') || '');
  const [inputPass, setInputPass] = useState('');
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [authError, setAuthError] = useState('');
  const[processingId, setProcessingId] = useState(null);
  
  const [editingProject, setEditingProject] = useState(null);
  const [editForm, setEditForm] = useState({ id: '', name: '' });
  const[editLoading, setEditLoading] = useState(false);
  const [editError, setEditError] = useState('');

  
  // Auto-fetch if token exists in session
  useEffect(() => {
    if (configPass) {
      loadProjects(configPass);
    }
  }, [configPass]);

  const loadProjects = async (password) => {
    setLoading(true);
    try {
      const data = await getConfigProjects(password);
      setProjects(data);
    } catch (err) {
      handleLogout(); // Auto logout on 401
    } finally {
      setLoading(false);
    }
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    setAuthError('');
    setLoading(true);
    try {
      await verifyConfigAccess(inputPass);
      sessionStorage.setItem('config_pass', inputPass);
      setConfigPass(inputPass);
    } catch (err) {
      setAuthError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    sessionStorage.removeItem('config_pass');
    setConfigPass('');
    setInputPass('');
    setProjects([]);
  };

  const handleToggle = async (projectId) => {
    setProcessingId(projectId);
    setError('');
    try {
      const updatedProject = await toggleProjectState(projectId, configPass);
      setProjects(prev => 
        prev.map(p => p.id === projectId ? { ...p, is_active: updatedProject.is_active } : p)
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setProcessingId(null);
    }
  };

  const handleOpenEdit = (project) => {
    setEditingProject(project.id);
    setEditForm({ id: project.id, name: project.name });
    setEditError('');
  };

  const handleSaveEdit = async () => {
    setEditLoading(true);
    setEditError('');
    try {
      const updated = await updateProject(editingProject, editForm.id, editForm.name, configPass);
      setProjects(prev => prev.map(p => p.id === editingProject ? updated : p));
      setEditingProject(null);
    } catch (err) {
      setEditError(err.message);
    } finally {
      setEditLoading(false);
    }
  };

  // --- UI: Auth Guard View ---
  if (!configPass) {
    return (
      <div className="container">
        <div className="auth-container">
          <h2 style={{ marginBottom: '1.5rem', color: '#343a40' }}>🔒 Área Protegida</h2>
          <form onSubmit={handleLogin}>
            <input 
              type="password" 
              className="auth-input"
              value={inputPass}
              onChange={(e) => setInputPass(e.target.value)}
              placeholder="Contraseña de Configuración"
              required 
            />
            <button type="submit" className="sync-button" style={{ width: '100%' }} disabled={loading}>
              {loading ? 'Verificando...' : 'Acceder a Configuración'}
            </button>
            {authError && <p className="error-message" style={{ color: '#dc3545', marginTop: '1rem', padding: 0 }}>{authError}</p>}
          </form>
        </div>
      </div>
    );
  }

  // --- UI: Control Panel View ---
  return (
    <div className="container">
      <div className="projects-header">
        <div>
          <h2 style={{ margin: 0 }}>Gestión de Proyectos Monitoreados</h2>
          <p style={{ margin: '0.5rem 0 0 0', color: '#6c757d' }}>
            Los proyectos inactivos no consumirán recursos de red ni aparecerán en el Dashboard.
          </p>
        </div>
        <button onClick={handleLogout} className="logout-btn">
          Salir (Cerrar Sesión)
        </button>
      </div>

      <div className="project-list" style={{ backgroundColor: '#fff', padding: '2rem', borderRadius: '8px', border: '1px solid #dee2e6' }}>
        <h3 style={{ marginTop: 0 }}>Proyectos Actuales</h3>
        
        {loading && <p>Cargando lista de proyectos...</p>}
        {error && <p className="error-message" style={{ color: '#dc3545', padding: '1rem 0' }}>{error}</p>}
        
        {!loading && projects.length > 0 && (
          <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: '1rem' }}>
            <thead>
              <tr style={{ backgroundColor: '#f8f9fa', borderBottom: '2px solid #dee2e6' }}>
                <th style={{ padding: '1rem', textAlign: 'left' }}>ID GitLab</th>
                <th style={{ padding: '1rem', textAlign: 'left' }}>Nombre del Proyecto</th>
                <th style={{ padding: '1rem', textAlign: 'center' }}>Estado (Toggle)</th>
              </tr>
            </thead>
            <tbody>
              {projects.map(p => (
                <tr key={p.id} style={{ borderBottom: '1px solid #e9ecef' }}>
                  <td style={{ padding: '1rem', fontWeight: 'bold', color: '#495057' }}>{p.id}</td>
                  <td style={{ padding: '1rem' }}>{p.name}</td>
                  <td style={{ padding: '1rem', textAlign: 'center' }}>
                    <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'center' }}>
                      <button 
                        className={`toggle-btn ${p.is_active ? 'active' : 'inactive'}`}
                        onClick={() => handleToggle(p.id)}
                        disabled={processingId === p.id}
                      >
                        {processingId === p.id ? '⏳...' : (p.is_active ? '🟢 Activo' : '🔴 Inactivo')}
                      </button>
                      <button 
                        className="toggle-btn"
                        style={{ backgroundColor: '#ffc107', color: '#212529', borderColor: '#ffc107' }}
                        onClick={() => handleOpenEdit(p)}
                        disabled={processingId === p.id}
                      >
                        ✏️ Editar
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {editingProject && (
        <div style={{ position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh', backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1000 }}>
          <div style={{ backgroundColor: 'white', padding: '2rem', borderRadius: '8px', width: '400px', maxWidth: '90%', boxShadow: '0 4px 12px rgba(0,0,0,0.15)' }}>
            <h3 style={{ marginTop: 0 }}>✏️ Editar Proyecto</h3>
            {editError && <p className="error-message" style={{ color: '#dc3545', padding: '0.5rem 0', textAlign: 'left' }}>{editError}</p>}
            <div style={{ marginBottom: '1rem' }}>
              <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold' }}>ID del Proyecto (GitLab)</label>
              <input 
                type="number" 
                className="auth-input" 
                style={{ marginBottom: 0 }}
                value={editForm.id} 
                onChange={e => setEditForm({...editForm, id: e.target.value})} 
              />
            </div>
            <div style={{ marginBottom: '1.5rem' }}>
              <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold' }}>Nombre del Proyecto</label>
              <input 
                type="text" 
                className="auth-input" 
                style={{ marginBottom: 0 }}
                value={editForm.name} 
                onChange={e => setEditForm({...editForm, name: e.target.value})} 
              />
            </div>
            <div style={{ display: 'flex', gap: '1rem', justifyContent: 'flex-end' }}>
              <button 
                className="sync-button" 
                style={{ backgroundColor: '#6c757d', borderColor: '#6c757d' }} 
                onClick={() => setEditingProject(null)} 
                disabled={editLoading}
              >
                Cancelar
              </button>
              <button 
                className="sync-button" 
                onClick={handleSaveEdit} 
                disabled={editLoading}
              >
                {editLoading ? 'Guardando...' : 'Guardar Cambios'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default ProjectsPage;
