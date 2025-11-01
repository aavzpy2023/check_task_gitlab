import React from 'react';

const ProjectList = ({ projects, selectedProjectId, onSelectProject }) => {
  return (
    <div>
      <h3>Proyectos Activos</h3>
      <div className="project-list">
        {projects.map(project => (
          <button
            key={project.id}
            className={`project-button ${project.id === selectedProjectId ? 'selected' : ''}`}
            onClick={() => onSelectProject(project.id, project.name)}
          >
            {project.name} ({project.review_task_count})
          </button>
        ))}
      </div>
    </div>
  );
};

export default ProjectList;