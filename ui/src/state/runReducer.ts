import {
  ActionRequest,
  AgentInfo,
  Block,
  FileNode,
  FindingInfo,
  RunEvent,
  RunStatus,
} from '../api/contract';
import { deriveStagesFromEvents, getInitialStages, StageState } from './stages';

export interface RunState {
  runId: string;
  status: RunStatus;
  events: RunEvent[];
  stages: StageState[];
  agents: AgentInfo[];
  findings: FindingInfo[];
  blocks: Block[];
  files: FileNode[];
  actions: ActionRequest[];
  lastEventId: number;
}

export function createInitialRunState(runId = ''): RunState {
  return {
    runId,
    status: runId ? 'streaming' : 'queued',
    events: [],
    stages: getInitialStages(),
    agents: [],
    findings: [],
    blocks: [],
    files: [],
    actions: [],
    lastEventId: 0,
  };
}

export type RunAction =
  | { type: 'ADD_EVENT'; event: RunEvent }
  | { type: 'SET_STATUS'; status: RunStatus }
  | { type: 'UPDATE_ACTION'; action: ActionRequest }
  | { type: 'RESET_RUN'; runId: string };

export function runReducer(state: RunState, action: RunAction): RunState {
  switch (action.type) {
    case 'RESET_RUN':
      return createInitialRunState(action.runId);

    case 'SET_STATUS':
      return { ...state, status: action.status };

    case 'UPDATE_ACTION': {
      const updatedActions = state.actions.map((act) =>
        act.action_id === action.action.action_id ? action.action : act
      );
      return { ...state, actions: updatedActions };
    }

    case 'ADD_EVENT': {
      const { event } = action;

      // Ignore duplicates
      if (state.events.some((e) => e.run_id === event.run_id && e.seq === event.seq)) {
        return state;
      }

      const newEvents = [...state.events, event].sort((a, b) => a.seq - b.seq);
      const newLastId = Math.max(state.lastEventId, event.seq);
      const newStages = deriveStagesFromEvents(newEvents);

      let newStatus = state.status;
      let newAgents = [...state.agents];
      let newFindings = [...state.findings];
      let newActions = [...state.actions];
      let newBlocks = [...state.blocks];
      let newFiles = [...state.files];

      // Update run status based on event
      if (event.type === 'needs_input') {
        newStatus = 'needs_input';
      } else if (event.type === 'completed') {
        newStatus = 'done';
      } else if (event.type === 'failed') {
        newStatus = 'failed';
      } else if (event.type === 'cancelled') {
        newStatus = 'cancelled';
      }

      // Track Agents
      if (event.type === 'agent_started') {
        const id = (event.data['agent_id'] as string) || (event.data['id'] as string) || `agent_${newAgents.length}`;
        const skill = (event.data['skill'] as string) || 'generic-skill';
        if (!newAgents.some((a) => a.id === id)) {
          newAgents.push({
            id,
            skill,
            status: 'running',
            tool_calls: 0,
            backend: event.backend || 'scripted',
          });
        }
      }

      if (event.type === 'tool_call') {
        const agentId = event.data['agent_id'] as string;
        newAgents = newAgents.map((a) =>
          a.id === agentId ? { ...a, tool_calls: a.tool_calls + 1 } : a
        );
      }

      if (event.type === 'agent_done') {
        const agentId = event.data['agent_id'] as string;
        newAgents = newAgents.map((a) =>
          a.id === agentId ? { ...a, status: 'done' } : a
        );
      }

      if (event.type === 'agent_failed') {
        const agentId = event.data['agent_id'] as string;
        const reason = (event.data['reason'] as string) || 'Agent execution failed';
        newAgents = newAgents.map((a) =>
          a.id === agentId ? { ...a, status: 'failed', reason } : a
        );
      }

      // Track Findings
      if (event.type === 'promoted') {
        const items = event.data['findings'] as FindingInfo[] | undefined;
        if (Array.isArray(items)) {
          for (const item of items) {
            const idx = newFindings.findIndex((f) => f.id === item.id);
            if (idx >= 0) newFindings[idx] = item;
            else newFindings.push(item);
          }
        }
      }

      // Track Actions
      if (event.type === 'action_proposed') {
        const act = event.data as unknown as ActionRequest;
        if (act && act.action_id) {
          const idx = newActions.findIndex((a) => a.action_id === act.action_id);
          if (idx >= 0) newActions[idx] = act;
          else newActions.push(act);
        }
      }

      // Track Blocks
      if (event.type === 'routed') {
        newBlocks.push({
          type: 'routing',
          data: {
            pack: (event.data['pack'] as any) || 'investigate',
            intent: (event.data['intent'] as string) || '',
            confidence: Number(event.data['confidence'] || 1),
            backend: event.backend || 'scripted',
          },
        });
      }

      if (event.type === 'skill_assigned') {
        const assignments = event.data['assignments'] as any;
        if (Array.isArray(assignments)) {
          newBlocks.push({
            type: 'skills',
            data: { assignments },
          });
        }
      }

      if (event.type === 'answer') {
        const ans = event.data['text'] as any;
        if (ans) {
          newBlocks.push({
            type: 'answer',
            data: {
              text: typeof ans === 'string' ? ans : ans.text || '',
              cited_cids: Array.isArray(ans.cited_cids) ? ans.cited_cids : [],
              backend: event.backend || 'scripted',
            },
          });
        }
      }

      return {
        ...state,
        events: newEvents,
        stages: newStages,
        status: newStatus,
        lastEventId: newLastId,
        agents: newAgents,
        findings: newFindings,
        actions: newActions,
        blocks: newBlocks,
        files: newFiles,
      };
    }

    default:
      return state;
  }
}
