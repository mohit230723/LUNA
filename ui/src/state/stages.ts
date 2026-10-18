import type { RunEvent } from '../api/contract';

export type StageName =
  | 'UNDERSTOOD'
  | 'PLANNED'
  | 'SKILLS ASSIGNED'
  | 'AGENTS WORKING'
  | 'VERIFIED'
  | 'ANSWER';

export type StageStatus = 'pending' | 'running' | 'done' | 'failed' | 'cancelled';

export interface StageState {
  name: StageName;
  status: StageStatus;
  startedAt?: string;
  completedAt?: string;
  durationMs?: number;
}

export const STAGE_NAMES: StageName[] = [
  'UNDERSTOOD',
  'PLANNED',
  'SKILLS ASSIGNED',
  'AGENTS WORKING',
  'VERIFIED',
  'ANSWER',
];

export function getInitialStages(): StageState[] {
  return STAGE_NAMES.map((name) => ({
    name,
    status: 'pending',
  }));
}

export interface StageTrackingContext {
  stages: StageState[];
  hasUnderstood: boolean;
  hasEntitiesResolved: boolean;
  hasPlan: boolean;
  hasSkillAssigned: boolean;
  startedAgents: Set<string>;
  doneAgents: Set<string>;
  failedAgents: Set<string>;
  hasPromoted: boolean;
  hasAnswer: boolean;
}

export function createInitialStageContext(): StageTrackingContext {
  return {
    stages: getInitialStages(),
    hasUnderstood: false,
    hasEntitiesResolved: false,
    hasPlan: false,
    hasSkillAssigned: false,
    startedAgents: new Set(),
    doneAgents: new Set(),
    failedAgents: new Set(),
    hasPromoted: false,
    hasAnswer: false,
  };
}

export function deriveStagesFromEvents(events: RunEvent[]): StageState[] {
  if (!events || events.length === 0) {
    return getInitialStages();
  }

  const sorted = [...events].sort((a, b) => a.seq - b.seq);
  const ctx = createInitialStageContext();

  for (const event of sorted) {
    processEventForStages(ctx, event);
  }

  return ctx.stages;
}

export function processEventForStages(ctx: StageTrackingContext, event: RunEvent): void {
  const ts = event.ts;

  switch (event.type) {
    case 'understood': {
      ctx.hasUnderstood = true;
      if (ctx.hasEntitiesResolved) {
        updateStage(ctx.stages, 'UNDERSTOOD', 'done', ts);
        if (ctx.stages[1]?.status === 'pending') {
          updateStage(ctx.stages, 'PLANNED', 'running', ts);
        }
      } else {
        updateStage(ctx.stages, 'UNDERSTOOD', 'running', ts);
      }
      break;
    }

    case 'entities_resolved': {
      ctx.hasEntitiesResolved = true;
      if (ctx.hasUnderstood) {
        updateStage(ctx.stages, 'UNDERSTOOD', 'done', ts);
        if (ctx.stages[1]?.status === 'pending') {
          updateStage(ctx.stages, 'PLANNED', 'running', ts);
        }
      } else {
        updateStage(ctx.stages, 'UNDERSTOOD', 'running', ts);
      }
      break;
    }

    case 'plan': {
      ctx.hasPlan = true;
      updateStage(ctx.stages, 'UNDERSTOOD', 'done', ts);
      updateStage(ctx.stages, 'PLANNED', 'done', ts);
      if (ctx.stages[2]?.status === 'pending') {
        updateStage(ctx.stages, 'SKILLS ASSIGNED', 'running', ts);
      }
      break;
    }

    case 'skill_assigned': {
      ctx.hasSkillAssigned = true;
      updateStage(ctx.stages, 'UNDERSTOOD', 'done', ts);
      updateStage(ctx.stages, 'PLANNED', 'done', ts);
      updateStage(ctx.stages, 'SKILLS ASSIGNED', 'running', ts);
      break;
    }

    case 'agent_started': {
      const agentId = (event.data['agent_id'] as string) || (event.data['id'] as string) || `agent_${ctx.startedAgents.size + 1}`;
      ctx.startedAgents.add(agentId);
      // first agent_started completes SKILLS ASSIGNED and activates AGENTS WORKING
      updateStage(ctx.stages, 'SKILLS ASSIGNED', 'done', ts);
      updateStage(ctx.stages, 'AGENTS WORKING', 'running', ts);
      break;
    }

    case 'tool_call':
    case 'traversal_step':
    case 'finding': {
      if (ctx.stages[3]?.status === 'pending') {
        updateStage(ctx.stages, 'AGENTS WORKING', 'running', ts);
      }
      break;
    }

    case 'agent_done': {
      const agentId = (event.data['agent_id'] as string) || (event.data['id'] as string);
      if (agentId) ctx.doneAgents.add(agentId);
      checkAgentsWorkingDone(ctx, ts);
      break;
    }

    case 'agent_failed': {
      const agentId = (event.data['agent_id'] as string) || (event.data['id'] as string);
      if (agentId) ctx.failedAgents.add(agentId);
      checkAgentsWorkingDone(ctx, ts);
      break;
    }

    case 'promoted': {
      ctx.hasPromoted = true;
      updateStage(ctx.stages, 'AGENTS WORKING', 'done', ts);
      updateStage(ctx.stages, 'VERIFIED', 'done', ts);
      if (ctx.stages[5]?.status === 'pending') {
        updateStage(ctx.stages, 'ANSWER', 'running', ts);
      }
      break;
    }

    case 'answer': {
      ctx.hasAnswer = true;
      updateStage(ctx.stages, 'VERIFIED', 'done', ts);
      updateStage(ctx.stages, 'ANSWER', 'done', ts);
      break;
    }

    case 'completed': {
      if (ctx.hasAnswer) {
        updateStage(ctx.stages, 'ANSWER', 'done', ts);
      }
      break;
    }

    case 'failed': {
      // Find current running stage and mark it failed
      for (const stage of ctx.stages) {
        if (stage.status === 'running') {
          stage.status = 'failed';
          stage.completedAt = ts;
          break;
        }
      }
      break;
    }

    case 'cancelled': {
      for (const stage of ctx.stages) {
        if (stage.status === 'running') {
          stage.status = 'cancelled';
          stage.completedAt = ts;
          break;
        }
      }
      break;
    }

    default:
      break;
  }
}

function checkAgentsWorkingDone(ctx: StageTrackingContext, ts: string): void {
  if (ctx.startedAgents.size > 0) {
    const finishedCount = ctx.doneAgents.size + ctx.failedAgents.size;
    if (finishedCount >= ctx.startedAgents.size) {
      updateStage(ctx.stages, 'AGENTS WORKING', 'done', ts);
      if (ctx.stages[4]?.status === 'pending') {
        updateStage(ctx.stages, 'VERIFIED', 'running', ts);
      }
    }
  }
}

function updateStage(
  stages: StageState[],
  name: StageName,
  status: StageStatus,
  timestamp?: string
): void {
  const stage = stages.find((s) => s.name === name);
  if (!stage) return;

  if (stage.status === 'done' && status === 'running') {
    return; // Do not regress completed stage
  }

  stage.status = status;

  if (status === 'running' && !stage.startedAt && timestamp) {
    stage.startedAt = timestamp;
  }

  if (status === 'done' || status === 'failed' || status === 'cancelled') {
    if (timestamp) {
      stage.completedAt = timestamp;
      if (stage.startedAt) {
        stage.durationMs =
          new Date(timestamp).getTime() - new Date(stage.startedAt).getTime();
      }
    }
  }
}
