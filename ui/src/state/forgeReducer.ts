import type { ForgeAgent, ForgeEvent, ForgeReport, ForgeRunDetail, ForgeRunSummary, ForgeTask } from '../api/contract';

export interface ForgeState {
  agents: ForgeAgent[];
  runs: ForgeRunSummary[];
  activeRun: ForgeRunDetail | null;
  lastSeq: number;
  connection: 'open' | 'reconnecting' | 'closed';
}

export type ForgeAction =
  | { type: 'agents'; agents: ForgeAgent[] }
  | { type: 'runs'; runs: ForgeRunSummary[] }
  | { type: 'run'; run: ForgeRunDetail | null }
  | { type: 'event'; event: ForgeEvent }
  | { type: 'connection'; state: ForgeState['connection'] };

export const initialForgeState: ForgeState = {
  agents: [],
  runs: [],
  activeRun: null,
  lastSeq: 0,
  connection: 'closed',
};

const str = (v: unknown): string => (typeof v === 'string' ? v : '');

function upsertAgent(agents: ForgeAgent[], data: Record<string, unknown>, ts: string): ForgeAgent[] {
  const id = str(data.session_id);
  if (!id) return agents;
  const idx = agents.findIndex((a) => a.session_id === id);
  const prev = idx >= 0 ? agents[idx]! : null;
  const next: ForgeAgent = {
    session_id: id,
    client_name: str(data.client_name) || prev?.client_name || '',
    client_version: str(data.client_version) || prev?.client_version || '',
    first_seen: prev?.first_seen || ts,
    last_seen: ts,
    connected: true,
  };
  if (idx < 0) return [next, ...agents];
  return agents.map((a, i) => (i === idx ? next : a));
}

function patchTask(state: ForgeState, data: Record<string, unknown>): ForgeState {
  const run = state.activeRun;
  if (!run || data.run_id !== run.run.run_id) return state;
  const taskId = str(data.task_id);
  if (!run.tasks.some((t) => t.task_id === taskId)) return state;
  const tasks = run.tasks.map((t): ForgeTask => {
    if (t.task_id !== taskId) return t;
    const patch: Partial<ForgeTask> = { status: str(data.status) || t.status };
    if (typeof data.claimed_by === 'string') patch.claimed_by = data.claimed_by;
    if (typeof data.agent_label === 'string') patch.agent_label = data.agent_label;
    if (data.result && typeof data.result === 'object') patch.result = data.result as Record<string, unknown>;
    return { ...t, ...patch };
  });
  return { ...state, activeRun: { ...run, tasks } };
}

export function forgeReducer(state: ForgeState, action: ForgeAction): ForgeState {
  switch (action.type) {
    case 'agents':
      return { ...state, agents: action.agents };
    case 'runs':
      return { ...state, runs: action.runs };
    case 'run':
      return { ...state, activeRun: action.run };
    case 'connection':
      return { ...state, connection: action.state };
    case 'event': {
      const { event } = action;
      if (event.seq <= state.lastSeq) return state;
      const base: ForgeState = { ...state, lastSeq: event.seq };
      const data = event.data ?? {};
      switch (event.type) {
        case 'agent_connected':
        case 'agent_seen':
          return { ...base, agents: upsertAgent(base.agents, data, event.ts) };
        case 'run_created': {
          const summary: ForgeRunSummary = {
            run_id: str(data.run_id),
            prompt: str(data.prompt),
            status: 'planned',
            created_at: event.ts,
            task_count: 0,
          };
          return { ...base, runs: [summary, ...base.runs.filter((r) => r.run_id !== summary.run_id)] };
        }
        case 'task_updated':
        case 'task_stalled':
          return patchTask(base, data);
        case 'run_assembled': {
          const report = (data.report ?? null) as ForgeReport | null;
          const runId = str(data.run_id);
          const runs = base.runs.map((r) => (r.run_id === runId && report ? { ...r, status: report.status } : r));
          const active = base.activeRun;
          if (active && active.run.run_id === runId) {
            return {
              ...base,
              runs,
              activeRun: {
                ...active,
                run: report ? { ...active.run, status: report.status } : active.run,
                report,
              },
            };
          }
          return { ...base, runs };
        }
        default:
          return base;
      }
    }
  }
}
