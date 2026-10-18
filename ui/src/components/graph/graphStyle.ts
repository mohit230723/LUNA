import type { StylesheetStyle } from 'cytoscape';

// Hyperstudio Cytoscape stylesheet strictly compliant with Part 5.2 and 5.3 specifications
export const cytoscapeStyles: StylesheetStyle[] = [
  // Core Node base
  {
    selector: 'node',
    style: {
      'font-family': 'IBM Plex Mono, monospace',
      'font-size': '12px',
      'color': '#f3f3f3',
      'text-valign': 'bottom',
      'text-halign': 'center',
      'text-margin-y': 10,
      'text-wrap': 'wrap',
      'text-max-width': '110px',
      'text-background-color': '#101010',
      'text-background-opacity': 0.9,
      'text-background-padding': '3px',
      'text-background-shape': 'roundrectangle',
      'min-zoomed-font-size': 8,
      'z-index-compare': 'manual',
      'z-index': 10,
      'border-width': '1px',
      'border-color': '#474747',
      'background-color': '#080808',
      'width': '40px',
      'height': '40px',
      'overlay-opacity': 0,
      'content': 'data(displayName)',
      'transition-property': 'opacity, border-color, border-width, underlay-opacity',
      'transition-duration': 0.3,
    },
  },

  // Customer / Person: 44px, diamond shape
  {
    selector: 'node[type = "Customer"], node[type = "customer"], node[type = "Person"], node[type = "person"]',
    style: {
      'shape': 'diamond',
      'background-color': '#9c9c9c',
      'border-color': '#474747',
      'color': '#f3f3f3',
      'width': '44px',
      'height': '44px',
    },
  },

  // Organization
  {
    selector: 'node[type = "Organization"], node[type = "organization"], node[type = "Org"]',
    style: {
      'shape': 'round-rectangle',
      'background-color': '#212121',
      'border-color': '#474747',
      'color': '#f3f3f3',
      'width': '42px',
      'height': '38px',
    },
  },

  // Entity (Phone, Address, BankAccount, Provider, InsuranceClaim): Carbon fill, Graphite border, ellipse
  {
    selector: 'node[type = "entity"], node[type = "Entity"], node[type = "Phone"], node[type = "Address"], node[type = "BankAccount"], node[type = "Account"], node[type = "Provider"], node[type = "InsuranceClaim"]',
    style: {
      'shape': 'ellipse',
      'background-color': '#080808',
      'border-color': '#212121',
      'color': '#f3f3f3',
      'width': '40px',
      'height': '40px',
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

  // Superseded finding
  {
    selector: 'node[status = "superseded"], node.superseded',
    style: {
      'opacity': 0.3,
      'border-style': 'dashed',
      'border-color': '#9c9c9c',
      'background-color': '#212121',
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

  // Path Nodes: 2.5px Signal White border
  {
    selector: 'node[?on_path], node.on-path',
    style: {
      'border-color': '#ffffff',
      'border-width': '2.5px',
      'opacity': 1.0,
      'z-index': 50,
    },
  },

  // Non-path nodes: 70% opacity in Overview
  {
    selector: 'node.non-path',
    style: {
      'opacity': 0.7,
    },
  },

  // Context Nodes: 40% opacity in Overview
  {
    selector: 'node[?context], node.context',
    style: {
      'opacity': 0.4,
    },
  },

  // Selected Node: 2px Signal White border
  {
    selector: 'node:selected, node.selected',
    style: {
      'border-color': '#ffffff',
      'border-width': '2.5px',
      'z-index': 60,
    },
  },

  // TOUR MODE HIGHLIGHTS
  // Current tour stop focus node: 3px white border, underlay, 16px label
  {
    selector: 'node.current-tour-node',
    style: {
      'border-color': '#ffffff',
      'border-width': '3px',
      'underlay-color': '#f3f3f3',
      'underlay-opacity': 0.12,
      'underlay-padding': '10px',
      'font-size': '16px',
      'opacity': 1.0,
      'z-index': 100,
    },
  },

  // Visited tour nodes: 2px white border
  {
    selector: 'node.visited-tour-node',
    style: {
      'border-color': '#ffffff',
      'border-width': '2px',
      'opacity': 1.0,
      'z-index': 70,
    },
  },

  // Visited tour edges: white line, width 3
  {
    selector: 'edge.visited-tour-edge',
    style: {
      'line-color': '#ffffff',
      'target-arrow-color': '#ffffff',
      'width': '3px',
      'opacity': 1.0,
      'z-index': 80,
    },
  },

  // Tour active transitioning edge
  {
    selector: 'edge.active-tour-edge',
    style: {
      'line-color': '#ffffff',
      'target-arrow-color': '#ffffff',
      'width': '3px',
      'opacity': 1.0,
      'z-index': 90,
    },
  },

  // Dimmed elements in tour
  {
    selector: '.dimmed',
    style: {
      'opacity': 0.22,
    },
  },

  // Edges base: 1.5px, bezier, control-point-step-size 40
  {
    selector: 'edge',
    style: {
      'width': '1.5px',
      'line-color': '#474747',
      'target-arrow-color': '#474747',
      'target-arrow-shape': 'triangle',
      'arrow-scale': 1.0,
      'curve-style': 'bezier',
      'control-point-step-size': 40,
      'font-family': 'IBM Plex Mono, monospace',
      'font-size': '10px',
      'color': '#9c9c9c',
      'text-rotation': 'autorotate',
      'text-margin-y': -8,
      'text-background-color': '#101010',
      'text-background-opacity': 0.9,
      'text-background-padding': '2px',
      'text-background-shape': 'roundrectangle',
      'content': '', // Hidden by default for non-path edges
      'transition-property': 'opacity, line-color, width',
      'transition-duration': 0.3,
    },
  },

  // Edge label shown ONLY for path edges or when adjacent to hovered/selected
  {
    selector: 'edge[?on_path], edge.on-path, edge.show-label',
    style: {
      'content': 'data(label)',
    },
  },

  // Path Edges: 2.5px Signal White
  {
    selector: 'edge[?on_path], edge.on-path',
    style: {
      'width': '2.5px',
      'line-color': '#ffffff',
      'target-arrow-color': '#ffffff',
      'z-index': 40,
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
];
