// frontend-react/src/components/Navbar.jsx
import React from 'react';
import { NavLink } from 'react-router-dom';
import './Navbar.css';

const Navbar = () => (
  <nav className="navbar">
    <div className="navbar-brand">
      <NavLink to="/" className="navbar-item brand">
        📖 Portal Unificado
      </NavLink>
    </div>
    
    <div className="navbar-menu">
      {/* Botón Dashboard */}
      <NavLink 
        to="/" 
        className={({ isActive }) => (isActive ? 'navbar-item active' : 'navbar-item')}
      >
        Dashboard
      </NavLink>

      {/* SSS: Botón NUEVO para Documentación */}
      <NavLink 
        to="/docs" 
        className={({ isActive }) => (isActive ? 'navbar-item active' : 'navbar-item')}
      >
        Documentación
      </NavLink>

      {/* Botón Proyectos */}
      <NavLink 
        to="/projects" 
        className={({ isActive }) => (isActive ? 'navbar-item active' : 'navbar-item')}
      >
        Proyectos
      </NavLink>
    </div>
  </nav>
);

export default Navbar;