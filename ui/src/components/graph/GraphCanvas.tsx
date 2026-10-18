import {
  useRef,
  useEffect,
  useState,
  useImperativeHandle,
  forwardRef,
} from 'react';
import cytoscape, { Core, NodeSingular, EdgeSingular } from 'cytoscape';
import dagre from 'cytoscape-dagre';
import { cytoscapeStyles } from './graphStyle';
import type { ElementsDefinition } from 'cytoscape';
import type { TraceNode, TraceStep } from '../../api/contract';
import styles from './GraphCanvas.module.css';

// Register dagre layout once safely
try {
  cytoscape.use(dagre);
} catch {
  // Already registered
}

export type LayoutType = 'layered' | 'radial' | 'force';

export interface GraphCanvasHandle {
  fit: () => void;
  exportPng: () => string | null;
  focusNode: (id: string) => void;
}

export interface GraphCanvasProps {
  elements: ElementsDefinition;
  mode?: 'traversal' | 'blueprint';
  layoutType?: LayoutType;
  hideContext?: boolean;
  searchQuery?: string;
  activeStep?: TraceStep;
  isPlaying?: boolean;
  truncated?: boolean;
  totalNodeCount?: number;
  onSelectNode: (node: TraceNode | null) => void;
  onExpandNode?: (cid: string) => void;
}

interface TooltipData {
  x: number;
  y: number;
  id: string;
  label: string;
  props?: Record<string, unknown>;
}

