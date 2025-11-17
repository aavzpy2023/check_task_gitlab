import React from 'react';

const ProjectList = ({ projects, selectedProjectId, onSelectProject }) => {
  return (
    <div>
      <h3>Proyectos Activos</h3>
      <div className="project-list">
        {projects.map(project => (
          <button
            key={project.id}
            // SSS: La clase 'selected' ahora se basa en la prop 'selectedProjectId'
            className={`project-button ${project.id === selectedProjectId ? 'selected' : ''}`}
            // SSS: El onClick ahora llama a la función pasada desde App.jsx
            onClick={() => onSelectProject(project.id)}
          >
            {project.name} ({project.review_task_count})
          </button>
        ))}
      </div>
    </div>
  );
};

export default ProjectList;