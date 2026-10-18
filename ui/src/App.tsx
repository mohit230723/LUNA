import React, { useEffect, useReducer, useRef, useState } from 'react';
import { Header } from './components/Header';
import { GraphCanvas } from './components/GraphCanvas';
import { FindingsTable } from './components/FindingsTable';
import { DecisionPanel } from './components/DecisionPanel';
import { WhyExplanationModal } from './components/WhyExplanationModal';
import {
  INITIAL_PIPELINE_STATE,
  pipelineReducer,
  StepName,
} from './state/pipelineReducer';
import {
  approveAction,
  fetchGraphScope,
  fetchReplayData,
  fetchRunWhy,
  rejectAction,
  startLiveRun,
} from './services/api';
import { CustomerExplanation, GraphScopeData, PipelineEvent } from './types';
import './styles/theme.css';

export const App: React.FC = () => {
  const [state, dispatch] = useReducer(pipelineReducer, INITIAL_PIPELINE_STATE);

  // UI state
  const [mode, setMode] = useState<'LIVE' | 'REPLAY'>('REPLAY');
  const [scope, setScope] = useState<'run' | 'atlas' | 'domain' | 'agent'>('run');
  const [scopeData, setScopeData] = useState<GraphScopeData | null>(null);
  const [isGraphLoading, setIsGraphLoading] = useState(false);

  // Replay playback state
  const [replayEvents, setReplayEvents] = useState<PipelineEvent[]>([]);
  const [replayIndex, setReplayIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [snapshots, setSnapshots] = useState<Record<string, GraphScopeData>>({});

  // Explanation Modal
  const [explanation, setExplanation] = useState<CustomerExplanation | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [highlightedIds, setHighlightedIds] = useState<string[]>([]);

  // EventSource ref for Live mode
  const eventSourceRef = useRef<EventSource | null>(null);

  // Load replay data on initial mount
  useEffect(() => {
    loadReplay();
  }, []);

  const loadReplay = async () => {
    try {
      const data: any = await fetchReplayData();
      let events: PipelineEvent[] = [];
      let runId = 'replay_run_01';
      let graphSnaps: Record<string, GraphScopeData> = {};

      if (data.runs && data.runs.length > 0) {
        events = data.runs[0].events || [];
        runId = data.runs[0].run_id || runId;
        graphSnaps = data.runs[0].graph_snapshots || {};
      } else if (Array.isArray(data.events)) {
        events = data.events;
        runId = data.run_id || runId;
        graphSnaps = data.graph_snapshots || {};
      }

      setReplayEvents(events);
      setSnapshots(graphSnaps);
      dispatch({ type: 'RESET_STATE' });
      dispatch({ type: 'SET_RUN_ID', runId });
      setReplayIndex(0);

      // Initial graph snapshot if present
      if (graphSnaps.domain) {
        setScopeData(graphSnaps.domain);
      } else if (graphSnaps.run) {
        setScopeData(graphSnaps.run);
      }
    } catch (err) {
      console.warn('Could not load /api/replay, using empty state:', err);
    }
  };

  // Step through replay events
  const stepToEventIndex = (targetIndex: number) => {
    if (targetIndex < 0 || targetIndex >= replayEvents.length) return;

    // Reset and replay up to target index
    dispatch({ type: 'RESET_STATE' });
    dispatch({ type: 'SET_RUN_ID', runId: state.runId });

    for (let i = 0; i <= targetIndex; i++) {
      const ev = replayEvents[i];
      // Normalize event data
      const normalizedEv: PipelineEvent = {
        step: (ev.step || 'detect') as StepName,
        phase: ev.phase || (ev as any).message || String(ev.step),
        data: ev.data || {},
        timestamp: ev.timestamp || new Date().toISOString(),
        id: ev.id ?? i,
      };
      dispatch({ type: 'PROCESS_EVENT', event: normalizedEv });
    }
    setReplayIndex(targetIndex);
  };

  // Replay playback timer
  useEffect(() => {
    if (!isPlaying || mode !== 'REPLAY') return;

    const intervalTime = Math.max(50, Math.floor(1000 / speed));
    const timer = setInterval(() => {
      setReplayIndex((prev) => {
        if (prev >= replayEvents.length - 1) {
          setIsPlaying(false);
          return prev;
        }
        const nextIndex = prev + 1;
        const ev = replayEvents[nextIndex];
        const normalizedEv: PipelineEvent = {
          step: (ev.step || 'detect') as StepName,
          phase: ev.phase || (ev as any).message || String(ev.step),
          data: ev.data || {},
          timestamp: ev.timestamp || new Date().toISOString(),
          id: ev.id ?? nextIndex,
        };
        dispatch({ type: 'PROCESS_EVENT', event: normalizedEv });
        return nextIndex;
      });
    }, intervalTime);

    return () => clearInterval(timer);
  }, [isPlaying, replayEvents, speed, mode]);

  // Load Graph Scope data whenever scope or runId changes
  useEffect(() => {
    if (!state.runId) return;

    // In replay mode, check if we have a recorded snapshot
    if (mode === 'REPLAY' && snapshots[scope]) {
      setScopeData(snapshots[scope]);
      return;
    }

    // Otherwise fetch live from backend API
    let active = true;
    setIsGraphLoading(true);
    fetchGraphScope(state.runId, scope)
      .then((data) => {
        if (active) {
          setScopeData(data);
          setIsGraphLoading(false);
        }
      })
      .catch((err) => {
        if (active) {
          setIsGraphLoading(false);
          // If live fetch fails, synthesize scope from reducer state
          synthesizeLocalScopeData(scope);
        }
      });

    return () => {
      active = false;
    };
  }, [state.runId, scope, mode, snapshots, state.events.length]);

  const synthesizeLocalScopeData = (targetScope: string) => {
    if (state.nodes.length > 0) {
      setScopeData({
        nodes: state.nodes.map((n) => ({ ...n.data, id: n.data.id, label: n.data.label })),
        edges: state.edges.map((e) => ({
          ...e.data,
          source: e.data.source,
          target: e.data.target,
          type: e.data.type,
        })),
      });
    }
  };

  // SSE Live Connection
  useEffect(() => {
    if (mode !== 'LIVE' || !state.runId || state.runStatus === 'IDLE') {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      return;
    }

    const sseUrl = `/api/runs/${encodeURIComponent(state.runId)}/events`;
    const es = new EventSource(sseUrl);
    eventSourceRef.current = es;

    es.onmessage = (msg) => {
      try {
        const parsed = JSON.parse(msg.data);
        const normalizedEv: PipelineEvent = {
          step: (parsed.step || 'detect') as StepName,
          phase: parsed.phase || parsed.step,
          data: parsed.data || {},
          timestamp: parsed.timestamp || new Date().toISOString(),
          id: parsed.id,
        };
        dispatch({ type: 'PROCESS_EVENT', event: normalizedEv });
      } catch (e) {
        console.error('Error parsing SSE event:', e);
      }
    };

    es.onerror = (err) => {
      console.warn('SSE connection error or closed:', err);
      es.close();
    };

    return () => {
      es.close();
    };
  }, [mode, state.runId, state.runStatus]);

  // Handlers
  const handleToggleMode = (newMode: 'LIVE' | 'REPLAY') => {
    setMode(newMode);
    setIsPlaying(false);
    if (newMode === 'REPLAY') {
      loadReplay();
    }
  };

  const handleStartLiveRun = async () => {
    try {
      dispatch({ type: 'RESET_STATE' });
      const res = await startLiveRun({ scenario: 'fraud_ring' });
      dispatch({ type: 'SET_RUN_ID', runId: res.run_id });
      dispatch({ type: 'SET_RUN_STATUS', status: 'RUNNING' });
    } catch (err: any) {
      alert(`Failed to start run: ${err.message}`);
    }
  };

  const handleSelectCustomer = (customerId: string) => {
    dispatch({ type: 'SELECT_CUSTOMER', customerId });
    setHighlightedIds([customerId]);
  };

  const handleSelectNode = (nodeId: string, nodeType: string) => {
    dispatch({ type: 'SELECT_NODE', nodeId });
    if (nodeType === 'Customer') {
      dispatch({ type: 'SELECT_CUSTOMER', customerId: nodeId });
    }
    setHighlightedIds(nodeId ? [nodeId] : []);
  };

  const handleExplainCustomer = async (customerId: string) => {
    try {
      const whyData = await fetchRunWhy(state.runId, customerId);
      setExplanation(whyData);
      setIsModalOpen(true);
    } catch (err: any) {
      // Local fallback narrative if backend why endpoint is not active
      const res = state.resolutions[customerId];
      const customerFindings = state.findings.filter((f) => f.customer_id === customerId);
      const activeSuspicious = customerFindings.filter((f) => f.verdict === 'suspicious' && f.status === 'active');
      const winning = res?.winning_side || (activeSuspicious.length > 0 ? 'suspicious' : 'benign');
      const action = state.actions.find((a) => a.customer_id === customerId);

      setExplanation({
        customer_id: customerId,
        winning_side: winning,
        narrative: `Customer ${customerId} was analyzed across ${customerFindings.length} distinct agent findings. Corroborated with ${activeSuspicious.length} active suspicious findings. Winning verdict: ${winning.toUpperCase()}.`,
        corroboration: {
          corroborated: activeSuspicious.length >= 2,
          active_suspicious_count: activeSuspicious.length,
          distinct_skills: Array.from(new Set(activeSuspicious.map((f) => f.skill_id))),
          best_confidence: activeSuspicious[0]?.confidence || 0.85,
        },
        supporting_findings: customerFindings.filter((f) => f.status === 'active'),
        superseded_findings: customerFindings.filter((f) => f.status === 'superseded'),
        action: action
          ? {
              action_type: action.action_type,
              status: action.status,
              confidence: action.confidence,
              reason: action.reason,
            }
          : null,
        subgraph: {
          nodes: [{ id: customerId, label: customerId, type: 'Customer' }],
          edges: [],
        },
      });
      setIsModalOpen(true);
    }
  };

  const handleApproveAction = async (actionId: string) => {
    try {
      const res = await approveAction(state.runId, actionId);
      dispatch({
        type: 'UPDATE_ACTION_STATUS',
        actionId,
        status: 'EXECUTED',
        executionResult: res.execution_result,
      });
    } catch (err: any) {
      // If offline/replay, simulate local execution
      dispatch({
        type: 'UPDATE_ACTION_STATUS',
        actionId,
        status: 'EXECUTED',
        executionResult: { status: 'EXECUTED_LOCALLY', timestamp: new Date().toISOString() },
      });
    }
  };

  const handleRejectAction = async (actionId: string, reason: string) => {
    try {
      await rejectAction(state.runId, actionId, reason);
      dispatch({ type: 'UPDATE_ACTION_STATUS', actionId, status: 'REJECTED' });
    } catch (err: any) {
      dispatch({ type: 'UPDATE_ACTION_STATUS', actionId, status: 'REJECTED' });
    }
  };

  const handleHighlightSubgraph = (nodeIds: string[]) => {
    setHighlightedIds(nodeIds);
  };

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
        width: '100vw',
        background: 'var(--bg-canvas)',
        color: 'var(--text-primary)',
        overflow: 'hidden',
      }}
    >
      {/* Top Header */}
      <Header
        runId={state.runId}
        runStatus={state.runStatus}
        currentStep={state.currentStep}
        stepProgress={state.stepProgress}
        mode={mode}
        isPlaying={isPlaying}
        speed={speed}
        replayIndex={replayIndex}
        totalReplayEvents={replayEvents.length}
        onToggleMode={handleToggleMode}
        onTogglePlay={() => setIsPlaying(!isPlaying)}
        onStepNext={() => stepToEventIndex(replayIndex + 1)}
        onReset={() => stepToEventIndex(0)}
        onChangeSpeed={setSpeed}
        onScrub={stepToEventIndex}
        onStartLiveRun={handleStartLiveRun}
      />

      {/* Main 3-Column Layout */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '320px 1fr 340px',
          flex: 1,
          overflow: 'hidden',
        }}
      >
        {/* Left Column: Findings Table */}
        <FindingsTable
          findings={state.findings}
          onSelectCustomer={handleSelectCustomer}
          onExplainCustomer={handleExplainCustomer}
          selectedCustomerId={state.selectedCustomerId}
        />

        {/* Center Column: Interactive Cytoscape Canvas */}
        <GraphCanvas
          runId={state.runId}
          scope={scope}
          scopeData={scopeData}
          onScopeChange={setScope}
          onSelectNode={handleSelectNode}
          highlightedIds={highlightedIds}
          isLoading={isGraphLoading}
        />

        {/* Right Column: Decision Engine & HIL Action Gate */}
        <DecisionPanel
          runId={state.runId}
          resolutions={state.resolutions}
          actions={state.actions}
          onApproveAction={handleApproveAction}
          onRejectAction={handleRejectAction}
          selectedCustomerId={state.selectedCustomerId}
        />
      </div>

      {/* "Why?" Explanation Modal */}
      <WhyExplanationModal
        explanation={explanation}
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onHighlightSubgraph={handleHighlightSubgraph}
      />
    </div>
  );
};
export default App;
