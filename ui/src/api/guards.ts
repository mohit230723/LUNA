import { Block, RunEvent, RunEventType } from './contract';

const VALID_RUN_EVENT_TYPES: Set<string> = new Set([
  'routed',
  'requirements',
  'blueprint',
  'skill_assigned',
  'skill_fit',
  'agent_started',
  'agent_progress',
  'tool_call',
  'traversal_step',
  'artifact_written',
  'contract_violation',
  'remediation',
  'agent_done',
  'agent_failed',
  'promoted',
  'conflict_resolved',
  'answer',
  'action_proposed',
  'needs_input',
  'approved',
  'executed',
  'learned',
  'completed',
  'failed',
  'cancelled',
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
  if (typeof obj.data !== 'object' || obj.data === null) {
    return false;
  }
  return true;
}

export function filterValidBlocks(blocks: unknown[]): Block[] {
  if (!Array.isArray(blocks)) return [];
  const valid: Block[] = [];
  for (const b of blocks) {
    if (isBlock(b)) {
      valid.push(b);
    } else {
      if (import.meta.env.DEV) {
        console.warn('Unknown or malformed block ignored:', b);
      }
    }
  }
  return valid;
}