export const GraphCanvas = forwardRef<GraphCanvasHandle, GraphCanvasProps>(
  (
    {
      elements,
      mode = 'traversal',
      layoutType = 'layered',
      hideContext = false,
      searchQuery = '',
      activeStep,
      isPlaying = false,
      truncated = false,
      totalNodeCount = 0,
      onSelectNode,
      onExpandNode,
    },
    ref
  ) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const cyRef = useRef<Core | null>(null);
    const canvasMarkerRef = useRef<HTMLCanvasElement>(null);
    const animFrameRef = useRef<number | null>(null);
    const [tooltip, setTooltip] = useState<TooltipData | null>(null);

    // Imperative methods for parent
    useImperativeHandle(ref, () => ({
      fit: () => {
        cyRef.current?.fit(undefined, 40);
      },
      exportPng: () => {
        if (!cyRef.current) return null;
        return cyRef.current.png({ full: true, bg: '#101010', scale: 2 });
      },
      focusNode: (id: string) => {
        if (!cyRef.current) return;
        const node = cyRef.current.$id(id);
        if (node.length > 0) {
          cyRef.current.elements().unselect();
          node.select();
          cyRef.current.animate({
            center: { eles: node },
            zoom: 1.2,
            duration: 300,
          });
        }
      },
    }));

    // Initialize cytoscape
    useEffect(() => {
      if (!containerRef.current) return;

      const prefersReducedMotion =
        typeof window !== 'undefined' && typeof window.matchMedia === 'function'
          ? window.matchMedia('(prefers-reduced-motion: reduce)').matches
          : false;

      const initialLayout = getLayoutOptions(layoutType, mode, prefersReducedMotion);

      const cy = cytoscape({
        container: containerRef.current,
        elements,
        style: cytoscapeStyles,
        layout: initialLayout,
        boxSelectionEnabled: true,
        autounselectify: false,
      });

      cyRef.current = cy;

      // Click to select node
      cy.on('tap', 'node', (evt) => {
        const node = evt.target as NodeSingular;
        const data = node.data();
        onSelectNode({
          id: data.id,
          label: data.label,
          props: data,
          context: data.context,
        });
      });

      // Background click unselects
      cy.on('tap', (evt) => {
        if (evt.target === cy) {
          onSelectNode(null);
          setTooltip(null);
        }
      });

      // Double-click to expand neighbors
      let lastTapTime = 0;
      let lastTapNode = '';
      cy.on('tap', 'node', (evt) => {
        const currentTime = new Date().getTime();
        const node = evt.target as NodeSingular;
        const nodeId = node.id();

        if (currentTime - lastTapTime < 300 && lastTapNode === nodeId) {
          onExpandNode?.(nodeId);
        }
        lastTapTime = currentTime;
        lastTapNode = nodeId;
      });

      // Hover tooltip
      cy.on('mouseover', 'node', (evt) => {
        const node = evt.target as NodeSingular;
        const pos = node.renderedPosition();
        const data = node.data();
        setTooltip({
          x: pos.x + 15,
          y: pos.y + 15,
          id: data.id,
          label: data.label,
          props: data,
        });
      });

      cy.on('mouseout', 'node', () => {
        setTooltip(null);
      });

      // Zoom listener: toggle labels at zoom >= 0.5
      cy.on('zoom', () => {
        const z = cy.zoom();
        if (z < 0.5) {
          cy.nodes().style('content', '');
        } else {
          cy.nodes().style('content', 'data(label)');
        }
      });

      // Escape key clears selection
      const handleKeyDown = (e: KeyboardEvent) => {
        if (e.key === 'Escape') {
          cy.elements().unselect();
          onSelectNode(null);
        }
      };
      window.addEventListener('keydown', handleKeyDown);

      // Apply initial layout
      applyLayout(cy, layoutType, mode, prefersReducedMotion);

      return () => {
        window.removeEventListener('keydown', handleKeyDown);
        cy.destroy();
        cyRef.current = null;
      };
    }, []);

    // Update elements when props change
    useEffect(() => {
      const cy = cyRef.current;
      if (!cy) return;

      const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

      // Update elements smoothly
      cy.json({ elements });
      applyLayout(cy, layoutType, mode, prefersReducedMotion);
    }, [elements, layoutType, mode]);

    // Handle hideContext toggle
    useEffect(() => {
      const cy = cyRef.current;
      if (!cy) return;

      if (hideContext) {
        cy.nodes('[?context], .context').style('display', 'none');
      } else {
        cy.nodes('[?context], .context').style('display', 'element');
      }
    }, [hideContext]);

    // Handle searchQuery highlight
    useEffect(() => {
      const cy = cyRef.current;
      if (!cy || !searchQuery.trim()) return;

      const q = searchQuery.toLowerCase().trim();
      cy.elements().unselect();
      const matched = cy.nodes().filter((n) => {
        const id = n.id().toLowerCase();
        const label = (n.data('label') || '').toLowerCase();
        return id.includes(q) || label.includes(q);
      });

      if (matched.length > 0) {
        matched.select();
        cy.animate({
          center: { eles: matched },
          duration: 200,
        });
      }
    }, [searchQuery]);

    // Traveling green pulse marker animation on active step edge
    useEffect(() => {
      const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      if (prefersReducedMotion || !isPlaying || !activeStep || !canvasMarkerRef.current || !cyRef.current) {
        if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
        const ctx = canvasMarkerRef.current?.getContext('2d');
        if (ctx && canvasMarkerRef.current) {
          ctx.clearRect(0, 0, canvasMarkerRef.current.width, canvasMarkerRef.current.height);
        }
        return;
      }

      const cy = cyRef.current;
      const canvas = canvasMarkerRef.current;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      canvas.width = canvas.offsetWidth;
      canvas.height = canvas.offsetHeight;

      // Find active edge
      const edge = cy.edges().filter((e) => {
        const s = e.source().id();
        const t = e.target().id();
        return (
          (s === activeStep.from && t === activeStep.to) ||
          (s === activeStep.to && t === activeStep.from)
        );
      })[0] as EdgeSingular | undefined;

      if (!edge) return;

      let progress = 0;
      let lastTime = performance.now();

      const render = (time: number) => {
        const delta = (time - lastTime) / 1000;
        lastTime = time;

        progress = (progress + delta * 1.5) % 1;

        ctx.clearRect(0, 0, canvas.width, canvas.height);

        const srcPos = edge.source().renderedPosition();
        const tgtPos = edge.target().renderedPosition();

        const x = srcPos.x + (tgtPos.x - srcPos.x) * progress;
        const y = srcPos.y + (tgtPos.y - srcPos.y) * progress;

        // Draw 6px Pulse Green dot with 1px Graphite ring
        ctx.beginPath();
        ctx.arc(x, y, 4, 0, Math.PI * 2);
        ctx.fillStyle = '#98ff38'; // Pulse Green marker dot
        ctx.fill();
        ctx.lineWidth = 1;
        ctx.strokeStyle = '#212121'; // Graphite ring
        ctx.stroke();

        animFrameRef.current = requestAnimationFrame(render);
      };

      animFrameRef.current = requestAnimationFrame(render);

      return () => {
        if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
        ctx.clearRect(0, 0, canvas.width, canvas.height);
      };
    }, [isPlaying, activeStep]);

    return (
      <div className={styles.wrapper}>
        <div ref={containerRef} className={styles.cyContainer} />
        <canvas ref={canvasMarkerRef} className={styles.markerCanvas} />

        {/* Truncation Badge */}
        {truncated && (
          <div className={styles.truncationBadge}>
            Showing 500 of {totalNodeCount || 500}+ nodes
          </div>
        )}

        {/* Hover Tooltip */}
        {tooltip && (
          <div
            className={styles.tooltip}
            style={{ left: `${tooltip.x}px`, top: `${tooltip.y}px` }}
          >
            <div className={styles.tooltipId}>{tooltip.id}</div>
            <div>{tooltip.label}</div>
          </div>
        )}
      </div>
    );
  }
);

function getLayoutOptions(
  layoutType: LayoutType,
  mode: 'traversal' | 'blueprint',
  reducedMotion: boolean
): cytoscape.LayoutOptions {
  if (layoutType === 'radial') {
    return {
      name: 'concentric',
      animate: !reducedMotion,
      animationDuration: 300,
      padding: 40,
    } as any;
  }
  if (layoutType === 'force') {
    return {
      name: 'cose',
      animate: !reducedMotion,
      animationDuration: 300,
      padding: 40,
    } as any;
  }
  return {
    name: 'dagre',
    rankDir: mode === 'blueprint' ? 'TB' : 'LR',
    ranker: 'tight-tree',
    nodeSep: 35,
    edgeSep: 25,
    rankSep: 60,
    animate: !reducedMotion,
    animationDuration: 300,
    padding: 40,
  } as any;
}

function applyLayout(
  cy: Core,
  layoutType: LayoutType,
  mode: 'traversal' | 'blueprint',
  reducedMotion: boolean
) {
  try {
    const layoutOptions = getLayoutOptions(layoutType, mode, reducedMotion);
    cy.layout(layoutOptions).run();
  } catch {
    // Graceful fallback for test/headless environments
  }
}

