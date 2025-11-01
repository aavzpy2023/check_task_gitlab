import React from 'react';
import TaskItem from './TaskItem';

const TaskDetails = ({ tasks, projectName, isLoading }) => {
  if (isLoading) {
    return <div>Cargando tareas...</div>;
  }

  if (!tasks || tasks.length === 0) {
    return <div>No hay tareas en revisión para este proyecto.</div>;
  }

  return (
    <div>
      <h3>Tareas en Revisión para: {projectName}</h3>
      {tasks.map(task => (
        <TaskItem key={task.url} task={task} />
      ))}
    </div>
  );
};

export default TaskDetails;