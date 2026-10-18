import React, { useReducer, useEffect, useState, useRef, useMemo, useCallback } from 'react';
import { ArrowLeft } from 'lucide-react';
import { Badge } from '../ui/Badge';
import { GhostButton } from '../ui/GhostButton';
import { Spinner } from '../ui/Spinner';
import { ErrorState } from '../ui/ErrorState';
import { StepList } from './StepList';
import { GraphCanvas, GraphCanvasHandle, LayoutType } from './GraphCanvas';
import { StepCard } from './StepCard';
import { NodeDetail } from './NodeDetail';
import { Scrubber } from './Scrubber';
import { Legend } from './Legend';
import { toElements } from './toElements';
import { traceReducer, INITIAL_TRACE_STATE } from '../../state/traceReducer';
import { getApi } from '../../api';
import type { TraceResponse, TraceNode, TraceEdge, FindingInfo } from '../../api/contract';
import styles from './TraceView.module.css';

export interface TraceViewProps {
  runId: string;
  pack?: 'investigate' | 'build';
  findings?: FindingInfo[];
  initialFocusedCid?: string;
  onBack: () => void;
  onWhy?: (target: string) => void;
}

export const TraceView: React.FC<TraceViewProps> = ({
  runId,
  pack,
  findings = [],
  initialFocusedCid,
  onBack,
  onWhy,
}) => {
  const [traceData, setTraceData] = useState<TraceResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [state, dispatch] = useReducer(traceReducer, INITIAL_TRACE_STATE);
  const [selectedNode, setSelectedNode] = useState<TraceNode | null>(null);
  const [showLegend, setShowLegend] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [copyFeedback, setCopyFeedback] = useState(false);

  const graphCanvasRef = useRef<GraphCanvasHandle>(null);

  // Load trace data
  const loadTrace = async () => {
    setLoading(true);
    setError(null);
    try {
      const api = getApi();
      const res = await api.getTrace(runId);
      setTraceData(res);
    } catch {
      setError('Failed to load trace data.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTrace();
  }, [runId]);

  // Focus initial node if provided
  useEffect(() => {
    if (initialFocusedCid && traceData) {
      setTimeout(() => {
        graphCanvasRef.current?.focusNode(initialFocusedCid, true);
        const node = traceData.nodes.find((n) => n.id === initialFocusedCid);
        if (node) setSelectedNode(node);
      }, 400);
    }
  }, [initialFocusedCid, traceData]);

  // Convert nodes & edges to Cytoscape elements (Overview whole subgraph)
  const { elements, truncated } = useMemo(() => {
    if (!traceData) {
      return { elements: { nodes: [], edges: [] }, truncated: false };
    }

    return toElements({
      nodes: traceData.nodes,
      edges: traceData.edges,
      pathNodeIds: traceData.path_node_ids,
    });
  }, [traceData]);

  // Node name map for StepCard
  const nodeNameMap = useMemo(() => {
    const map: Record<string, string> = {};
    if (traceData) {
      for (const n of traceData.nodes) {
        map[n.id] = (n.props?.name as string) || n.id;
      }
    }
    return map;
  }, [traceData]);

  // Start node for Step 0 of Tour
  const startNode = useMemo(() => {
    if (!traceData || traceData.steps.length === 0) return undefined;
    const startId = traceData.steps[0]?.from;
    if (!startId) return undefined;
    return traceData.nodes.find((n) => n.id === startId);
  }, [traceData]);

  // Keyboard navigation
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable) {
        return;
      }

      if (state.mode === 'overview') {
        if (e.code === 'Space' || e.key === 'Enter' || e.key === 'ArrowRight') {
          if (traceData && traceData.steps.length > 0) {
            e.preventDefault();
            dispatch({ type: 'ENTER_TOUR', stepIndex: 0 });
          }
        }
      } else if (state.mode === 'tour') {
        if (e.code === 'Space' || e.key === 'Enter' || e.key === 'ArrowRight') {
          e.preventDefault();
          if (traceData) {
            dispatch({ type: 'NEXT_STEP', totalSteps: traceData.steps.length });
          }
        } else if (e.key === 'ArrowLeft') {
          e.preventDefault();
          dispatch({ type: 'PREV_STEP' });
        } else if (e.key === 'Escape' || e.key === 'o' || e.key === 'O') {
          e.preventDefault();
          dispatch({ type: 'EXIT_TOUR' });
          graphCanvasRef.current?.resetToOverview();
        }
      }
    },
    [state.mode, traceData]
  );

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  // Handle Export PNG
  const handleExportPng = () => {
    const dataUrl = graphCanvasRef.current?.exportPng();
    if (!dataUrl) return;
    const a = document.createElement('a');
    a.href = dataUrl;
    a.download = `trace_${runId}.png`;
    a.click();
  };

  // Handle Copy Path
  const handleCopyPath = () => {
    if (!traceData) return;
    const summaryText = traceData.summary || traceData.path_node_ids.join(' -> ');
    navigator.clipboard.writeText(summaryText);
    setCopyFeedback(true);
    setTimeout(() => setCopyFeedback(false), 2000);
  };

  // Handle Fit / Exit Tour
  const handleFit = () => {
    if (state.mode === 'tour') {
      dispatch({ type: 'EXIT_TOUR' });
      graphCanvasRef.current?.resetToOverview();
    } else {
      graphCanvasRef.current?.fit(60);
    }
  };

  // Handle neighbor expansion
  const handleExpandNode = async (cid: string) => {
    try {
      const api = getApi();
      const expanded = await api.expandNode(cid, 1);
      if (traceData) {
        const existingNodeIds = new Set(traceData.nodes.map((n: TraceNode) => n.id));
        const newNodes = expanded.nodes.filter((n: TraceNode) => !existingNodeIds.has(n.id));
        const existingEdgeIds = new Set(traceData.edges.map((e: TraceEdge) => e.id));
        const newEdges = expanded.edges.filter((e: TraceEdge) => !existingEdgeIds.has(e.id));

        setTraceData({
          ...traceData,
          nodes: [...traceData.nodes, ...newNodes],
          edges: [...traceData.edges, ...newEdges],
          truncated: expanded.truncated,
        });
      }
    } catch {
      // Graceful fallback
    }
  };

  const detectedPack = pack || 'investigate';
  const shortRunId = runId.length > 12 ? runId.slice(0, 12) : runId;

  return (
    <div className={styles.container}>
      {/* 48px Hairline Toolbar */}
      <header className={styles.toolbar}>
        <div className={styles.toolbarLeft}>
          <button className={styles.backBtn} onClick={onBack} aria-label="Back to conversation">
            <ArrowLeft size={16} strokeWidth={1.5} />
            BACK
          </button>
          <span className={styles.title}>
            TRACE · {detectedPack.toUpperCase()} · {shortRunId}
          </span>
          <Badge size="compact">TRAVERSAL</Badge>
        </div>

        <div className={styles.toolbarRight}>
          <input
            type="text"
            className={styles.searchInput}
            placeholder="Find node by id"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            aria-label="Find node by id"
          />

          <select
            className={styles.layoutSelect}
            value={state.layout}
            disabled={state.mode === 'tour'}
            onChange={(e) => dispatch({ type: 'SET_LAYOUT', layout: e.target.value as LayoutType })}
            aria-label="Graph layout type"
          >
            <option value="layered">LAYERED</option>
            <option value="radial">RADIAL</option>
            <option value="force">FORCE</option>
          </select>

          <GhostButton onClick={handleFit} aria-label={state.mode === 'tour' ? 'Return to overview' : 'Fit to viewport'}>
            FIT
          </GhostButton>

          <GhostButton onClick={handleExportPng}>
            EXPORT PNG
          </GhostButton>

          <GhostButton onClick={handleCopyPath}>
            {copyFeedback ? 'COPIED' : 'COPY PATH'}
          </GhostButton>

          <GhostButton
            className={showLegend ? styles.activeToggleBtn : ''}
            onClick={() => setShowLegend((v) => !v)}
          >
            LEGEND
          </GhostButton>

          <GhostButton
            className={state.hideContext ? styles.activeToggleBtn : ''}
            onClick={() => dispatch({ type: 'TOGGLE_HIDE_CONTEXT' })}
          >
            HIDE CONTEXT
          </GhostButton>
        </div>
      </header>

      {/* Summary Strip */}
      {traceData?.summary && (
        <div className={styles.summaryStrip}>
          {traceData.summary}
        </div>
      )}

      {/* Main Graph Content */}
      <div className={`${styles.mainArea} ${state.mode === 'tour' ? styles.mainAreaTour : ''}`}>
        {loading ? (
          <div className={styles.loadingOverlay}>
            <Spinner size={32} />
            <span>TRACING...</span>
          </div>
        ) : error ? (
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <ErrorState title="Could not load trace" message={error} onRetry={loadTrace} />
          </div>
        ) : !traceData || traceData.nodes.length === 0 ? (
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--color-smoke)' }}>
            No trace data for this run.
          </div>
        ) : (
          <>
            {/* Left StepList (slides out in Tour mode) */}
            <div className={`${styles.stepListWrapper} ${state.mode === 'tour' ? styles.stepListWrapperTour : ''}`}>
              <StepList
                steps={traceData.steps}
                activeStepSeq={
                  state.stepIndex && state.stepIndex > 0
                    ? traceData.steps[state.stepIndex - 1]?.seq
                    : undefined
                }
                onSelectStep={(seq) => {
                  dispatch({ type: 'ENTER_TOUR', stepIndex: seq });
                }}
                mode={traceData.mode}
              />
            </div>

            {/* Center Cytoscape Graph Canvas */}
            <main className={styles.centerGraph}>
              <GraphCanvas
                ref={graphCanvasRef}
                elements={elements}
                mode={state.mode}
                stepIndex={state.stepIndex}
                steps={traceData.steps}
                layoutType={state.layout}
                hideContext={state.hideContext}
                searchQuery={searchQuery}
                truncated={truncated}
                totalNodeCount={traceData.nodes.length}
                onSelectNode={setSelectedNode}
                onExpandNode={handleExpandNode}
              />

              {/* Floating Step Card in Tour Mode */}
              {state.mode === 'tour' && state.stepIndex !== null && (
                <StepCard
                  stepIndex={state.stepIndex}
                  totalSteps={traceData.steps.length}
                  currentStep={
                    state.stepIndex > 0 ? traceData.steps[state.stepIndex - 1] : undefined
                  }
                  startNode={startNode}
                  nodeNameMap={nodeNameMap}
                  exploredSteps={traceData.explored_steps}
                />
              )}

              <Legend isOpen={showLegend} onClose={() => setShowLegend(false)} />
            </main>

            {/* Right NodeDetail Drawer */}
            {selectedNode && (
              <NodeDetail
                node={selectedNode}
                steps={traceData.steps}
                findings={findings}
                onClose={() => setSelectedNode(null)}
                onWhy={onWhy}
                onExpand={handleExpandNode}
              />
            )}
          </>
        )}
      </div>

      {/* Bottom Scrubber */}
      {traceData && (
        <Scrubber
          totalSteps={traceData.steps.length}
          mode={state.mode}
          stepIndex={state.stepIndex}
          onEnterTour={() => dispatch({ type: 'ENTER_TOUR', stepIndex: 0 })}
          onExitTour={() => {
            dispatch({ type: 'EXIT_TOUR' });
            graphCanvasRef.current?.resetToOverview();
          }}
          onStepBack={() => dispatch({ type: 'PREV_STEP' })}
          onStepForward={() => dispatch({ type: 'NEXT_STEP', totalSteps: traceData.steps.length })}
          onSeek={(idx) => dispatch({ type: 'SET_STEP', stepIndex: idx })}
        />
      )}
    </div>
  );
};
