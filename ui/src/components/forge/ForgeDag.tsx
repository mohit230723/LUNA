import React, { useEffect, useMemo, useRef } from 'react';
import cytoscape from 'cytoscape';
import type { Core, ElementDefinition, StylesheetStyle } from 'cytoscape';
import dagre from 'cytoscape-dagre';
import type { ForgeTask } from '../../api/contract';
import './forge.css';

// Register the dagre layout once (GraphCanvas may already have done so).
let dagreRegistered = false;
function ensureDagre() {
  if (dagreRegistered) return;
  try {
    cytoscape.use(dagre);
  } catch {
    // already registered by another module
  }
  dagreRegistered = true;
}

// Fallbacks are the Hyperstudio token values the forge.css variables map onto.
const FALLBACK: Record<string, string> = {
  '--forge-status-pending': '#474747',
  '--forge-status-ready': '#9c9c9c',
  '--forge-status-claimed': '#6f6759',
  '--forge-status-stalled': '#c1c1c1',
  '--forge-status-done': '#f3f3f3',
  '--forge-node-bg': '#080808',
  '--forge-node-text': '#f3f3f3',
  '--forge-edge': '#474747',
};

function cssVar(name: string): string {
  if (typeof window === 'undefined' || typeof getComputedStyle !== 'function') return FALLBACK[name]!;
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v && !v.startsWith('var(') ? v : FALLBACK[name]!;
}

function buildStyle(): StylesheetStyle[] {
  const status = (s: string, extra: Record<string, unknown> = {}): StylesheetStyle => ({
    selector: `node.${s}`,
    style: { 'border-color': cssVar(`--forge-status-${s}`), ...extra } as StylesheetStyle['style'],
  });
  return [
    {
      selector: 'node',
      style: {
        shape: 'round-rectangle',
        width: 172,
        height: 54,
        'background-color': cssVar('--forge-node-bg'),
        'border-width': 1,
        'border-color': cssVar('--forge-status-pending'),
        color: cssVar('--forge-node-text'),
        label: 'data(label)',
        'text-wrap': 'wrap',
        'text-max-width': '156px',
        'text-valign': 'center',
        'text-halign': 'center',
        'line-height': 1.45,
        'font-family': 'IBM Plex Mono, monospace',
        'font-size': 11,
        'overlay-opacity': 0,
        'transition-property': 'border-color, border-width, opacity',
        'transition-duration': 250,
      },
    },
    status('pending', { opacity: 0.65, 'border-style': 'dashed' }),
    status('ready', { 'border-width': 1.5 }),
    status('claimed', {
      'border-width': 2,
      'underlay-color': cssVar('--forge-status-claimed'),
      'underlay-opacity': 0.14,
      'underlay-padding': 7,
      'underlay-shape': 'round-rectangle',
    }),
    status('stalled', { 'border-style': 'dotted', 'border-width': 2 }),
    status('done', {
      'border-width': 1.5,
      'background-color': '#212121',
      'underlay-color': cssVar('--forge-status-done'),
      'underlay-opacity': 0.06,
      'underlay-padding': 6,
      'underlay-shape': 'round-rectangle',
    }),
    { selector: 'node.selected', style: { 'border-width': 3 } },
    {
      selector: 'edge',
      style: {
        width: 1.4,
        'line-color': cssVar('--forge-edge'),
        'target-arrow-color': cssVar('--forge-edge'),
        'target-arrow-shape': 'triangle',
        'target-distance-from-node': 4,
        'arrow-scale': 1.1,
        'curve-style': 'bezier',
      },
    },
  ];
}

export interface ForgeDagProps {
  tasks: ForgeTask[];
  selectedTaskId: string | null;
  onSelect: (taskId: string) => void;
}

export const ForgeDag: React.FC<ForgeDagProps> = ({ tasks, selectedTaskId, onSelect }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;

  // Rebuild only when the graph content (ids, edges, labels, statuses) changes.
  const elements = useMemo<ElementDefinition[]>(() => {
    const ids = new Set(tasks.map((t) => t.task_id));
    const nodes: ElementDefinition[] = tasks.map((t) => ({
      data: { id: t.task_id, label: `${t.title || t.task_id}\n${t.status}` },
      classes: t.status,
    }));
    const edges: ElementDefinition[] = tasks.flatMap((t) =>
      t.depends_on
        .filter((d) => ids.has(d))
        .map((d) => ({ data: { id: `${d}->${t.task_id}`, source: d, target: t.task_id } }))
    );
    return [...nodes, ...edges];
  }, [tasks]);
  const signature = JSON.stringify(elements);

  useEffect(() => {
    if (!containerRef.current) return;
    ensureDagre();
    const cy = cytoscape({
      container: containerRef.current,
      elements: JSON.parse(signature) as ElementDefinition[],
      style: buildStyle(),
      layout: { name: 'dagre', rankDir: 'LR', nodeSep: 28, rankSep: 76 } as cytoscape.LayoutOptions,
      userZoomingEnabled: true,
      boxSelectionEnabled: false,
      autoungrabify: true,
    });
    cy.on('tap', 'node', (evt) => onSelectRef.current(evt.target.id()));
    cyRef.current = cy;
    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  }, [signature]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.nodes().removeClass('selected');
    if (selectedTaskId) cy.getElementById(selectedTaskId).addClass('selected');
  }, [selectedTaskId, signature]);

  const done = tasks.filter((t) => t.status === 'done').length;
  return (
    <div
      ref={containerRef}
      className="forge-dag"
      role="img"
      aria-label={`Task dependency graph: ${done} of ${tasks.length} tasks done. Task details are listed below.`}
    />
  );
};

export default ForgeDag;
