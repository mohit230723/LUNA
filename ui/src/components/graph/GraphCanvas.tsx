import {
  useRef,
  useEffect,
  useState,
  useImperativeHandle,
  forwardRef,
} from 'react';
import cytoscape, { Core, NodeSingular } from 'cytoscape';
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
  fit: (padding?: number) => void;
  exportPng: () => string | null;
  focusNode: (id: string, pulse?: boolean) => void;
  resetToOverview: () => void;
  cy: () => Core | null;
}

export interface GraphCanvasProps {
  elements: ElementsDefinition;
  mode: 'overview' | 'tour';
  stepIndex: number | null; // null for overview, 0 for START, 1..N for steps
  steps: TraceStep[];
  layoutType?: LayoutType;
  hideContext?: boolean;
  searchQuery?: string;
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
  fullName?: string;
}

export const GraphCanvas = forwardRef<GraphCanvasHandle, GraphCanvasProps>(
  (
    {
      elements,
      mode,
      stepIndex,
      steps,
      layoutType = 'layered',
      hideContext = false,
      searchQuery = '',
      truncated = false,
      totalNodeCount = 0,
      onSelectNode,
      onExpandNode,
    },
    ref
  ) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const cyRef = useRef<Core | null>(null);
    const lastFocusedNodeId = useRef<string | null>(null);
    const [tooltip, setTooltip] = useState<TooltipData | null>(null);

    // Imperative methods for parent
    useImperativeHandle(ref, () => ({
      fit: (padding = 60) => {
        if (!cyRef.current) return;
        const visibleEles = cyRef.current.elements(':visible');
        cyRef.current.animate(
          { fit: { eles: visibleEles, padding } },
          { duration: 400, easing: 'ease-in-out-cubic' }
        );
      },
      exportPng: () => {
        if (!cyRef.current) return null;
        return cyRef.current.png({ full: true, bg: '#080808', scale: 2 });
      },
      focusNode: (id: string, pulse = false) => {
        if (!cyRef.current) return;
        const cy = cyRef.current;
        const node = cy.$id(id);
        if (node.length > 0) {
          cy.elements().unselect();
          node.select();

          const prefersReducedMotion =
            typeof window !== 'undefined' &&
            window.matchMedia('(prefers-reduced-motion: reduce)').matches;

          if (pulse) {
            node.css('underlay-color', '#ffffff');
            node.css('underlay-opacity', 0.25);
            node.css('underlay-padding', '12px');
            setTimeout(() => {
              node.removeStyle();
            }, 600);
          }

          if (prefersReducedMotion) {
            cy.center(node);
          } else {
            cy.animate({
              center: { eles: node },
              duration: 350,
              easing: 'ease-in-out-cubic',
            });
          }
        }
      },
      resetToOverview: () => {
        const cy = cyRef.current;
        if (!cy) return;
        const prefersReducedMotion =
          typeof window !== 'undefined' &&
          window.matchMedia('(prefers-reduced-motion: reduce)').matches;

        // Clear all tour classes
        cy.elements().removeClass(
          'current-tour-node visited-tour-node visited-tour-edge active-tour-edge dimmed'
        );

        const visibleEles = cy.elements(':visible');
        if (prefersReducedMotion) {
          cy.fit(visibleEles, 60);
        } else {
          cy.stop(true, true);
          cy.animate(
            { fit: { eles: visibleEles, padding: 60 } },
            { duration: 700, easing: 'ease-in-out-cubic' }
          );
        }
      },
      cy: () => cyRef.current,
    }));

    // First step 'from' node for radial layout centering
    const firstStepFromId = steps.length > 0 && steps[0] ? steps[0].from : null;

    // Initialize Cytoscape
    useEffect(() => {
      if (!containerRef.current) return;

      const prefersReducedMotion =
        typeof window !== 'undefined' &&
        window.matchMedia('(prefers-reduced-motion: reduce)').matches;

      const initialLayout = getLayoutOptions(layoutType, firstStepFromId, prefersReducedMotion);

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

      // Hover tooltip & edge label display
      cy.on('mouseover', 'node', (evt) => {
        const node = evt.target as NodeSingular;
        const pos = node.renderedPosition();
        const data = node.data();
        const fullName = (data.props?.name as string) || (data.name as string) || data.id;

        // Show connected edge labels on hover
        node.connectedEdges().addClass('show-label');

        setTooltip({
          x: pos.x + 15,
          y: pos.y + 15,
          id: data.id,
          label: data.label || 'Entity',
          fullName,
        });
      });

      cy.on('mouseout', 'node', (evt) => {
        const node = evt.target as NodeSingular;
        node.connectedEdges().removeClass('show-label');
        setTooltip(null);
      });

      // ResizeObserver to automatically resize canvas on layout shift
      const ro = new ResizeObserver(() => {
        cy.resize();
      });
      ro.observe(containerRef.current);

      // Fit to viewport initially with 60px padding
      setTimeout(() => {
        if (cyRef.current) {
          cyRef.current.fit(cyRef.current.elements(':visible'), 60);
        }
      }, 50);

      return () => {
        ro.disconnect();
        cy.destroy();
        cyRef.current = null;
      };
    }, []);

    // Update elements when props change in overview mode
    useEffect(() => {
      const cy = cyRef.current;
      if (!cy) return;

      const prefersReducedMotion =
        typeof window !== 'undefined' &&
        window.matchMedia('(prefers-reduced-motion: reduce)').matches;

      cy.json({ elements });

      if (mode === 'overview') {
        applyLayout(cy, layoutType, firstStepFromId, prefersReducedMotion);
      }
    }, [elements, layoutType, mode, firstStepFromId]);

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

    // Handle search highlight
    useEffect(() => {
      const cy = cyRef.current;
      if (!cy || !searchQuery.trim()) return;

      const q = searchQuery.toLowerCase().trim();
      cy.elements().unselect();
      const matched = cy.nodes().filter((n) => {
        const id = n.id().toLowerCase();
        const label = (n.data('label') || '').toLowerCase();
        const name = (n.data('name') || n.data('displayName') || '').toLowerCase();
        return id.includes(q) || label.includes(q) || name.includes(q);
      });

      if (matched.length > 0) {
        matched.select();
        const prefersReducedMotion =
          typeof window !== 'undefined' &&
          window.matchMedia('(prefers-reduced-motion: reduce)').matches;

        // Brief white underlay pulse
        matched.css('underlay-color', '#ffffff');
        matched.css('underlay-opacity', 0.25);
        matched.css('underlay-padding', '12px');
        setTimeout(() => {
          matched.removeStyle();
        }, 600);

        if (prefersReducedMotion) {
          cy.center(matched);
        } else {
          cy.animate({
            center: { eles: matched },
            duration: 300,
            easing: 'ease-in-out-cubic',
          });
        }
      }
    }, [searchQuery]);

    // TOUR MODE: Camera animation, dimming, and stop highlighting
    useEffect(() => {
      const cy = cyRef.current;
      if (!cy) return;

      if (mode !== 'tour' || stepIndex === null || steps.length === 0) {
        // Clear tour highlights when in overview
        cy.elements().removeClass(
          'current-tour-node visited-tour-node visited-tour-edge active-tour-edge dimmed'
        );
        return;
      }

      const prefersReducedMotion =
        typeof window !== 'undefined' &&
        window.matchMedia('(prefers-reduced-motion: reduce)').matches;

      // Identify focus target node ID
      let targetNodeId: string;
      if (stepIndex === 0) {
        const firstStep = steps[0];
        if (!firstStep) return;
        targetNodeId = firstStep.from;
      } else {
        const currentStep = steps[stepIndex - 1];
        if (!currentStep) return;
        targetNodeId = currentStep.focus || currentStep.to;
      }

      const targetNode = cy.$id(targetNodeId);
      if (targetNode.length === 0) return;

      // Visited nodes: start node + all 'to' nodes up to stepIndex - 1
      const visitedNodeIds = new Set<string>();
      const firstStep = steps[0];
      if (firstStep) visitedNodeIds.add(firstStep.from);
      for (let i = 1; i <= stepIndex && i <= steps.length; i++) {
        const prevStep = steps[i - 1];
        if (prevStep) visitedNodeIds.add(prevStep.to);
      }

      // Visited edges: all steps walked up to stepIndex - 1
      const visitedEdges = cy.edges().filter((e) => {
        const s = e.source().id();
        const t = e.target().id();
        for (let i = 0; i < stepIndex && i < steps.length; i++) {
          const st = steps[i];
          if (st && ((s === st.from && t === st.to) || (s === st.to && t === st.from))) {
            return true;
          }
        }
        return false;
      });

      // Active edge (current transition edge for stepIndex > 0)
      const activeEdge =
        stepIndex > 0
          ? cy.edges().filter((e) => {
              const cur = steps[stepIndex - 1];
              if (!cur) return false;
              const s = e.source().id();
              const t = e.target().id();
              return (s === cur.from && t === cur.to) || (s === cur.to && t === cur.from);
            })
          : cy.collection();

      // Apply classes
      cy.elements().removeClass(
        'current-tour-node visited-tour-node visited-tour-edge active-tour-edge dimmed'
      );

      // Current focus node
      targetNode.addClass('current-tour-node');

      // Visited nodes (excluding current target node)
      cy.nodes().forEach((n) => {
        if (n.id() !== targetNodeId && visitedNodeIds.has(n.id())) {
          n.addClass('visited-tour-node');
        } else if (n.id() !== targetNodeId) {
          n.addClass('dimmed');
        }
      });

      // Visited & active edges
      visitedEdges.addClass('visited-tour-edge');
      activeEdge.addClass('active-tour-edge');

      // Dim non-visited edges
      cy.edges().forEach((e) => {
        if (!visitedEdges.contains(e) && !activeEdge.contains(e)) {
          e.addClass('dimmed');
        }
      });

      // Calculate camera animation
      const nodeSizePx = targetNode.numericStyle('width') || 40;
      const z = Math.min(3.2, Math.max(1.6, 120 / nodeSizePx));

      // Measure distance from previous position
      let duration = 700;
      if (lastFocusedNodeId.current) {
        const prevNode = cy.$id(lastFocusedNodeId.current);
        if (prevNode.length > 0) {
          const p1 = prevNode.renderedPosition();
          const p2 = targetNode.renderedPosition();
          const distPx = Math.hypot(p2.x - p1.x, p2.y - p1.y);
          duration = Math.min(1100, Math.max(600, Math.round(500 + distPx * 0.6)));
        }
      }
      lastFocusedNodeId.current = targetNodeId;

      if (prefersReducedMotion) {
        cy.center(targetNode);
        cy.zoom(z);
      } else {
        // Stop any running camera animation before starting the next
        cy.stop(true, true);
        cy.animate(
          {
            center: { eles: targetNode },
            zoom: z,
          },
          {
            duration,
            easing: 'ease-in-out-cubic',
          }
        );
      }
    }, [mode, stepIndex, steps]);

    return (
      <div className={styles.wrapper}>
        <div
          ref={containerRef}
          className={styles.cyContainer}
          aria-label={`Graph canvas with ${elements.nodes?.length || 0} nodes and ${steps.length} traversal steps`}
        />

        {/* Truncation Badge */}
        {truncated && (
          <div className={styles.truncationBadge}>
            Showing 400 of {totalNodeCount || 400}+ nodes
          </div>
        )}

        {/* Hover Tooltip */}
        {tooltip && (
          <div
            className={styles.tooltip}
            style={{ left: `${tooltip.x}px`, top: `${tooltip.y}px` }}
          >
            <div className={styles.tooltipId}>{tooltip.id}</div>
            <div className={styles.tooltipName}>{tooltip.fullName || tooltip.label}</div>
            <div className={styles.tooltipType}>{tooltip.label.toUpperCase()}</div>
          </div>
        )}
      </div>
    );
  }
);

