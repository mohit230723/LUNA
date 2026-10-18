import { describe, it, expect } from 'vitest';
import {
  deriveStagesFromEvents,
  getInitialStages,
} from '../state/stages';
import { createInitialRunState, runReducer } from '../state/runReducer';
import { INITIAL_TRACE_STATE, traceReducer } from '../state/traceReducer';
import { F1_EVENTS } from '../api/mock/fixtures/f1_investigate';
import { F2_EVENTS } from '../api/mock/fixtures/f2_build';
import { F5_ALL_FAIL_EVENTS } from '../api/mock/fixtures/f5_failure';
import { RunEvent } from '../api/contract';

describe('State Reducers and Stage Derivation', () => {
  it('before any event, all stages are pending', () => {
    const stages = getInitialStages();
    expect(stages).toHaveLength(6);
    stages.forEach((s) => {
      expect(s.status).toBe('pending');
    });
  });

  it('F1 Investigate: stage derivation over full event list ends with all stages done', () => {
    const stages = deriveStagesFromEvents(F1_EVENTS);
    expect(stages).toHaveLength(6);
    stages.forEach((s) => {
      expect(s.status).toBe('done');
    });
  });

  it('F2 Build: stage derivation over full event list ends with all stages done', () => {
    const stages = deriveStagesFromEvents(F2_EVENTS);
    expect(stages).toHaveLength(6);
    stages.forEach((s) => {
      expect(s.status).toBe('done');
    });
  });

  it('ignores duplicate events with same run_id and seq', () => {
    let state = createInitialRunState('test_run');
    const ev: RunEvent = {
      run_id: 'test_run',
      seq: 1,
      ts: '2026-10-18T10:00:00Z',
      type: 'routed',
      data: { pack: 'investigate' },
    };

    state = runReducer(state, { type: 'ADD_EVENT', event: ev });
    expect(state.events).toHaveLength(1);

    // Add exact duplicate
    state = runReducer(state, { type: 'ADD_EVENT', event: ev });
    expect(state.events).toHaveLength(1);
  });

  it('orders out-of-order events by sequence number', () => {
    const ev1: RunEvent = { run_id: 'r', seq: 1, ts: '2026-10-18T10:00:00Z', type: 'routed', data: {} };
    const ev2: RunEvent = { run_id: 'r', seq: 2, ts: '2026-10-18T10:00:01Z', type: 'skill_assigned', data: {} };

    // Pass in reverse order
    const stages = deriveStagesFromEvents([ev2, ev1]);
    expect(stages[0]?.status).toBe('done');
    expect(stages[1]?.status).toBe('done');
  });

  it('marks active stage as failed when all agents fail', () => {
    const stages = deriveStagesFromEvents(F5_ALL_FAIL_EVENTS);
    const failedStage = stages.find((s) => s.status === 'failed');
    expect(failedStage).toBeDefined();
    expect(failedStage?.name).toBe('AGENTS WORKING');
  });

  it('traceReducer handles play, pause, step forward, seek, speed, and showAll', () => {
    let state = { ...INITIAL_TRACE_STATE, totalSteps: 6, revealedStepCount: 0 };

    // Step forward
    state = traceReducer(state, { type: 'STEP_FORWARD' });
    expect(state.revealedStepCount).toBe(1);
    expect(state.selectedStepSeq).toBe(1);

    // Play & Pause
    state = traceReducer(state, { type: 'PLAY' });
    expect(state.playing).toBe(true);

    state = traceReducer(state, { type: 'PAUSE' });
    expect(state.playing).toBe(false);

    // Seek step
    state = traceReducer(state, { type: 'SEEK_STEP', stepIndex: 4 });
    expect(state.revealedStepCount).toBe(4);
    expect(state.selectedStepSeq).toBe(4);

    // Step back
    state = traceReducer(state, { type: 'STEP_BACK' });
    expect(state.revealedStepCount).toBe(3);

    // Speed toggle
    state = traceReducer(state, { type: 'SET_SPEED', speed: 5 });
    expect(state.speed).toBe(5);

    // Show all
    state = traceReducer(state, { type: 'TOGGLE_SHOW_ALL' });
    expect(state.showAll).toBe(true);
    expect(state.revealedStepCount).toBe(6);
  });
});
