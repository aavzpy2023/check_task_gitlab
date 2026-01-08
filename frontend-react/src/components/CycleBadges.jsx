import React from 'react';
import './CycleBadges.css';

const Badge = ({ label, days, colorClass }) => {
  // SSS: CORRECCIÓN - Eliminamos la restricción "if (days <= 0)".
  // Ahora mostramos la burbuja incluso si es 0, para confirmar visualización.
  // Solo ocultamos si es undefined o null.
  if (days === undefined || days === null) return null;

  return (
    <div className={`cycle-badge ${colorClass}`} title={`${label}: ${days} días acumulados`}>
      <span className="cb-label">{label}</span>
      <span className="cb-days">{days}d</span>
    </div>
  );
};

const CycleBadges = ({ metrics }) => {
  // Si metrics es null (aún no sincronizado), no renderizamos nada
  if (!metrics) return null;

  return (
    <div className="cycle-badges-container">
      {/* Mostramos siempre las 3 etapas para tener la foto completa */}
      <Badge label="Ejec" days={metrics.execution_days} colorClass="bg-blue" />
      <Badge label="Rev" days={metrics.review_days} colorClass="bg-orange" />
      <Badge label="Func" days={metrics.functional_days} colorClass="bg-green" />
    </div>
  );
};

export default CycleBadges;