function getLayoutOptions(
  layoutType: LayoutType,
  firstStepFromId: string | null,
  reducedMotion: boolean
): cytoscape.LayoutOptions {
  if (layoutType === 'radial') {
    return {
      name: 'concentric',
      concentric: (node: NodeSingular) => {
        if (firstStepFromId && node.id() === firstStepFromId) return 100;
        return 10;
      },
      levelWidth: () => 1,
      minNodeSpacing: 70,
      animate: !reducedMotion,
      animationDuration: 300,
      padding: 60,
    } as any;
  }
  if (layoutType === 'force') {
    return {
      name: 'cose',
      nodeRepulsion: () => 12000,
      idealEdgeLength: () => 140,
      animate: !reducedMotion,
      animationDuration: 300,
      padding: 60,
    } as any;
  }
  // Layered (dagre)
  return {
    name: 'dagre',
    rankDir: 'LR',
    ranker: 'network-simplex',
    nodeSep: 70,
    rankSep: 170,
    edgeSep: 20,
    spacingFactor: 1.2,
    animate: !reducedMotion,
    animationDuration: 300,
    padding: 60,
  } as any;
}

function applyLayout(
  cy: Core,
  layoutType: LayoutType,
  firstStepFromId: string | null,
  reducedMotion: boolean
) {
  try {
    const layoutOptions = getLayoutOptions(layoutType, firstStepFromId, reducedMotion);
    cy.layout(layoutOptions).run();
  } catch {
    // Graceful fallback for test/headless environments
  }
}
