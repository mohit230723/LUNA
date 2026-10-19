import React, { useCallback, useEffect, useReducer, useRef, useState } from 'react';
import { getApi } from '../../api';
import type { ForgeConnectInfo, ForgeEvent, ForgeRunSummary } from '../../api/contract';
import { forgeReducer, initialForgeState } from '../../state/forgeReducer';
import { ConnectCard } from './ConnectCard';
import { AgentList } from './AgentList';
import { RunList } from './RunList';
import { RunView } from './RunView';
import './forge.css';

const REFETCH_DEBOUNCE_MS = 300;
const POLL_MS = 30_000;
const RUN_REFRESH_EVENTS = new Set(['task_updated', 'task_stalled', 'run_assembled']);

function newestRun(runs: ForgeRunSummary[]): string | null {
  if (runs.length === 0) return null;
  const sorted = [...runs].sort((a, b) => (Date.parse(b.created_at) || 0) - (Date.parse(a.created_at) || 0));
  return sorted[0]!.run_id;
}

export const AgentsTab: React.FC = () => {
  const [state, dispatch] = useReducer(forgeReducer, initialForgeState);
  const [connect, setConnect] = useState<ForgeConnectInfo | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [now, setNow] = useState(() => Date.now());

  const selectedRef = useRef<string | null>(null);
  selectedRef.current = selectedRunId;
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mounted = useRef(true);

  const loadRun = useCallback(async (runId: string) => {
    try {
      const detail = await getApi().forgeRun(runId);
      // Drop stale responses for a run the user has since navigated away from.
      if (mounted.current && selectedRef.current === runId) dispatch({ type: 'run', run: detail });
    } catch {
      // keep the last known state; the next event or poll retries
    }
  }, []);

  const loadAgents = useCallback(async () => {
    try {
      const agents = await getApi().forgeAgents();
      if (mounted.current) dispatch({ type: 'agents', agents });
    } catch {
      // transient; the poll retries
    }
  }, []);

  const loadRuns = useCallback(async () => {
    try {
      const runs = await getApi().forgeRuns();
      if (mounted.current) dispatch({ type: 'runs', runs });
    } catch {
      // transient; the poll retries
    }
  }, []);

  // Initial load: connect info, agents and runs; select the newest run.
  const loadAll = useCallback(async () => {
    const api = getApi();
    try {
      const [info, agents, runs] = await Promise.all([api.forgeConnect(), api.forgeAgents(), api.forgeRuns()]);
      if (!mounted.current) return;
      setError(null);
      setConnect(info);
      dispatch({ type: 'agents', agents });
      dispatch({ type: 'runs', runs });
      setSelectedRunId((cur) => cur ?? newestRun(runs));
    } catch (e) {
      if (mounted.current) setError(e instanceof Error ? e.message : 'Could not reach the LUNA forge API.');
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    loadAll();
    return () => {
      mounted.current = false;
    };
  }, [loadAll]);

  // Live events. The reducer patches state optimistically; run-affecting events
  // also schedule a debounced refetch because events alone are not trusted.
  useEffect(() => {
    const onEvent = (e: ForgeEvent) => {
      dispatch({ type: 'event', event: e });
      if (e.type === 'run_created') {
        setSelectedRunId((cur) => cur ?? (typeof e.data?.run_id === 'string' ? e.data.run_id : null));
      }
      const runId = selectedRef.current;
      if (runId && RUN_REFRESH_EVENTS.has(e.type) && e.data?.run_id === runId) {
        if (debounceRef.current) clearTimeout(debounceRef.current);
        debounceRef.current = setTimeout(() => {
          debounceRef.current = null;
          loadRun(runId);
        }, REFETCH_DEBOUNCE_MS);
      }
    };
    let unsub: () => void = () => undefined;
    try {
      unsub = getApi().subscribeForge({
        onEvent,
        onState: (s) => dispatch({ type: 'connection', state: s }),
        onHello: (h) => {
          dispatch({ type: 'hello', seq: h.seq });
          if (h.restarted) {
            // New backend process: resync everything over REST.
            loadAgents();
            loadRuns();
            if (selectedRef.current) loadRun(selectedRef.current);
          }
        },
      });
    } catch {
      // No EventSource available: stay usable on the 30 s poll alone.
      dispatch({ type: 'connection', state: 'closed' });
    }
    return () => {
      unsub();
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [loadRun, loadAgents, loadRuns]);

  // Load the selected run whenever the selection changes.
  useEffect(() => {
    setSelectedTaskId(null);
    if (selectedRunId) loadRun(selectedRunId);
    else dispatch({ type: 'run', run: null });
  }, [selectedRunId, loadRun]);

  // Periodic reconciliation: agent idle/connected labels, the run list and the active run.
  useEffect(() => {
    const id = setInterval(() => {
      loadAgents();
      loadRuns();
      if (selectedRef.current) loadRun(selectedRef.current);
    }, POLL_MS);
    return () => clearInterval(id);
  }, [loadAgents, loadRuns, loadRun]);

  // One-second clock for lease countdowns and "last seen" ages.
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  const activeRun =
    state.activeRun && state.activeRun.run.run_id === selectedRunId ? state.activeRun : null;
  const live = state.connection === 'open';

  return (
    <div className="forge-agents">
      <div className="forge-col">
        <p className="forge-status-label" role="status">
          <span className={`forge-status-dot${live ? ' is-live' : ''}`} aria-hidden="true" />
          {live ? 'Live' : state.connection === 'reconnecting' ? 'Reconnecting…' : 'Offline'}
        </p>
        {error && (
          <div className="forge-panel">
            <p className="forge-error">{error}</p>
            <button type="button" className="forge-btn" onClick={loadAll}>
              Retry
            </button>
          </div>
        )}
        {connect && <ConnectCard info={connect} />}
        <AgentList agents={state.agents} now={now} />
        <RunList runs={state.runs} selectedId={selectedRunId} onSelect={setSelectedRunId} />
      </div>
      <div className="forge-col">
        {activeRun ? (
          <RunView
            run={activeRun}
            now={now}
            selectedTaskId={selectedTaskId}
            onSelectTask={setSelectedTaskId}
          />
        ) : (
          <section className="forge-panel">
            <p className="forge-muted">
              {selectedRunId ? 'Loading run…' : 'No build run selected. Runs appear here as agents plan work.'}
            </p>
          </section>
        )}
      </div>
    </div>
  );
};

export default AgentsTab;
