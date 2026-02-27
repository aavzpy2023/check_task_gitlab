// frontend-react/src/components/TaskItem.jsx
import React, { useState } from 'react';
import CycleBadges from './CycleBadges';
import './TaskItem.css';

/**
 * Sanitiza un texto en Markdown eliminando la sintaxis de imágenes para evitar roturas de layout.
 * @param {string | null} text El texto a limpiar.
 * @returns {string} El texto limpio.
 */
const sanitizeMarkdown = (text) => {
  if (!text) return 'Sin descripción.';
  // Expresión regular para encontrar y reemplazar ![alt text](url) por un placeholder
  return text.replace(/!\[.*?\]\(.*?\)/g, '[Imagen Omitida]');
};

/**
 * Determina si una tarea está estancada basándose en su fecha de última actualización.
 * Criterio: Más de 3 días de inactividad.
 * @param {string} dateString Fecha en formato ISO.
 * @returns {boolean} True si está estancada.
 */
const isTaskStale = (dateString) => {
  if (!dateString) return false;
  const lastUpdate = new Date(dateString);
  const now = new Date();
  
  // Diferencia en milisegundos
  const diffTime = Math.abs(now - lastUpdate);
  // Convertir a días (1000ms * 60s * 60m * 24h)
  const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24)); 
  
  // Retorna verdadero si han pasado más de 3 días
  return diffDays > 3;
};

const TaskItem = ({ task }) => {
  const [isExpanded, setIsExpanded] = useState(false);

  // Calculamos el estado de estancamiento
  const isStale = isTaskStale(task.updated_at);

  // Fallback para legacy JSONB de metrics
  const cycleMetrics = task.cycle_metrics || {};
  const qaBounces = cycleMetrics.qa_bounces || 0;
  const functionalBounces = cycleMetrics.functional_bounces || 0;
  const totalBounces = qaBounces + functionalBounces;

  return (
    <div className={`task-item-container ${isStale ? 'stale-task' : ''}`}>
      
      {/* Sección Superior: Cabecera y Métricas */}
      <div className="task-item-header-wrapper">
        
        {/* 1. Burbujas de Métricas de Ciclo (Visualización del Flujo) */}
        {/* Se muestran arriba del título para dar contexto inmediato del histórico */}
        <div style={{ marginBottom: '0.5rem' }}>
            <CycleBadges metrics={task.cycle_metrics} />
        </div>

        {/* 2. Fila del Título y Enlace */}
        <div className="task-item-title-row">
          <a 
            href={task.url} 
            target="_blank" 
            rel="noopener noreferrer" 
            className="task-link"
            title="Abrir en GitLab"
          >[LINK]
          </a>

           <h5 className="task-title" onClick={() => setIsExpanded(!isExpanded)}>
            <strong>[{task.project_name}]</strong> {task.title}

            {/* SKDEV BYPASS: Cambiamos totalBounces > 0 a >= 0 temporalmente para forzar su visualización */}
            {totalBounces >= 0 && (
              <span className="rework-badge" title={`QA: ${qaBounces} | Funcional: ${functionalBounces}`}>
                🔄 Retrabajos: {totalBounces}
              </span>
            )}
          </h5>

          {/* Badge de Alerta si está estancada */}
          {isStale && (
            <span className="stale-badge" title="Sin actividad por más de 3 días">
              ⚠️ Retrasado
            </span>
          )}
        </div>
      </div>

      {/* Sección Inferior: Detalles Expandibles */}
      {isExpanded && (
        <div className="task-item-details">
          <div className="task-description">
            <p>{sanitizeMarkdown(task.description)}</p>
          </div>
          
          <hr />
          
          <div className="task-meta">
            <span><strong>Autor:</strong> {task.author}</span>
            {task.assignee && <span><strong>Asignado a:</strong> {task.assignee}</span>}
            {task.milestone && <span><strong>Milestone:</strong> {task.milestone}</span>}
          </div>

          <div className="task-extended-meta">
            <span><strong>Creado:</strong> {new Date(task.created_at).toLocaleDateString()}</span>
            
            {task.updated_at && (
                <span style={{ 
                    color: isStale ? '#dc3545' : 'inherit', 
                    fontWeight: isStale ? 'bold' : 'normal' 
                }}>
                    <strong>Actualizado:</strong> {new Date(task.updated_at).toLocaleDateString()}
                </span>
            )}

            {task.time_stats.human_total_time_spent && (
                <span><strong>Tiempo Invertido:</strong> {task.time_stats.human_total_time_spent}</span>
            )}
             {task.time_stats.human_time_estimate && (
                <span><strong>Estimado:</strong> {task.time_stats.human_time_estimate}</span>
            )}
          </div>

          {task.labels && task.labels.length > 0 && (
            <div className="task-labels">
              {task.labels.map(label => (
                <span key={label} className="task-label">{label}</span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default TaskItem;