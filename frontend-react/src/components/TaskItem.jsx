import React, { useState } from 'react';
import './TaskItem.css';

/**
 * Sanitiza un texto en Markdown eliminando la sintaxis de imágenes.
 * @param {string | null} text El texto a limpiar.
 * @returns {string} El texto limpio.
 */
const sanitizeMarkdown = (text) => {
  if (!text) return 'Sin descripción.';
  // Expresión regular para encontrar y reemplazar ![alt text](url)
  return text.replace(/!\[.*?\]\(.*?\)/g, '[Imagen Omitida]');
};

const TaskItem = ({ task }) => {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className="task-item-container">
      <div className="task-item-header">
        <a href={task.url} target="_blank" rel="noopener noreferrer" className="task-link">
          [LINK]
        </a>
        <h5 className="task-title" onClick={() => setIsExpanded(!isExpanded)}>
          {/* SSS: Se añade el nombre del proyecto para el contexto */}
          <strong>[{task.project_name}]</strong> {task.title}
        </h5>
      </div>
      {isExpanded && (
        <div className="task-item-details">
          <p>{sanitizeMarkdown(task.description)}</p>
          <hr />
          <div className="task-meta">
            <span><strong>Autor:</strong> {task.author}</span>
            {task.assignee && <span><strong>Asignado a:</strong> {task.assignee}</span>}
            {task.milestone && <span><strong>Milestone:</strong> {task.milestone}</span>}
          </div>
          {/* SSS: NUEVA SECCIÓN DE DATOS EXTENDIDOS */}
          <div className="task-extended-meta">
            <span><strong>Creado:</strong> {new Date(task.created_at).toLocaleDateString()}</span>
            {task.time_stats.human_total_time_spent && <span><strong>Tiempo Invertido:</strong> {task.time_stats.human_total_time_spent}</span>}
            {task.time_stats.human_time_estimate && <span><strong>Tiempo Estimado:</strong> {task.time_stats.human_time_estimate}</span>}
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