// frontend-react/src/pages/DocumentationPage.jsx
import React, { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { getWikiProjects, getWikiPages, getWikiPageContent } from '../services/api';
import './DocumentationPage.css'; // Crearemos este CSS a continuación

export default function DocumentationPage() {
  const [projects, setProjects] = useState([]);
  const [selectedProjectId, setSelectedProjectId] = useState(null);
  const [pages, setPages] = useState([]);
  const [selectedPage, setSelectedPage] = useState(null); // Objeto completo de la página
  const [pageContent, setPageContent] = useState('');
  const [loading, setLoading] = useState(false);
  const [contentLoading, setContentLoading] = useState(false);

  // 1. Cargar lista de proyectos al inicio
  useEffect(() => {
    const fetchProjects = async () => {
      try {
        const data = await getWikiProjects();
        setProjects(data);
        if (data.length > 0) setSelectedProjectId(data[0].id);
      } catch (error) {
        console.error("Error cargando proyectos:", error);
      }
    };
    fetchProjects();
  }, []);

  // 2. Cargar lista de páginas cuando cambia el proyecto seleccionado
  useEffect(() => {
    if (!selectedProjectId) return;
    
    const fetchPages = async () => {
      setLoading(true);
      setPages([]);
      setSelectedPage(null);
      setPageContent('');
      try {
        const data = await getWikiPages(selectedProjectId);
        setPages(data);
        // Seleccionar la página 'home' por defecto si existe, o la primera
        const homePage = data.find(p => p.slug.toLowerCase() === 'home') || data[0];
        if (homePage) setSelectedPage(homePage);
      } catch (error) {
        console.error("Error cargando páginas:", error);
      } finally {
        setLoading(false);
      }
    };
    fetchPages();
  }, [selectedProjectId]);

  // 3. Cargar contenido cuando cambia la página seleccionada
  useEffect(() => {
    if (!selectedProjectId || !selectedPage) return;

    const fetchContent = async () => {
      setContentLoading(true);
      try {
        const data = await getWikiPageContent(selectedProjectId, selectedPage.slug);
        setPageContent(data.content);
      } catch (error) {
        setPageContent('Error cargando el contenido de la página.');
      } finally {
        setContentLoading(false);
      }
    };
    fetchContent();
  }, [selectedProjectId, selectedPage]);

  return (
    <div className="documentation-container">
      {/* Panel Izquierdo: Navegación */}
      <aside className="doc-sidebar">
        <h3>📚 Proyectos</h3>
        <select 
          className="project-selector"
          value={selectedProjectId || ''} 
          onChange={(e) => setSelectedProjectId(Number(e.target.value))}
        >
          {projects.map(p => (
            <option key={p.id} value={p.id}>{p.name}</option>
          ))}
        </select>

        <h4 className="mt-4">Páginas</h4>
        {loading ? (
          <p>Cargando índice...</p>
        ) : (
          <ul className="wiki-nav-list">
            {pages.map(page => (
              <li 
                key={page.slug} 
                className={selectedPage?.slug === page.slug ? 'active' : ''}
                onClick={() => setSelectedPage(page)}
              >
                {page.title}
              </li>
            ))}
            {pages.length === 0 && <li className="empty-msg">No hay páginas wiki.</li>}
          </ul>
        )}
      </aside>

      {/* Panel Derecho: Contenido */}
      <main className="doc-content">
        {contentLoading ? (
          <div className="loading-spinner">Cargando contenido...</div>
        ) : selectedPage ? (
          <article className="markdown-body">
            <h1>{selectedPage.title}</h1>
            <div className="meta-info">
               Última edición: {new Date(selectedPage.created_at).toLocaleDateString()}
            </div>
            <hr />
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {pageContent}
            </ReactMarkdown>
          </article>
        ) : (
          <div className="empty-state">Seleccione un proyecto y una página.</div>
        )}
      </main>
    </div>
  );
}