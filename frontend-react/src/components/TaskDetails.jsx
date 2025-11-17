import React from 'react';
import TaskItem from './TaskItem';

const TaskDetails = ({ tasks, isLoading, categoryName }) => {
  if (isLoading) {
    return <div>Cargando tareas...</div>;
  }

  if (!tasks || tasks.length === 0) {
    return <div>No hay tareas en la selección actual.</div>;
  }

  return (
    <div>
      <h3>Tareas para: {categoryName}</h3>
      {tasks.map(task => (
        <TaskItem key={task.url} task={task} />
      ))}
    </div>
  );
};

export default TaskDetails;