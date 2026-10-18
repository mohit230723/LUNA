import type { StylesheetStyle } from 'cytoscape';

// Authoritative Hyperstudio Cytoscape stylesheet
// Strictly uses ONLY allowed colors from Section 3.1
export const cytoscapeStyles: StylesheetStyle[] = [
  // Core Node base
  {
    selector: 'node',
    style: {
      'font-family': 'IBM Plex Mono, monospace',
      'font-size': '11px',
      'color': '#f3f3f3',
      'text-valign': 'center',
      'text-halign': 'center',
      'text-wrap': 'wrap',
      'text-max-width': '80px',
      'border-width': '1px',
      'border-color': '#474747',
      'background-color': '#080808',
      'width': '38px',
      'height': '38px',
      'overlay-opacity': 0,
      'content': 'data(label)',
    },
  },

  // Node types & shapes
  // Customer: Smoke fill, Iron border, diamond
  {
    selector: 'node[type = "customer"], node[type = "Customer"]',
    style: {
      'shape': 'diamond',
      'background-color': '#9c9c9c',
      'border-color': '#474747',
      'color': '#080808',
      'width': '40px',
      'height': '40px',
    },
  },

  // Entity (Phone, Address, BankAccount, Provider, InsuranceClaim): Carbon fill, Graphite border, ellipse
  {
    selector: 'node[type = "entity"], node[type = "Entity"], node[type = "Phone"], node[type = "Address"], node[type = "BankAccount"], node[type = "Provider"], node[type = "InsuranceClaim"]',
    style: {
      'shape': 'ellipse',
      'background-color': '#080808',
      'border-color': '#212121',
      'color': '#f3f3f3',
    },
  },

  // Finding: Chalk fill, round-rectangle
  {
    selector: 'node[type = "finding"], node[type = "Finding"]',
    style: {
      'shape': 'round-rectangle',
      'background-color': '#f3f3f3',
      'border-color': '#c1c1c1',
      'color': '#080808',
      'width': '42px',
      'height': '32px',
    },
  },
  // Superseded finding: 30% opacity + dashed border
  {
    selector: 'node[type = "finding"][status = "superseded"], node.superseded',
    style: {
      'opacity': 0.3,
      'border-style': 'dashed',
      'border-color': '#9c9c9c',
      'background-color': '#212121',
      'color': '#9c9c9c',
    },
  },

  // Agent: Card Slate fill, hexagon
  {
    selector: 'node[type = "agent"], node[type = "Agent"]',
    style: {
      'shape': 'hexagon',
      'background-color': '#3b3d45',
      'border-color': '#474747',
      'color': '#f3f3f3',
      'width': '42px',
      'height': '38px',
    },
  },

  // SkillRef: Iron fill, tag
  {
    selector: 'node[type = "skill"], node[type = "SkillRef"], node[type = "Skill"]',
    style: {
      'shape': 'tag',
      'background-color': '#474747',
      'border-color': '#c1c1c1',
      'color': '#f3f3f3',
      'width': '44px',
      'height': '34px',
    },
  },

  // Action: transparent fill, Compass Gold border, octagon
  {
    selector: 'node[type = "action"], node[type = "Action"]',
    style: {
      'shape': 'octagon',
      'background-color': '#101010',
      'border-color': '#6f6759',
      'color': '#f3f3f3',
      'width': '42px',
      'height': '42px',
    },
  },

  // Component: Card Slate fill, rectangle
  {
    selector: 'node[type = "component"], node[type = "Component"]',
    style: {
      'shape': 'rectangle',
      'background-color': '#3b3d45',
      'border-color': '#474747',
      'color': '#f3f3f3',
      'width': '48px',
      'height': '32px',
    },
  },

  // Contract: Carbon fill, Chalk border, barrel
  {
    selector: 'node[type = "contract"], node[type = "Contract"]',
    style: {
      'shape': 'barrel',
      'background-color': '#080808',
      'border-color': '#f3f3f3',
      'color': '#f3f3f3',
      'width': '44px',
      'height': '36px',
    },
  },

  // Artifact: Graphite fill, rectangle
  {
    selector: 'node[type = "artifact"], node[type = "Artifact"]',
    style: {
      'shape': 'rectangle',
      'background-color': '#212121',
      'border-color': '#474747',
      'color': '#f3f3f3',
      'width': '42px',
      'height': '32px',
    },
  },

  // Requirement: Carbon fill, Smoke border, round-tag
  {
    selector: 'node[type = "requirement"], node[type = "Requirement"]',
    style: {
      'shape': 'round-tag',
      'background-color': '#080808',
      'border-color': '#9c9c9c',
      'color': '#f3f3f3',
      'width': '44px',
      'height': '34px',
    },
  },

  // Violation: dashed Chalk border with "x" label prefix
  {
    selector: 'node[type = "violation"], node[type = "Violation"]',
    style: {
      'shape': 'round-rectangle',
      'background-color': '#080808',
      'border-style': 'dashed',
      'border-color': '#f3f3f3',
      'color': '#f3f3f3',
    },
  },

  // Path Nodes: Signal White border and highlight
  {
    selector: 'node[?on_path], node.on-path',
    style: {
      'border-color': '#ffffff',
      'border-width': '2px',
    },
  },

  // Selected Node: 2px Signal White border
  {
    selector: 'node:selected, node.selected',
    style: {
      'border-color': '#ffffff',
      'border-width': '2px',
    },
  },

  // Context Nodes: dimmed to 35% opacity
  {
    selector: 'node[?context], node.context',
    style: {
      'opacity': 0.35,
    },
  },

  // Edges
  {
    selector: 'edge',
    style: {
      'width': '1px',
      'line-color': '#474747',
      'target-arrow-color': '#474747',
      'target-arrow-shape': 'triangle',
      'arrow-scale': 0.8,
      'curve-style': 'bezier',
      'font-family': 'IBM Plex Mono, monospace',
      'font-size': '10px',
      'color': '#9c9c9c',
      'text-rotation': 'autorotate',
      'text-margin-y': -8,
    },
  },

  // Rejected Edges: dashed Smoke
  {
    selector: 'edge[rel = "REJECTED"], edge.rejected',
    style: {
      'line-style': 'dashed',
      'line-color': '#9c9c9c',
      'target-arrow-color': '#9c9c9c',
    },
  },

  // Path Edges: 2.5px Signal White
  {
    selector: 'edge[?on_path], edge.on-path',
    style: {
      'width': '2.5px',
      'line-color': '#ffffff',
      'target-arrow-color': '#ffffff',
      'z-index': 99,
    },
  },

  // Active / revealed step edge
  {
    selector: 'edge.active-step',
    style: {
      'width': '2.5px',
      'line-color': '#ffffff',
      'target-arrow-color': '#ffffff',
    },
  },
];
