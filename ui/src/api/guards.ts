import { Block, RunEvent, RunEventType } from './contract';

const VALID_RUN_EVENT_TYPES: Set<string> = new Set([
  'understood',
  'entities_resolved',
  'plan',
  'skill_assigned',
  'agent_started',
  'tool_call',
  'traversal_step',
  'finding',
  'agent_done',
  'agent_failed',
  'promoted',
  'answer',
  'needs_input',
  'completed',
  'failed',
  'cancelled',
  // keep legacy event names tolerated for graceful transitions
  'routed',
  'requirements',
  'blueprint',
  'skill_fit',
  'agent_progress',
  'artifact_written',
  'contract_violation',
  'remediation',
  'conflict_resolved',
  'action_proposed',
  'approved',
  'executed',
  'learned',
]);

const VALID_BLOCK_TYPES: Set<string> = new Set([
  'text',
  'routing',
  'plan',
  'skills',
  'agents',
  'trace_preview',
  'findings',
  'files',
  'action_request',
  'needs_input',
  'warning',
  'answer',
  'graph_summary',
]);

export function isRunEventType(val: unknown): val is RunEventType {
  return typeof val === 'string' && VALID_RUN_EVENT_TYPES.has(val);
}

export function isRunEvent(val: unknown): val is RunEvent {
  if (typeof val !== 'object' || val === null) {
    return false;
  }
  const obj = val as Record<string, unknown>;
  return (
    typeof obj.run_id === 'string' &&
    typeof obj.seq === 'number' &&
    typeof obj.ts === 'string' &&
    isRunEventType(obj.type) &&
    typeof obj.data === 'object' &&
    obj.data !== null
  );
}

export function isBlock(val: unknown): val is Block {
  if (typeof val !== 'object' || val === null) {
    return false;
  }
  const obj = val as Record<string, unknown>;
  if (typeof obj.type !== 'string' || !VALID_BLOCK_TYPES.has(obj.type)) {
    return false;
  }
  return typeof obj.data === 'object' && obj.data !== null;
}

export function filterValidBlocks(blocks: unknown): Block[] {
  if (!Array.isArray(blocks)) {
    return [];
  }
  return blocks.filter(isBlock);
}
