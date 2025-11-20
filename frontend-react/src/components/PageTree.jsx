import React, { useState } from 'react';
import './PageTree.css';

const PageTreeNode = ({ node, onSelectPage }) => {
  const [isOpen, setIsOpen] = useState(true);
  const isFolder = node.type === 'folder';

  const handleToggle = () => {
    setIsOpen(!isOpen);
  };

  const handleSelect = () => {
    if (!isFolder) {
      onSelectPage({ slug: node.slug, title: node.title });
    }
  };

  return (
    <div className="tree-node">
      <div className={`node-label ${isFolder ? 'folder' : 'file'}`} onClick={isFolder ? handleToggle : handleSelect}>
        {isFolder && <span>{isOpen ? '▼' : '►'} </span>}
        {node.title}
      </div>
      {isFolder && isOpen && (
        <div className="node-children">
          <PageTree nodes={node.children} onSelectPage={onSelectPage} />
        </div>
      )}
    </div>
  );
};

const PageTree = ({ nodes, onSelectPage }) => (
  <div>
    {nodes.map(node => (
      <PageTreeNode key={node.id} node={node} onSelectPage={onSelectPage} />
    ))}
  </div>
);

export default PageTree;