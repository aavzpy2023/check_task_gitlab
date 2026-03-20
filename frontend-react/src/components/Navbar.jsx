// frontend-react/src/components/Navbar.jsx
import React from 'react';
import { NavLink } from 'react-router-dom';
import './Navbar.css';

const Navbar = () => (
  <nav className="navbar">
    <div className="navbar-brand">
      <NavLink to="/" className="nav-link brand">
        📖 Portal Unificado
      </NavLink>
    </div>
    
    <div className="navbar-links">
      <NavLink 
        to="/" 
        className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}
      >
        Dashboard
      </NavLink>

      <NavLink 
        to="/docs" 
        className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}
      >
        Documentación
      </NavLink>

      <NavLink 
        to="/projects" 
        className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}
      >
        Proyectos
      </NavLink>

      <NavLink 
        to="/audit" 
        className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}
      >
        Auditoría
      </NavLink>
    </div>
  </nav>
);

export default Navbar;