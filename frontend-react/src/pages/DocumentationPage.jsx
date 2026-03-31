// frontend-react/src/pages/DocumentationPage.jsx
import React, { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { getWikiProjects, getWikiPages, getWikiPageContent, downloadWikiPdf } from '../services/api';
import PageTree from '../components/PageTree';
import './DocumentationPage.css';

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

  const buildTree = (flatPages) => {
    const root =[];
    flatPages.forEach(page => {
      const parts = page.slug.split('/');
      let currentLevel = root;
      parts.forEach((part, index) => {
        const isFile = index === parts.length - 1;
        const nodeTitle = isFile ? page.title : part;
        
        let existing = currentLevel.find(n => n.title === nodeTitle && n.type === (isFile ? 'file' : 'folder'));
        
        if (!existing) {
          existing = {
            id: isFile ? page.slug : parts.slice(0, index + 1).join('/'),
            title: nodeTitle,
            slug: isFile ? page.slug : null,
            type: isFile ? 'file' : 'folder',
            children:[]
          };
          currentLevel.push(existing);
        }
        currentLevel = existing.children;
      });
    });
    return root;
  };

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
        setPages(buildTree(data));
        
        // Seleccionar la página 'home' por defecto si existe
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
          <div className="wiki-nav-list">
            {pages.length > 0 ? (
              <PageTree nodes={pages} onSelectPage={(page) => setSelectedPage(page)} />
            ) : (
              <p className="empty-msg">No hay páginas wiki.</p>
            )}
          </div>
        )}
      </aside>

      {/* Panel Derecho: Contenido */}
      <main className="doc-content">
        {contentLoading ? (
          <div className="loading-spinner">Cargando contenido...</div>
        ) : selectedPage ? (
          <article className="markdown-body">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h1 style={{ margin: 0 }}>{selectedPage.title}</h1>
              <button 
                className="sync-button" 
                style={{ backgroundColor: '#17a2b8', borderColor: '#17a2b8', padding: '0.5rem 1rem' }}
                onClick={() => downloadWikiPdf(selectedProjectId, selectedPage.slug)}
              >
                ⬇️ Descargar PDF
              </button>
            </div>
            {selectedPage.created_at && (
              <div className="meta-info" style={{ marginTop: '0.5rem', color: '#6c757d', fontSize: '0.9rem' }}>
                 Última edición: {new Date(selectedPage.created_at).toLocaleDateString()}
              </div>
            )}
            <hr />
            <ReactMarkdown 
              remarkPlugins={[remarkGfm]}
              components={{
                img: ({node, ...props}) => {
                  return <img {...props} style={{maxWidth: '100%'}} alt={props.alt || ''} />;
                }
              }}
            >
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