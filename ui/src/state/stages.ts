import { RunEvent, RunEventType } from '../api/contract';

export type StageName =
  | 'ROUTED'
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
  'ROUTED',
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
  hasRouted: boolean;
  hasRequirements: boolean;
  hasBlueprint: boolean;
  hasSkillAssigned: boolean;
  assignedSubjects: Set<string>;
  fittedSubjects: Set<string>;
  startedAgents: Set<string>;
  doneAgents: Set<string>;
  failedAgents: Set<string>;
  hasVerificationActivity: boolean;
  hasAnswer: boolean;
  isRunCompleted: boolean;
  isRunFailed: boolean;
  isRunCancelled: boolean;
}

export function createInitialStageContext(): StageTrackingContext {
  return {
    stages: getInitialStages(),
    hasRouted: false,
    hasRequirements: false,
    hasBlueprint: false,
    hasSkillAssigned: false,
    assignedSubjects: new Set(),
    fittedSubjects: new Set(),
    startedAgents: new Set(),
    doneAgents: new Set(),
    failedAgents: new Set(),
    hasVerificationActivity: false,
    hasAnswer: false,
    isRunCompleted: false,
    isRunFailed: false,
    isRunCancelled: false,
  };
}

export function deriveStagesFromEvents(events: RunEvent[]): StageState[] {
  if (!events || events.length === 0) {
    return getInitialStages();
  }

  // Sort events by sequence number
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
    case 'routed': {
      ctx.hasRouted = true;
      updateStage(ctx.stages, 'ROUTED', 'done', ts);
      // Next stage becomes active
      if (ctx.stages[1]?.status === 'pending') {
        updateStage(ctx.stages, 'PLANNED', 'running', ts);
      }
      break;
    }

    case 'requirements': {
      ctx.hasRequirements = true;
      if (ctx.stages[1]?.status === 'pending') {
        updateStage(ctx.stages, 'PLANNED', 'running', ts);
      }
      break;
    }

    case 'blueprint': {
      ctx.hasBlueprint = true;
      if (ctx.hasRequirements && ctx.hasBlueprint) {
        updateStage(ctx.stages, 'PLANNED', 'done', ts);
      }
      break;
    }

    case 'skill_assigned': {
      ctx.hasSkillAssigned = true;
      // In investigate runs, first skill_assigned completes PLANNED
      updateStage(ctx.stages, 'PLANNED', 'done', ts);
      updateStage(ctx.stages, 'SKILLS ASSIGNED', 'running', ts);

      const assignments = event.data['assignments'] as Array<{ subject?: string }> | undefined;
      if (Array.isArray(assignments)) {
        assignments.forEach((a) => {
          if (a.subject) ctx.assignedSubjects.add(a.subject);
        });
      }
      break;
    }

    case 'skill_fit': {
      const subject = event.data['subject'] as string | undefined;
      if (subject) ctx.fittedSubjects.add(subject);

      // If all assigned subjects are fitted
      if (
        ctx.assignedSubjects.size > 0 &&
        ctx.fittedSubjects.size >= ctx.assignedSubjects.size
      ) {
        updateStage(ctx.stages, 'SKILLS ASSIGNED', 'done', ts);
      }
      break;
    }

    case 'agent_started': {
      // First agent_started completes PLANNED and SKILLS ASSIGNED if they were still running or pending
      if (ctx.stages[1]?.status === 'running' || ctx.stages[1]?.status === 'pending') {
        updateStage(ctx.stages, 'PLANNED', 'done', ts);
      }
      if (ctx.stages[2]?.status === 'running' || ctx.stages[2]?.status === 'pending') {
        updateStage(ctx.stages, 'SKILLS ASSIGNED', 'done', ts);
      }
      updateStage(ctx.stages, 'AGENTS WORKING', 'running', ts);

      const agentId = (event.data['agent_id'] as string) || (event.data['id'] as string);
      if (agentId) ctx.startedAgents.add(agentId);
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

    case 'promoted':
    case 'contract_violation':
    case 'conflict_resolved':
    case 'remediation': {
      ctx.hasVerificationActivity = true;
      if (ctx.stages[4]?.status === 'pending') {
        updateStage(ctx.stages, 'VERIFIED', 'running', ts);
      }
      break;
    }

    case 'answer': {
      ctx.hasAnswer = true;
      // Answer arrival marks VERIFIED done
      updateStage(ctx.stages, 'VERIFIED', 'done', ts);
      updateStage(ctx.stages, 'ANSWER', 'done', ts);
      break;
    }

    case 'completed': {
      ctx.isRunCompleted = true;
      // Mark any unfinished stages done
      ctx.stages.forEach((stage) => {
        if (stage.status === 'pending' || stage.status === 'running') {
          updateStage(ctx.stages, stage.name, 'done', ts);
        }
      });
      break;
    }

    case 'failed': {
      ctx.isRunFailed = true;
      // Mark active stage as failed
      markActiveStageStatus(ctx.stages, 'failed', ts);
      break;
    }

    case 'cancelled': {
      ctx.isRunCancelled = true;
      // Mark active stage as cancelled
      markActiveStageStatus(ctx.stages, 'cancelled', ts);
      break;
    }
  }
}

function checkAgentsWorkingDone(ctx: StageTrackingContext, ts: string) {
  const totalFinished = ctx.doneAgents.size + ctx.failedAgents.size;
  if (ctx.startedAgents.size > 0 && totalFinished >= ctx.startedAgents.size) {
    if (ctx.failedAgents.size === ctx.startedAgents.size && ctx.startedAgents.size > 0) {
      updateStage(ctx.stages, 'AGENTS WORKING', 'failed', ts);
    } else {
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
) {
  const stage = stages.find((s) => s.name === name);
  if (!stage) return;

  if (status === 'running' && stage.status === 'pending') {
    stage.status = 'running';
    stage.startedAt = timestamp;
  } else if (status === 'done' || status === 'failed' || status === 'cancelled') {
    if (!stage.startedAt) stage.startedAt = timestamp;
    stage.status = status;
    stage.completedAt = timestamp;
    if (stage.startedAt && stage.completedAt) {
      const start = new Date(stage.startedAt).getTime();
      const end = new Date(stage.completedAt).getTime();
      if (!isNaN(start) && !isNaN(end) && end >= start) {
        stage.durationMs = end - start;
      }
    }
  }
}

function markActiveStageStatus(stages: StageState[], status: 'failed' | 'cancelled', timestamp?: string) {
  let activeFound = false;
  for (const s of stages) {
    if (s.status === 'running') {
      s.status = status;
      s.completedAt = timestamp;
      activeFound = true;
      break;
    }
  }
  if (!activeFound) {
    for (const s of stages) {
      if (s.status === 'pending') {
        s.status = status;
        s.completedAt = timestamp;
        break;
      }
    }
  }
}
