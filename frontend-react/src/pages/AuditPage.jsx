import React, { useState, useEffect, useCallback } from 'react';
import { getWikiProjects, getWikiAudit } from '../services/api';

/**
 * AuditPage: Orchestrates the aggregation of Wiki edits across all monitored
 * projects for a specific set of QA testers.
 */

const WORKERS = [
  { name: "Jennifer Rodríguez", username: "jennifer.rodriguez" },
  { name: "Yaima Hernández", username: "yaima.hernandez" },
  { name: "Massiel Gutiérrez", username: "massiel.gutierrez" },
  { name: "Elia Cárdenas", username: "elia.cardenas" },
  { name: "Alejandro Gil", username: "alejandro.gil" },
  { name: "Alianay Marcilla", username: "alianay.marcilla" },
];

const AuditPage = () => {
  const [auditData, setAuditData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Time filters state
  const now = new Date();
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [year, setYear] = useState(now.getFullYear());

  const runAudit = useCallback(async () => {
    setLoading(true);
    setError(null);
    console.log(`[AUDIT] Starting audit for ${month}/${year}`);

    try {
      const projects = await getWikiProjects();
      
      if (!projects || projects.length === 0) {
        throw new Error("No monitored projects found to audit.");
      }

      // We parallelize the audit per worker to improve performance
      const results = await Promise.all(WORKERS.map(async (worker) => {
        let totalCount = 0;
        
        // Sequential check per project to avoid hitting rate limits (GitLab)
        for (const project of projects) {
          try {
            const data = await getWikiAudit(project.id, worker.username, month, year);
            totalCount += (data?.audit_count || 0);
          } catch (e) {
            console.error(`Failed to audit project ${project.id} for ${worker.username}`);
          }
        }

        return {
          ...worker,
          totalEdits: totalCount
        };
      }));

      setAuditData(results);
    } catch (err) {
      console.error("[AUDIT ERROR]", err);
      setError(err.message || "Failed to generate audit report.");
    } finally {
      setLoading(false);
    }
  }, [month, year]);

  useEffect(() => {
    runAudit();
  }, [runAudit]);

  return (
    <div className="container">
      <header style={{ marginBottom: '2rem' }}>
        <h1>📊 Auditoría de Casos de Uso</h1>
        <p className="sync-time">Resumen mensual de actividad en Wikis de GitLab</p>
      </header>

      <section className="header-controls" style={{ marginBottom: '2rem' }}>
        <div className="sync-container">
          <label><strong>Mes:</strong> </label>
          <select 
            value={month} 
            onChange={(e) => setMonth(Number(e.target.value))}
            style={{ padding: '0.5rem', marginRight: '1rem' }}
          >
            {[...Array(12).keys()].map(m => (
              <option key={m + 1} value={m + 1}>
                {new Date(0, m).toLocaleString('es', { month: 'long' })}
              </option>
            ))}
          </select>

          <label><strong>Año:</strong> </label>
          <input 
            type="number" 
            value={year} 
            onChange={(e) => setYear(Number(e.target.value))}
            style={{ padding: '0.5rem', width: '80px' }}
          />
          
          <button 
            onClick={runAudit} 
            disabled={loading}
            className="sync-button"
            style={{ marginLeft: '2rem' }}
          >
            {loading ? 'Procesando...' : 'Recargar Datos'}
          </button>
        </div>
      </section>

      {error && (
        <div className="status-message error">
          <p>⚠️ {error}</p>
        </div>
      )}

      {loading && !auditData.length ? (
        <div className="status-message">
          <p>Consultando eventos en GitLab para los proyectos monitoreados...</p>
        </div>
      ) : (
        <table style={{ width: '100%', borderCollapse: 'collapse', backgroundColor: '#fff' }}>
          <thead>
            <tr style={{ backgroundColor: '#f8f9fa', borderBottom: '2px solid #dee2e6' }}>
              <th style={{ padding: '1rem', textAlign: 'left' }}>Tester</th>
              <th style={{ padding: '1rem', textAlign: 'left' }}>Usuario GitLab</th>
              <th style={{ padding: '1rem', textAlign: 'center' }}>Casos de Uso (Editados/Creados)</th>
            </tr>
          </thead>
          <tbody>
            {auditData.map((worker) => (
              <tr key={worker.username} style={{ borderBottom: '1px solid #e9ecef' }}>
                <td style={{ padding: '1rem' }}>{worker.name}</td>
                <td style={{ padding: '1rem' }}>
                  <code style={{ color: '#e83e8c' }}>@{worker.username}</code>
                </td>
                <td style={{ 
                  padding: '1rem', 
                  textAlign: 'center', 
                  fontWeight: 'bold', 
                  fontSize: '1.2rem',
                  color: worker.totalEdits > 0 ? '#28a745' : '#6c757d'
                }}>
                  {worker.totalEdits}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {!loading && auditData.length === 0 && !error && (
        <p className="status-message">No se encontraron datos para el periodo seleccionado.</p>
      )}
    </div>
  );
};

export default AuditPage;