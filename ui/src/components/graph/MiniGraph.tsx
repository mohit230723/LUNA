import React, { useEffect, useRef } from 'react';
import cytoscape, { ElementsDefinition } from 'cytoscape';
import dagre from 'cytoscape-dagre';
import { cytoscapeStyles } from './graphStyle';
import styles from './MiniGraph.module.css';

try {
  cytoscape.use(dagre);
} catch {
  // Ignored if already registered
}

export interface MiniGraphProps {
  elements: ElementsDefinition;
  height?: number | string;
  className?: string;
  onClick?: () => void;
  direction?: 'LR' | 'TB';
}

export const MiniGraph: React.FC<MiniGraphProps> = ({
  elements,
  height = 180,
  className = '',
  onClick,
  direction = 'LR',
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: cytoscapeStyles,
      layout: {
        name: 'dagre',
        rankDir: direction,
        nodeSep: 25,
        rankSep: 40,
        padding: 16,
      } as cytoscape.LayoutOptions,
      userZoomingEnabled: false,
      userPanningEnabled: false,
      boxSelectionEnabled: false,
      autoungrabify: true,
      autounselectify: true,
    });

    cyRef.current = cy;
    cy.fit(undefined, 16);

    const handleResize = () => {
      cy.resize();
      cy.fit(undefined, 16);
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      cy.destroy();
      cyRef.current = null;
    };
  }, [elements, direction]);

  return (
    <div
      className={`${styles.container} ${className}`}
      style={{ height }}
      onClick={onClick}
      role={onClick ? 'button' : 'img'}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={onClick ? (e) => (e.key === 'Enter' || e.key === ' ') && onClick() : undefined}
      aria-label="Mini Graph visualization"
    >
      <div ref={containerRef} className={styles.canvas} />
    </div>
  );
};
