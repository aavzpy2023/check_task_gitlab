import React from 'react';
import { NavLink } from 'react-router-dom';

const Navbar = () => (
  <nav className="navbar">
    <div className="navbar-brand">
      <NavLink to="/" className="navbar-item brand">📖 Portal Unificado</NavLink>
    </div>
    <div className="navbar-menu">
      <NavLink to="/" className={({ isActive }) => (isActive ? 'navbar-item active' : 'navbar-item')}>Home</NavLink>
      <NavLink to="/tasks" className={({ isActive }) => (isActive ? 'navbar-item active' : 'navbar-item')}>Tareas</NavLink>
      <NavLink to="/documentation" className={({ isActive }) => (isActive ? 'navbar-item active' : 'navbar-item')}>Documentación</NavLink>
      <NavLink to="/projects" className={({ isActive }) => (isActive ? 'navbar-item active' : 'navbar-item')}>Proyectos</NavLink>
    </div>
  </nav>
);

export default Navbar;