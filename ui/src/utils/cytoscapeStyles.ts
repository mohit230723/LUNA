import cytoscape from 'cytoscape';
import { GraphScopeData } from '../types';

export const CYTOSCAPE_THEME: cytoscape.StylesheetStyle[] = [
  {
    selector: 'node',
    style: {
      'background-color': '#161b22',
      'border-width': 2,
      'border-color': '#30363d',
      'label': 'data(label)',
      'color': '#f0f6fc',
      'font-family': 'JetBrains Mono, monospace',
      'font-size': '11px',
      'text-valign': 'center',
      'text-halign': 'center',
      'text-wrap': 'ellipsis',
      'text-max-width': '100px',
      'width': 44,
      'height': 44,
      'transition-property': 'background-color, border-color, width, height, opacity',
      'transition-duration': 0.25,
    },
  },
  {
    selector: 'node[type = "Customer"]',
    style: {
      'shape': 'diamond',
      'width': 50,
      'height': 50,
      'border-color': '#58a6ff',
      'background-color': '#0d1117',
      'font-weight': 'bold',
    },
  },
  {
    selector: 'node[type = "Customer"][status = "seed"]',
    style: {
      'border-color': '#f85149',
      'background-color': 'rgba(248, 81, 73, 0.15)',
    },
  },
  {
    selector: 'node[type = "Finding"]',
    style: {
      'shape': 'round-rectangle',
      'width': 60,
      'height': 34,
    },
  },
  {
    selector: 'node[type = "Finding"][verdict = "suspicious"]',
    style: {
      'border-color': '#f85149',
      'color': '#ff7b72',
      'background-color': 'rgba(248, 81, 73, 0.12)',
    },
  },
  {
    selector: 'node[type = "Finding"][verdict = "benign"]',
    style: {
      'border-color': '#3fb950',
      'color': '#7ee787',
      'background-color': 'rgba(63, 185, 80, 0.12)',
    },
  },
  {
    selector: 'node[type = "Skill"]',
    style: {
      'shape': 'round-tag',
      'border-color': '#39c5cf',
      'color': '#79c0ff',
      'background-color': '#161b22',
    },
  },
  {
    selector: 'node[type = "Action"]',
    style: {
      'shape': 'hexagon',
      'border-color': '#d29922',
      'color': '#e3b341',
      'background-color': 'rgba(210, 153, 34, 0.12)',
      'width': 48,
      'height': 48,
    },
  },
  {
    selector: 'node[status = "superseded"], node[?dimmed]',
    style: {
      'opacity': 0.35,
      'border-color': '#8b949e',
      'color': '#8b949e',
      'background-color': '#21262d',
    },
  },
  {
    selector: 'node[?highlighted]',
    style: {
      'border-width': 4,
      'border-color': '#39c5cf',
      'overlay-color': '#39c5cf',
      'overlay-padding': 6,
      'overlay-opacity': 0.35,
      'width': 58,
      'height': 58,
      'z-index': 99,
    },
  },
  {
    selector: 'node:selected',
    style: {
      'border-width': 3,
      'border-color': '#58a6ff',
      'background-color': '#1f6feb',
      'color': '#ffffff',
    },
  },
  {
    selector: 'edge',
    style: {
      'width': 1.5,
      'line-color': '#30363d',
      'target-arrow-color': '#58a6ff',
      'target-arrow-shape': 'triangle',
      'curve-style': 'bezier',
      'arrow-scale': 0.8,
      'font-family': 'JetBrains Mono, monospace',
      'font-size': '9px',
      'color': '#8b949e',
      'text-rotation': 'autorotate',
      'text-margin-y': -8,
      'opacity': 0.8,
    },
  },
  {
    selector: 'edge[?dashed]',
    style: {
      'line-style': 'dashed',
      'line-color': '#8b949e',
      'opacity': 0.3,
    },
  },
  {
    selector: 'edge[?highlighted]',
    style: {
      'width': 3.5,
      'line-color': '#39c5cf',
      'target-arrow-color': '#39c5cf',
      'opacity': 1,
      'z-index': 98,
    },
  },
];

export function transformScopeToCytoscape(scopeData: GraphScopeData): cytoscape.ElementDefinition[] {
  const elements: cytoscape.ElementDefinition[] = [];

  for (const n of scopeData.nodes || []) {
    const rawId = String(n.id || n.name || '');
    const label = String(n.label || n.name || rawId);
    let type = n.type || 'Entity';
    if (!type || type === 'Entity') {
      if (rawId.startsWith('cust_') || rawId.startsWith('CUST_')) type = 'Customer';
      else if (rawId.startsWith('f_') || rawId.startsWith('finding_')) type = 'Finding';
      else if (rawId.startsWith('act_') || rawId.startsWith('action_')) type = 'Action';
      else if (rawId.startsWith('sk_') || rawId.startsWith('skill_')) type = 'Skill';
      else if (rawId.startsWith('dev_') || rawId.startsWith('DEV_')) type = 'Device';
      else if (rawId.startsWith('ip_') || rawId.startsWith('IP_')) type = 'IP';
    }

    elements.push({
      group: 'nodes',
      data: {
        id: rawId,
        label: label.length > 18 ? label.slice(0, 16) + '...' : label,
        fullLabel: label,
        type: type,
        status: n.status,
        verdict: n.verdict,
        confidence: n.confidence,
        dimmed: n.status === 'superseded',
        properties: n,
      },
    });
  }

  for (let i = 0; i < (scopeData.edges || []).length; i++) {
    const e = scopeData.edges[i];
    const source = String(e.source);
    const target = String(e.target);
    const edgeType = e.type || 'CONNECTED_TO';
    const edgeId = e.id || `edge_${source}_${target}_${i}`;

    elements.push({
      group: 'edges',
      data: {
        id: edgeId,
        source: source,
        target: target,
        label: edgeType,
        type: edgeType,
        dashed: edgeType === 'SUPERSEDES' || e.dashed,
        properties: e,
      },
    });
  }

  return elements;
}
