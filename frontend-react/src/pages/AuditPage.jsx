import React, { useState, useEffect, useCallback } from 'react';
import { getAuditMetrics, forceAuditSync, getAuditSyncStatus, getWikiDetails } from '../services/api';

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
  const [isSyncing, setIsSyncing] = useState(false);
  const [error, setError] = useState(null);

  const now = new Date();
  const [month, setMonth] = useState(now.getMonth() + 1);
  const[year, setYear] = useState(now.getFullYear());

  const[wikiDetails, setWikiDetails] = useState([]);
  const [expandedRows, setExpandedRows] = useState([]);

  const toggleRow = (username) => {
    setExpandedRows(prev =>
      prev.includes(username) ? prev.filter(u => u !== username) : [...prev, username]
    );
  };

  const getEventBadge = (type) => {
    switch(type) {
      case 'UC_CREATED': return { label: 'CU (Creado)', bg: '#d4edda', color: '#155724' };
      case 'UC_UPDATED': return { label: 'CU (Actualizado)', bg: '#fff3cd', color: '#856404' };
      case 'MANUAL_CREATED': return { label: 'Manual (Creado)', bg: '#cce5ff', color: '#004085' };
      case 'MANUAL_UPDATED': return { label: 'Manual (Actualizado)', bg: '#e2e3e5', color: '#383d41' };
      case 'PUSH_EVENT': return { label: 'Git Push (Terminal)', bg: '#f3e8ff', color: '#6f42c1' };
      default: return { label: type, bg: '#f8f9fa', color: '#212529' };
    }
  };

  const fetchMetrics = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [data, detailsData] = await Promise.all([
        getAuditMetrics(month, year),
        getWikiDetails(month, year)
      ]);
      setAuditData(data ||[]);
      setWikiDetails(detailsData ||[]);
    } catch (err) {
      setError("Fallo al obtener las métricas de auditoría. Verifique la conexión.");
    } finally {
      setLoading(false);
    }
  }, [month, year]);

  // Initial load
  useEffect(() => {
    fetchMetrics();
  }, [fetchMetrics]);

  // Polling for Sync Status
  useEffect(() => {
    let interval;
    if (isSyncing) {
      interval = setInterval(async () => {
        try {
          const status = await getAuditSyncStatus();
          if (!status.is_syncing) {
            setIsSyncing(false);
            fetchMetrics();
          }
        } catch (e) {
          console.error("Error checking sync status:", e);
        }
      }, 3000); // Poll every 3 seconds
    }
    return () => clearInterval(interval);
  },[isSyncing, fetchMetrics]);

  const handleSyncClick = async () => {
    setError(null);
    try {
      setIsSyncing(true);
      await forceAuditSync(month, year);
    } catch (err) {
      setIsSyncing(false);
      setError("No se pudo iniciar la sincronización. Puede que ya haya una en curso.");
    }
  };

  const getBadgeStyle = (onTime, total) => {
    if (total === 0) return { color: '#6c757d' };
    if (onTime === total) return { color: '#28a745', fontWeight: 'bold' };
    if (onTime > 0) return { color: '#fd7e14', fontWeight: 'bold' };
    return { color: '#dc3545', fontWeight: 'bold' };
  };

    const handleExportCSV = () => {
    if (!auditData || auditData.length === 0) return;

    const headers =[
      'Usuario', 'Issues Levantadas', 'Issues Revisadas',
      'Rev. en Tiempo', 'CU Creados', 'CU Actualizados',
      'Man. Creados', 'Man. Actualizados', 'Pushes (Terminal)'
    ];

    const rows = auditData.map(w =>[
      w.username, w.issues_raised, w.issues_reviewed,
      w.issues_reviewed_on_time, w.uc_created, w.uc_updated,
      w.manual_created, w.manual_updated, w.total_pushes || 0
    ]);

    const csvContent =[headers.join(',')]
      .concat(rows.map(row => row.join(',')))
      .join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');

    link.setAttribute('href', url);
    link.setAttribute('download', `auditoria_qa_${year}_${month}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="container">
      <header style={{ marginBottom: '2rem' }}>
        <h1>📊 Auditoría de Rendimiento QA</h1>
        <p className="sync-time">Métricas extraídas asíncronamente desde GitLab</p>
      </header>

      <section className="header-controls" style={{ marginBottom: '2rem' }}>
        <div className="sync-container">
          <label><strong>Mes:</strong> </label>
          <select
            value={month}
            onChange={(e) => setMonth(Number(e.target.value))}
            style={{ padding: '0.5rem', marginRight: '1rem' }}
            disabled={isSyncing}
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
            disabled={isSyncing}
          />

          <button
            onClick={handleSyncClick}
            disabled={isSyncing || loading}
            className="sync-button"
            style={{ marginLeft: '2rem' }}
          >
            {isSyncing ? 'Sincronizando en Segundo Plano...' : 'Extraer Datos de GitLab'}
          </button>
          <button
            onClick={handleExportCSV}
            disabled={isSyncing || loading || auditData.length === 0}
            className="sync-button"
            style={{
              marginLeft: '1rem',
              backgroundColor: '#17a2b8',
              borderColor: '#17a2b8'
            }}
            title="Exportar a CSV"
          >
            📥 Descargar CSV
          </button>
        </div>
      </section>

      {error && (
        <div className="status-message error">
          <p>⚠️ {error}</p>
        </div>
      )}

      {isSyncing && (
        <div className="status-message">
          <p>⏳ El servidor está extrayendo datos de GitLab para todos los proyectos. Esto puede tardar varios minutos...</p>
        </div>
      )}

      {!isSyncing && loading && (
        <div className="status-message">
          <p>Cargando métricas consolidadas...</p>
        </div>
      )}

      {!isSyncing && !loading && auditData.length > 0 && (
        <table style={{ width: '100%', borderCollapse: 'collapse', backgroundColor: '#fff', fontSize: '0.95rem' }}>
          <thead>
            <tr style={{ backgroundColor: '#f8f9fa', borderBottom: '2px solid #dee2e6' }}>
              <th style={{ padding: '1rem', textAlign: 'left' }}>Usuario</th>
              <th style={{ padding: '1rem', textAlign: 'center' }}>Issues Levantadas</th>
              <th style={{ padding: '1rem', textAlign: 'center' }}>Issues Revisadas</th>
              <th style={{ padding: '1rem', textAlign: 'center' }}>Rev. en Tiempo (≤3d)</th>
              <th style={{ padding: '1rem', textAlign: 'center' }}>CU Creados</th>
              <th style={{ padding: '1rem', textAlign: 'center' }}>Man. Actualizados</th>
              <th style={{ padding: '1rem', textAlign: 'center', color: '#6f42c1' }}>Pushes</th>
            </tr>
          </thead>
          <tbody>
            {auditData.map((worker) => {
              const isExpanded = expandedRows.includes(worker.username);
              const userWikiDetails = wikiDetails.filter(d => d.username === worker.username);

              return (
                <React.Fragment key={worker.username}>
                  <tr
                    style={{ borderBottom: '1px solid #e9ecef', cursor: 'pointer', backgroundColor: isExpanded ? '#f0f8ff' : 'transparent', transition: 'background-color 0.2s' }}
                    onClick={() => toggleRow(worker.username)}
                    title="Clic para ver detalle de actividad"
                  >
                    <td style={{ padding: '1rem', fontWeight: 'bold' }}>
                      <span style={{ display: 'inline-block', width: '20px', color: '#007bff' }}>
                        {isExpanded ? '▼' : '▶'}
                      </span>
                      @{worker.username}
                    </td>
                    <td style={{ padding: '1rem', textAlign: 'center' }}>{worker.issues_raised}</td>
                    <td style={{ padding: '1rem', textAlign: 'center' }}>{worker.issues_reviewed}</td>
                    <td style={{ padding: '1rem', textAlign: 'center', ...getBadgeStyle(worker.issues_reviewed_on_time, worker.issues_reviewed) }}>
                      {worker.issues_reviewed_on_time} / {worker.issues_reviewed}
                    </td>
                    <td style={{ padding: '1rem', textAlign: 'center' }}>{worker.uc_created}</td>
                    <td style={{ padding: '1rem', textAlign: 'center' }}>{worker.uc_updated}</td>
                    <td style={{ padding: '1rem', textAlign: 'center' }}>{worker.manual_created}</td>
                    <td style={{ padding: '1rem', textAlign: 'center' }}>{worker.manual_updated}</td>
                    <td style={{ padding: '1rem', textAlign: 'center', fontWeight: 'bold', color: '#6f42c1' }}>{worker.total_pushes || 0}</td>
                  </tr>

                  {isExpanded && (
                    <tr style={{ backgroundColor: '#fdfdfd' }}>
                      <td colSpan="9" style={{ padding: '1.5rem 2rem', borderBottom: '2px solid #dee2e6' }}>
                        <h5 style={{ marginTop: 0, marginBottom: '1rem', color: '#495057' }}>
                          📄 Detalle de Actividad (Wiki & Git Pushes) de este mes
                        </h5>
                        {userWikiDetails.length > 0 ? (
                          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem', backgroundColor: '#fff', border: '1px solid #ced4da', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
                            <thead>
                              <tr style={{ backgroundColor: '#e9ecef' }}>
                                <th style={{ padding: '0.5rem', textAlign: 'left', borderBottom: '1px solid #ced4da' }}>Proyecto</th>
                                <th style={{ padding: '0.5rem', textAlign: 'left', borderBottom: '1px solid #ced4da' }}>Nombre del Documento (Slug/Título)</th>
                                <th style={{ padding: '0.5rem', textAlign: 'center', borderBottom: '1px solid #ced4da' }}>Clasificación</th>
                                <th style={{ padding: '0.5rem', textAlign: 'center', borderBottom: '1px solid #ced4da' }}>Fecha Exacta</th>
                              </tr>
                            </thead>
                            <tbody>
                              {userWikiDetails.map((detail, idx) => {
                                const badge = getEventBadge(detail.event_type);
                                return (
                                  <tr key={idx}>
                                    <td style={{ padding: '0.5rem', borderBottom: '1px solid #e9ecef' }}>{detail.project_name}</td>
                                    <td style={{ padding: '0.5rem', borderBottom: '1px solid #e9ecef', fontWeight: 'bold' }}>{detail.reference_id}</td>
                                    <td style={{ padding: '0.5rem', borderBottom: '1px solid #e9ecef', textAlign: 'center' }}>
                                      <span style={{ padding: '3px 8px', borderRadius: '4px', fontSize: '0.8rem', backgroundColor: badge.bg, color: badge.color, fontWeight: 'bold' }}>
                                        {badge.label}
                                      </span>
                                    </td>
                                    <td style={{ padding: '0.5rem', borderBottom: '1px solid #e9ecef', textAlign: 'center' }}>
                                      {new Date(detail.event_date).toLocaleString()}
                                    </td>
                                  </tr>
                                );
                              })}
                            </tbody>
                          </table>
                        ) : (
                          <p style={{ margin: 0, color: '#6c757d', fontStyle: 'italic' }}>
                            No hay ediciones de Wiki registradas para este usuario en este mes. (Los pushes que no cumplan la heurística de Manual/CU se ignoran).
                          </p>
                        )}
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      )}

      {!isSyncing && !loading && auditData.length === 0 && !error && (
        <p className="status-message">No hay registros de auditoría almacenados para este mes. Por favor, extraiga datos de GitLab.</p>
      )}
    </div>
  );
};

export default AuditPage;