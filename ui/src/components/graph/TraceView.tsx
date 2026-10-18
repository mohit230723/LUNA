import React, { useReducer, useEffect, useState, useRef, useMemo } from 'react';
import { ArrowLeft } from 'lucide-react';
import { Badge } from '../ui/Badge';
import { GhostButton } from '../ui/GhostButton';
import { Spinner } from '../ui/Spinner';
import { ErrorState } from '../ui/ErrorState';
import { StepList } from './StepList';
import { GraphCanvas, GraphCanvasHandle, LayoutType } from './GraphCanvas';
import { NodeDetail } from './NodeDetail';
import { Scrubber } from './Scrubber';
import { Legend } from './Legend';
import { toElements } from './toElements';
import { traceReducer, initialTraceState } from '../../state/traceReducer';
import { getApi } from '../../api';
import type { TraceResponse, TraceNode, FindingInfo } from '../../api/contract';
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

  const [state, dispatch] = useReducer(traceReducer, initialTraceState);
  const [selectedNode, setSelectedNode] = useState<TraceNode | null>(null);
  const [layoutType, setLayoutType] = useState<LayoutType>('layered');
  const [hideContext, setHideContext] = useState(false);
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
      // Initialize revealed steps to total steps initially
      dispatch({ type: 'SET_TOTAL_STEPS', totalSteps: res.steps.length });
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
        graphCanvasRef.current?.focusNode(initialFocusedCid);
        const node = traceData.nodes.find((n) => n.id === initialFocusedCid);
        if (node) setSelectedNode(node);
      }, 400);
    }
  }, [initialFocusedCid, traceData]);

  // Playback ticker: 900ms / speed
  useEffect(() => {
    if (!state.playing || !traceData || traceData.steps.length === 0) return;

    const intervalMs = Math.round(900 / state.speed);
    const timer = setInterval(() => {
      dispatch({ type: 'STEP_FORWARD' });
    }, intervalMs);

    return () => clearInterval(timer);
  }, [state.playing, state.speed, traceData]);

  // Convert nodes & edges to Cytoscape elements
  const { elements, truncated } = useMemo(() => {
    if (!traceData) {
      return { elements: { nodes: [], edges: [] }, truncated: false };
    }

    const revealedSteps = state.showAll
      ? traceData.steps
      : traceData.steps.slice(0, state.revealedStepCount);

    return toElements({
      nodes: traceData.nodes,
      edges: traceData.edges,
      pathNodeIds: traceData.path_node_ids,
      revealedSteps,
      activeStepSeq: state.selectedStepSeq ?? state.revealedStepCount,
      showAll: state.showAll,
    });
  }, [traceData, state.revealedStepCount, state.selectedStepSeq, state.showAll]);

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
    const pathStr = traceData.path_node_ids.join(' -> ');
    navigator.clipboard.writeText(pathStr);
    setCopyFeedback(true);
    setTimeout(() => setCopyFeedback(false), 2000);
  };

  // Handle neighbor expansion
  const handleExpandNode = async (cid: string) => {
    try {
      const api = getApi();
      const expanded = await api.expandNode(cid, 1);
      if (traceData) {
        const existingNodeIds = new Set(traceData.nodes.map((n) => n.id));
        const newNodes = expanded.nodes.filter((n) => !existingNodeIds.has(n.id));
        const existingEdgeIds = new Set(traceData.edges.map((e) => e.id));
        const newEdges = expanded.edges.filter((e) => !existingEdgeIds.has(e.id));

        setTraceData({
          ...traceData,
          nodes: [...traceData.nodes, ...newNodes],
          edges: [...traceData.edges, ...newEdges],
          truncated: expanded.truncated,
        });
      }
    } catch {
      //
    }
  };

  const detectedPack = pack || (traceData?.mode === 'blueprint' ? 'build' : 'investigate');
  const shortRunId = runId.length > 12 ? runId.slice(0, 12) : runId;
  const currentStep = traceData?.steps.find(
    (s) => s.seq === (state.selectedStepSeq ?? state.revealedStepCount)
  );

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
          <Badge size="compact">
            {traceData?.mode === 'blueprint' ? 'BLUEPRINT' : 'TRAVERSAL'}
          </Badge>
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
            value={layoutType}
            onChange={(e) => setLayoutType(e.target.value as LayoutType)}
            aria-label="Graph layout type"
          >
            <option value="layered">LAYERED</option>
            <option value="radial">RADIAL</option>
            <option value="force">FORCE</option>
          </select>

          <GhostButton onClick={() => graphCanvasRef.current?.fit()}>
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
            className={hideContext ? styles.activeToggleBtn : ''}
            onClick={() => setHideContext((v) => !v)}
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
      <div className={styles.mainArea}>
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
            {/* Left StepList */}
            <StepList
              steps={traceData.steps}
              activeStepSeq={state.selectedStepSeq ?? state.revealedStepCount}
              onSelectStep={(seq) => dispatch({ type: 'SEEK_STEP', stepIndex: seq })}
              mode={traceData.mode}
            />

            {/* Center Cytoscape Graph Canvas */}
            <main className={styles.centerGraph}>
              <GraphCanvas
                ref={graphCanvasRef}
                elements={elements}
                mode={traceData.mode}
                layoutType={layoutType}
                hideContext={hideContext}
                searchQuery={searchQuery}
                activeStep={currentStep}
                isPlaying={state.playing}
                truncated={truncated}
                totalNodeCount={traceData.nodes.length}
                onSelectNode={setSelectedNode}
                onExpandNode={handleExpandNode}
              />

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
      {traceData && traceData.steps.length > 0 && (
        <Scrubber
          totalSteps={traceData.steps.length}
          currentStepSeq={state.selectedStepSeq ?? state.revealedStepCount}
          isPlaying={state.playing}
          speed={state.speed}
          showAll={state.showAll}
          onTogglePlay={() => dispatch({ type: 'TOGGLE_PLAY' })}
          onStepBack={() => dispatch({ type: 'STEP_BACK' })}
          onStepForward={() => dispatch({ type: 'STEP_FORWARD' })}
          onSeek={(seq) => dispatch({ type: 'SEEK_STEP', stepIndex: seq })}
          onChangeSpeed={(spd) => dispatch({ type: 'SET_SPEED', speed: spd })}
          onToggleShowAll={() => dispatch({ type: 'TOGGLE_SHOW_ALL' })}
        />
      )}
    </div>
  );
};
