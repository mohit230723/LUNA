import {
  CustomerResolution,
  Finding,
  GraphEdge,
  GraphNode,
  PipelineEvent,
  PipelineMetrics,
  ProposedAction,
  StepName,
} from '../types';

export type { StepName };

export interface PipelineState {
  runId: string;
  runStatus: 'IDLE' | 'RUNNING' | 'PAUSED' | 'AWAITING_APPROVAL' | 'COMPLETED' | 'ERROR';
  currentStep: StepName;
  stepProgress: number; // 0 to 8
  events: PipelineEvent[];
  findings: Finding[];
  resolutions: Record<string, CustomerResolution>;
  actions: ProposedAction[];
  nodes: GraphNode[];
  edges: GraphEdge[];
  metrics: PipelineMetrics;
  selectedCustomerId: string | null;
  selectedNodeId: string | null;
}

export const INITIAL_PIPELINE_STATE: PipelineState = {
  runId: '',
  runStatus: 'IDLE',
  currentStep: 'detect',
  stepProgress: 0,
  events: [],
  findings: [],
  resolutions: {},
  actions: [],
  nodes: [],
  edges: [],
  metrics: {
    run_status: 'IDLE',
    total_customers: 0,
    seeds_flagged: 0,
    findings_count: 0,
    contested_customers: 0,
    actions_proposed: 0,
    actions_approved: 0,
    actions_rejected: 0,
  },
  selectedCustomerId: null,
  selectedNodeId: null,
};

export const STEP_ORDER: StepName[] = [
  'detect',
  'score',
  'distribute',
  'investigate',
  'resolve',
  'target',
  'propose',
  'act',
  'review',
];

export type ActionType =
  | { type: 'PROCESS_EVENT'; event: PipelineEvent }
  | { type: 'SET_RUN_ID'; runId: string }
  | { type: 'SET_RUN_STATUS'; status: PipelineState['runStatus'] }
  | { type: 'SET_GRAPH_DATA'; nodes: GraphNode[]; edges: GraphEdge[] }
  | { type: 'SELECT_CUSTOMER'; customerId: string | null }
  | { type: 'SELECT_NODE'; nodeId: string | null }
  | { type: 'UPDATE_ACTION_STATUS'; actionId: string; status: ProposedAction['status']; executionResult?: any }
  | { type: 'RESET_STATE' };

function mapPhaseToStep(phase: string, step?: string): StepName {
  const p = (phase || '').toLowerCase();
  const s = (step || '').toLowerCase();
  if (s && STEP_ORDER.includes(s as StepName)) return s as StepName;
  if (p.includes('detect') || p.includes('seed')) return 'detect';
  if (p.includes('score') || p.includes('reputation')) return 'score';
  if (p.includes('distribute') || p.includes('assign')) return 'distribute';
  if (p.includes('investigate') || p.includes('agent')) return 'investigate';
  if (p.includes('resolve') || p.includes('resolution')) return 'resolve';
  if (p.includes('target') || p.includes('corroborat')) return 'target';
  if (p.includes('propose') || p.includes('action_propos')) return 'propose';
  if (p.includes('act') || p.includes('execut')) return 'act';
  if (p.includes('review') || p.includes('finish') || p.includes('complete')) return 'review';
  return 'detect';
}

