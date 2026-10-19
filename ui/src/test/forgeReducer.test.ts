import { describe, it, expect } from 'vitest';
import { forgeReducer, initialForgeState, type ForgeState } from '../state/forgeReducer';
import type { ForgeEvent, ForgeRunDetail, ForgeTask } from '../api/contract';

function mkTask(id: string, status: string): ForgeTask {
  return {
    task_id: id, title: id, capability: 'x', skill_id: '', depends_on: [], wave: 0, status,
    claimed_by: '', agent_label: '', lease_expires_at: '', assignment: null, candidates: [], result: null,
  };
}
function mkRun(): ForgeRunDetail {
  return {
    run: { run_id: 'r1', prompt: 'p', status: 'running' },
    tasks: [mkTask('implement_frontend', 'claimed'), mkTask('verify_contracts', 'pending')],
    report: null,
  };
}
const ev = (seq: number, type: string, data: Record<string, unknown>): ForgeEvent => ({
  seq, ts: '2026-01-01T00:00:00Z', type, data,
});
const withRun = (): ForgeState => forgeReducer(initialForgeState, { type: 'run', run: mkRun() });
const task = (s: ForgeState, id: string) => s.activeRun!.tasks.find((t) => t.task_id === id)!;

describe('forgeReducer', () => {
  it('patches task status for the active run only', () => {
    let s = withRun();
    s = forgeReducer(s, { type: 'event', event: ev(1, 'task_updated', { run_id: 'other', task_id: 'implement_frontend', status: 'failed' }) });
    expect(task(s, 'implement_frontend').status).toBe('claimed');
    s = forgeReducer(s, { type: 'event', event: ev(2, 'task_updated', { run_id: 'r1', task_id: 'implement_frontend', status: 'done', result: { summary: 'ok' } }) });
    expect(task(s, 'implement_frontend').status).toBe('done');
    expect(task(s, 'implement_frontend').result).toEqual({ summary: 'ok' });
  });

  it('ignores duplicate or older seq', () => {
    let s = withRun();
    s = forgeReducer(s, { type: 'event', event: ev(5, 'task_updated', { run_id: 'r1', task_id: 'verify_contracts', status: 'ready' }) });
    s = forgeReducer(s, { type: 'event', event: ev(5, 'task_updated', { run_id: 'r1', task_id: 'verify_contracts', status: 'done' }) });
    s = forgeReducer(s, { type: 'event', event: ev(3, 'task_updated', { run_id: 'r1', task_id: 'verify_contracts', status: 'failed' }) });
    expect(task(s, 'verify_contracts').status).toBe('ready');
    expect(s.lastSeq).toBe(5);
  });

  it('upserts agents by session_id', () => {
    let s = initialForgeState;
    s = forgeReducer(s, { type: 'event', event: ev(1, 'agent_connected', { session_id: 'a', client_name: 'claude-code', client_version: '1' }) });
    s = forgeReducer(s, { type: 'event', event: ev(2, 'agent_seen', { session_id: 'a', client_name: 'claude-code' }) });
    expect(s.agents).toHaveLength(1);
    expect(s.agents[0]!.connected).toBe(true);
  });

  it('prepends a summary on run_created', () => {
    const s = forgeReducer(initialForgeState, { type: 'event', event: ev(1, 'run_created', { run_id: 'r2', prompt: 'hi' }) });
    expect(s.runs[0]!.run_id).toBe('r2');
  });

  it('stores report on run_assembled', () => {
    let s = withRun();
    s = forgeReducer(s, { type: 'run', run: mkRun() });
    s = forgeReducer(s, { type: 'runs', runs: [{ run_id: 'r1', prompt: 'p', status: 'running', created_at: '', task_count: 2 }] });
    const report = { run_id: 'r1', status: 'complete' as const, missing: [], tasks: [], overlaps: {}, gaps: [], summary: 's' };
    s = forgeReducer(s, { type: 'event', event: ev(9, 'run_assembled', { run_id: 'r1', report }) });
    expect(s.activeRun!.report).toEqual(report);
    // Backend's term for a run whose report is complete.
    expect(s.runs[0]!.status).toBe('assembled');
    expect(s.activeRun!.run.status).toBe('assembled');
  });

  it('leaves run status alone for an incomplete report', () => {
    let s = withRun();
    s = forgeReducer(s, { type: 'runs', runs: [{ run_id: 'r1', prompt: 'p', status: 'running', created_at: '', task_count: 2 }] });
    const report = { run_id: 'r1', status: 'incomplete' as const, missing: ['x'], tasks: [], overlaps: {}, gaps: [], summary: 's' };
    s = forgeReducer(s, { type: 'event', event: ev(2, 'run_assembled', { run_id: 'r1', report }) });
    expect(s.runs[0]!.status).toBe('running');
    expect(s.activeRun!.report).toEqual(report);
  });

  it('resets lastSeq on hello so a restarted backend is heard again', () => {
    let s = withRun();
    s = forgeReducer(s, { type: 'event', event: ev(50, 'task_updated', { run_id: 'r1', task_id: 'verify_contracts', status: 'ready' }) });
    expect(s.lastSeq).toBe(50);
    s = forgeReducer(s, { type: 'hello', seq: 0 });
    expect(s.lastSeq).toBe(0);
    s = forgeReducer(s, { type: 'event', event: ev(1, 'task_updated', { run_id: 'r1', task_id: 'verify_contracts', status: 'done' }) });
    expect(task(s, 'verify_contracts').status).toBe('done');
    expect(s.lastSeq).toBe(1);
  });

  it('tracks connection state', () => {
    expect(forgeReducer(initialForgeState, { type: 'connection', state: 'reconnecting' }).connection).toBe('reconnecting');
  });
});
