import React, { useEffect, useRef, useState } from 'react';
import cytoscape, { Core } from 'cytoscape';
import { CYTOSCAPE_THEME, transformScopeToCytoscape } from '../utils/cytoscapeStyles';
import { GraphScopeData } from '../types';
import { Maximize2, ZoomIn, ZoomOut, RefreshCw, Eye } from 'lucide-react';

interface GraphCanvasProps {
  runId: string;
  scope: 'run' | 'atlas' | 'domain' | 'agent';
  scopeData?: GraphScopeData | null;
  onScopeChange: (scope: 'run' | 'atlas' | 'domain' | 'agent') => void;
  onSelectNode: (nodeId: string, nodeType: string) => void;
  highlightedIds?: string[];
  isLoading?: boolean;
}

export const GraphCanvas: React.FC<GraphCanvasProps> = ({
  runId,
  scope,
  scopeData,
  onScopeChange,
  onSelectNode,
  highlightedIds = [],
  isLoading = false,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const [nodeCount, setNodeCount] = useState(0);
  const [edgeCount, setEdgeCount] = useState(0);

  // Initialize Cytoscape core
  useEffect(() => {
    if (!containerRef.current) return;

    const cy = cytoscape({
      container: containerRef.current,
      style: CYTOSCAPE_THEME,
      layout: {
        name: 'cose',
        animate: false,
        randomize: false,
        componentSpacing: 60,
        nodeOverlap: 20,
        padding: 30,
      },
      minZoom: 0.2,
      maxZoom: 3.5,
      wheelSensitivity: 0.2,
    });

    cy.on('tap', 'node', (evt) => {
      const node = evt.target;
      const id = node.id();
      const type = node.data('type') || 'Unknown';
      onSelectNode(id, type);
    });

    cy.on('tap', (evt) => {
      if (evt.target === cy) {
        onSelectNode('', '');
      }
    });

    cyRef.current = cy;

    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  }, []);

  // Update Cytoscape elements when scopeData changes
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;

    cy.elements().remove();

    if (scopeData && scopeData.nodes && scopeData.nodes.length > 0) {
      const elements = transformScopeToCytoscape(scopeData);
      cy.add(elements);

      setNodeCount(scopeData.nodes.length);
      setEdgeCount(scopeData.edges ? scopeData.edges.length : 0);

      const layout = cy.layout({
        name: 'cose',
        animate: true,
        animationDuration: 400,
        randomize: false,
        padding: 40,
        nodeRepulsion: () => 4500,
        idealEdgeLength: () => 70,
      });
      layout.run();
    } else {
      setNodeCount(0);
      setEdgeCount(0);
    }
  }, [scopeData]);

  // Apply node highlights when highlightedIds changes
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;

    cy.batch(() => {
      cy.nodes().removeClass('highlighted');
      cy.edges().removeClass('highlighted');

      if (highlightedIds.length > 0) {
        const idSet = new Set(highlightedIds);
        cy.nodes().forEach((n) => {
          if (idSet.has(n.id())) {
            n.addClass('highlighted');
          }
        });

        // Also highlight edges connecting highlighted nodes
        cy.edges().forEach((e) => {
          if (idSet.has(e.source().id()) && idSet.has(e.target().id())) {
            e.addClass('highlighted');
          }
        });
      }
    });
  }, [highlightedIds]);

  const handleZoomIn = () => {
    if (cyRef.current) cyRef.current.zoom(cyRef.current.zoom() * 1.25);
  };

  const handleZoomOut = () => {
    if (cyRef.current) cyRef.current.zoom(cyRef.current.zoom() * 0.8);
  };

  const handleFit = () => {
    if (cyRef.current) cyRef.current.fit(undefined, 30);
  };

  const handleRelayout = () => {
    if (cyRef.current) {
      cyRef.current
        .layout({
          name: 'cose',
          animate: true,
          animationDuration: 300,
          padding: 30,
        })
        .run();
    }
  };

  return (
    <div
      style={{
        position: 'relative',
        width: '100%',
        height: '100%',
        background: 'var(--bg-canvas)',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}
    >
      {/* Top Scope Toolbar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '10px 16px',
          background: 'rgba(13, 17, 23, 0.9)',
          backdropFilter: 'blur(8px)',
          borderBottom: '1px solid var(--border-default)',
          zIndex: 10,
        }}
      >
        {/* Scope Tabs */}
        <div style={{ display: 'flex', gap: '6px' }}>
          {(['run', 'atlas', 'domain', 'agent'] as const).map((sc) => (
            <button
              key={sc}
              onClick={() => onScopeChange(sc)}
              style={{
                padding: '4px 12px',
                fontSize: '12px',
                fontWeight: 600,
                borderRadius: '6px',
                cursor: 'pointer',
                border: '1px solid',
                borderColor: scope === sc ? 'var(--accent-blue)' : 'var(--border-default)',
                background: scope === sc ? 'rgba(88, 166, 255, 0.15)' : 'var(--bg-panel)',
                color: scope === sc ? 'var(--accent-blue)' : 'var(--text-secondary)',
                transition: 'all 0.15s ease',
                textTransform: 'capitalize',
              }}
            >
              {sc} Slice
            </button>
          ))}
        </div>

        {/* Graph Stats & Canvas Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '11px',
              color: 'var(--text-muted)',
              display: 'flex',
              gap: '8px',
            }}
          >
            <span>Nodes: <strong style={{ color: 'var(--text-primary)' }}>{nodeCount}</strong></span>
            <span>Edges: <strong style={{ color: 'var(--text-primary)' }}>{edgeCount}</strong></span>
          </div>

          <div style={{ display: 'flex', gap: '4px' }}>
            <button className="btn" onClick={handleZoomIn} title="Zoom In" style={{ padding: '4px 8px' }}>
              <ZoomIn size={14} />
            </button>
            <button className="btn" onClick={handleZoomOut} title="Zoom Out" style={{ padding: '4px 8px' }}>
              <ZoomOut size={14} />
            </button>
            <button className="btn" onClick={handleFit} title="Fit to Screen" style={{ padding: '4px 8px' }}>
              <Maximize2 size={14} />
            </button>
            <button className="btn" onClick={handleRelayout} title="Relayout Graph" style={{ padding: '4px 8px' }}>
              <RefreshCw size={14} />
            </button>
          </div>
        </div>
      </div>

      {/* Main Cytoscape Canvas */}
      <div
        ref={containerRef}
        style={{
          flex: 1,
          width: '100%',
          height: '100%',
          outline: 'none',
        }}
      />

      {/* Loading Overlay */}
      {isLoading && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            background: 'rgba(9, 13, 19, 0.7)',
            backdropFilter: 'blur(4px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 20,
            color: 'var(--accent-blue)',
            fontFamily: 'var(--font-mono)',
            fontSize: '13px',
            gap: '8px',
          }}
        >
          <RefreshCw size={16} className="pulse" />
          Loading {scope} graph slice...
        </div>
      )}

      {/* Empty State */}
      {!isLoading && nodeCount === 0 && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--text-muted)',
            gap: '8px',
            pointerEvents: 'none',
          }}
        >
          <Eye size={28} />
          <span style={{ fontSize: '13px' }}>No graph nodes loaded in this scope yet.</span>
          <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
            Start a live run or step through the replay to populate graph state.
          </span>
        </div>
      )}
    </div>
  );
};