export function pipelineReducer(state: PipelineState, action: ActionType): PipelineState {
  switch (action.type) {
    case 'RESET_STATE':
      return { ...INITIAL_PIPELINE_STATE };

    case 'SET_RUN_ID':
      return { ...state, runId: action.runId };

    case 'SET_RUN_STATUS':
      return {
        ...state,
        runStatus: action.status,
        metrics: { ...state.metrics, run_status: action.status },
      };

    case 'SELECT_CUSTOMER':
      return { ...state, selectedCustomerId: action.customerId };

    case 'SELECT_NODE':
      return { ...state, selectedNodeId: action.nodeId };

    case 'SET_GRAPH_DATA':
      return { ...state, nodes: action.nodes, edges: action.edges };

    case 'UPDATE_ACTION_STATUS': {
      const updatedActions = state.actions.map((act) =>
        act.action_id === action.actionId
          ? {
              ...act,
              status: action.status,
              execution_result: action.executionResult || act.execution_result,
            }
          : act
      );
      const isApproved = action.status === 'APPROVED' || action.status === 'EXECUTED';
      const isRejected = action.status === 'REJECTED';
      return {
        ...state,
        actions: updatedActions,
        runStatus: isApproved ? 'RUNNING' : isRejected ? 'COMPLETED' : state.runStatus,
        metrics: {
          ...state.metrics,
          actions_approved: (state.metrics.actions_approved || 0) + (isApproved ? 1 : 0),
          actions_rejected: (state.metrics.actions_rejected || 0) + (isRejected ? 1 : 0),
        },
      };
    }

    case 'PROCESS_EVENT': {
      const { event } = action;
      const step = mapPhaseToStep(event.phase, event.step);
      const stepProgress = STEP_ORDER.indexOf(step);
      const newEvents = [...state.events, event];

      let newFindings = [...state.findings];
      let newResolutions = { ...state.resolutions };
      let newActions = [...state.actions];
      let newNodes = [...state.nodes];
      let newEdges = [...state.edges];
      let runStatus = state.runStatus;
      let metrics = { ...state.metrics };

      if (event.phase === 'pipeline_start') {
        runStatus = 'RUNNING';
        if (event.data?.run_id) state.runId = event.data.run_id;
      }

      // Handling Seeds / Detect
      if (event.phase === 'detect_seeds_end' && event.data?.seed_count !== undefined) {
        metrics.seeds_flagged = event.data.seed_count;
        if (Array.isArray(event.data.seeds)) {
          for (const s of event.data.seeds) {
            const cid = typeof s === 'string' ? s : s.customer_id;
            if (cid && !newNodes.some((n) => n.data.id === cid)) {
              newNodes.push({
                data: {
                  id: cid,
                  label: cid,
                  type: 'Customer',
                  status: 'seed',
                },
              });
            }
          }
        }
      }

      // Handling Findings
      if (event.phase === 'agent_investigation_end' || event.data?.finding_id) {
        const d = event.data;
        const findingId = d.finding_id || `finding_${newFindings.length + 1}`;
        const existingIdx = newFindings.findIndex((f) => f.finding_id === findingId);
        const findingObj: Finding = {
          finding_id: findingId,
          run_id: state.runId,
          customer_id: d.customer_id,
          agent_id: d.agent_id,
          skill_id: d.skill_id,
          verdict: d.verdict || 'inconclusive',
          confidence: Number(d.confidence || 0),
          evidence_count: Number(d.evidence_count || (d.evidence_keys ? d.evidence_keys.length : 0)),
          evidence_summary: d.evidence_summary || d.reason || '',
          status: 'active',
          backend: d.backend || 'scripted',
          timestamp: event.timestamp,
        };

        if (existingIdx >= 0) {
          newFindings[existingIdx] = findingObj;
        } else {
          newFindings.push(findingObj);
        }

        // Add Finding to graph
        if (!newNodes.some((n) => n.data.id === findingId)) {
          newNodes.push({
            data: {
              id: findingId,
              label: `${findingObj.verdict} (${(findingObj.confidence * 100).toFixed(0)}%)`,
              type: 'Finding',
              verdict: findingObj.verdict,
              confidence: findingObj.confidence,
              status: 'active',
            },
          });
        }
        // Connect Customer -> Finding
        if (d.customer_id) {
          const edgeId = `edge_${d.customer_id}_${findingId}`;
          if (!newEdges.some((e) => e.data.id === edgeId)) {
            newEdges.push({
              data: {
                id: edgeId,
                source: d.customer_id,
                target: findingId,
                type: 'HAS_FINDING',
                label: 'found',
              },
            });
          }
        }

        metrics.findings_count = newFindings.length;
      }

      // Batch findings from investigate_parallel_end
      if (event.phase === 'investigate_parallel_end' && Array.isArray(event.data?.findings)) {
        for (const d of event.data.findings) {
          const fid = d.finding_id;
          if (!fid) continue;
          const idx = newFindings.findIndex((f) => f.finding_id === fid);
          const item: Finding = {
            finding_id: fid,
            run_id: state.runId,
            customer_id: d.customer_id,
            agent_id: d.agent_id,
            skill_id: d.skill_id,
            verdict: d.verdict,
            confidence: d.confidence,
            evidence_count: d.evidence_count,
            evidence_summary: d.reason,
            status: 'active',
            backend: d.backend,
            timestamp: event.timestamp,
          };
          if (idx >= 0) newFindings[idx] = item;
          else newFindings.push(item);
        }
        metrics.findings_count = newFindings.length;
      }

      // Handling Side Resolution
      if (event.phase === 'resolve_side_resolution' || event.data?.winning_side) {
        const d = event.data;
        const cid = d.customer_id;
        if (cid) {
          newResolutions[cid] = {
            customer_id: cid,
            winning_side: d.winning_side,
            side_scores: d.side_scores || {},
            upheld_finding_id: d.upheld_finding_id || '',
            superseded_finding_ids: d.superseded_finding_ids || [],
            resolved_at: event.timestamp,
          };

          // Mark superseded findings
          if (Array.isArray(d.superseded_finding_ids)) {
            const supersededSet = new Set(d.superseded_finding_ids);
            newFindings = newFindings.map((f) =>
              supersededSet.has(f.finding_id) ? { ...f, status: 'superseded' as const } : f
            );
            // Dim nodes in graph
            newNodes = newNodes.map((n) =>
              supersededSet.has(n.data.id) ? { ...n, data: { ...n.data, status: 'superseded', dimmed: true } } : n
            );
            // Mark dashed edges
            newEdges = newEdges.map((e) =>
              supersededSet.has(e.data.target) ? { ...e, data: { ...e.data, dashed: true } } : e
            );
          }
          metrics.contested_customers = Object.keys(newResolutions).length;
        }
      }

      // Handling Action Proposal (Human Gate)
      if (event.phase === 'propose_actions' || event.phase === 'action_proposed' || event.data?.action_id) {
        const d = event.data;
        const actionId = d.action_id || (d.actions && d.actions[0]?.action_id);
        if (actionId) {
          const actionObj: ProposedAction = {
            action_id: actionId,
            run_id: state.runId,
            customer_id: d.customer_id || (d.actions && d.actions[0]?.customer_id) || '',
            action_type: d.action_type || (d.actions && d.actions[0]?.action_type) || 'FREEZE_ACCOUNT',
            confidence: Number(d.confidence || (d.actions && d.actions[0]?.confidence) || 0.95),
            reason: d.reason || (d.actions && d.actions[0]?.reason) || 'Corroborated suspicious ring detection',
            status: d.status || 'PENDING',
            approval_token: d.approval_token || 'token_' + actionId,
            created_at: event.timestamp,
          };

          const existIdx = newActions.findIndex((a) => a.action_id === actionId);
          if (existIdx >= 0) newActions[existIdx] = actionObj;
          else newActions.push(actionObj);

          if (actionObj.status === 'PENDING') {
            runStatus = 'AWAITING_APPROVAL';
          }
          metrics.actions_proposed = newActions.length;
        }
      }

      if (event.phase === 'action_approved') {
        const aid = event.data?.action_id;
        newActions = newActions.map((a) => (a.action_id === aid ? { ...a, status: 'APPROVED' } : a));
        metrics.actions_approved = (metrics.actions_approved || 0) + 1;
      }

      if (event.phase === 'action_rejected') {
        const aid = event.data?.action_id;
        newActions = newActions.map((a) => (a.action_id === aid ? { ...a, status: 'REJECTED' } : a));
        runStatus = 'COMPLETED';
        metrics.actions_rejected = (metrics.actions_rejected || 0) + 1;
      }

      if (event.phase === 'action_executed') {
        const aid = event.data?.action_id;
        newActions = newActions.map((a) =>
          a.action_id === aid
            ? { ...a, status: 'EXECUTED', execution_result: event.data?.execution_result }
            : a
        );
      }

      if (event.phase === 'pipeline_end') {
        runStatus = 'COMPLETED';
      }

      metrics.run_status = runStatus;

      return {
        ...state,
        currentStep: step,
        stepProgress: Math.max(state.stepProgress, stepProgress),
        events: newEvents,
        findings: newFindings,
        resolutions: newResolutions,
        actions: newActions,
        nodes: newNodes,
        edges: newEdges,
        runStatus,
        metrics,
      };
    }

    default:
      return state;
  }
}
