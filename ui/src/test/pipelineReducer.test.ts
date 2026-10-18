import { describe, it, expect } from 'vitest';
import {
  INITIAL_PIPELINE_STATE,
  pipelineReducer,
  STEP_ORDER,
} from '../state/pipelineReducer';
import { PipelineEvent } from '../types';

describe('pipelineReducer', () => {
  it('initializes with default values and idle status', () => {
    expect(INITIAL_PIPELINE_STATE.runStatus).toBe('IDLE');
    expect(INITIAL_PIPELINE_STATE.currentStep).toBe('detect');
    expect(INITIAL_PIPELINE_STATE.findings).toHaveLength(0);
    expect(INITIAL_PIPELINE_STATE.actions).toHaveLength(0);
  });

  it('advances currentStep and processes seeds on detect_seeds_end', () => {
    const event: PipelineEvent = {
      step: 'detect',
      phase: 'detect_seeds_end',
      data: {
        seed_count: 2,
        seeds: ['cust_1001', 'cust_1002'],
      },
      timestamp: '2026-10-18T08:00:00Z',
    };

    const state = pipelineReducer(INITIAL_PIPELINE_STATE, {
      type: 'PROCESS_EVENT',
      event,
    });

    expect(state.metrics.seeds_flagged).toBe(2);
    expect(state.nodes).toHaveLength(2);
    expect(state.nodes[0].data.id).toBe('cust_1001');
    expect(state.nodes[0].data.status).toBe('seed');
  });

  it('records agent findings and creates customer-finding edges', () => {
    const event: PipelineEvent = {
      step: 'investigate',
      phase: 'agent_investigation_end',
      data: {
        finding_id: 'f_test_01',
        customer_id: 'cust_1001',
        agent_id: 'agent_fraud_0',
        skill_id: 'skill_graph_pattern',
        verdict: 'suspicious',
        confidence: 0.88,
        evidence_count: 3,
        reason: 'Shared device with known mule',
      },
      timestamp: '2026-10-18T08:00:01Z',
    };

    const state = pipelineReducer(INITIAL_PIPELINE_STATE, {
      type: 'PROCESS_EVENT',
      event,
    });

    expect(state.findings).toHaveLength(1);
    expect(state.findings[0].finding_id).toBe('f_test_01');
    expect(state.findings[0].verdict).toBe('suspicious');
    expect(state.findings[0].confidence).toBe(0.88);
    expect(state.nodes.some((n) => n.data.id === 'f_test_01')).toBe(true);
    expect(state.edges.some((e) => e.data.source === 'cust_1001' && e.data.target === 'f_test_01')).toBe(true);
  });

  it('marks losing findings superseded and dims them on side resolution', () => {
    // Start with 2 findings for cust_1001: one suspicious, one benign
    let state = pipelineReducer(INITIAL_PIPELINE_STATE, {
      type: 'PROCESS_EVENT',
      event: {
        step: 'investigate',
        phase: 'agent_investigation_end',
        data: {
          finding_id: 'f_susp_01',
          customer_id: 'cust_1001',
          verdict: 'suspicious',
          confidence: 0.9,
          evidence_count: 4,
        },
        timestamp: '2026-10-18T08:00:01Z',
      },
    });

    state = pipelineReducer(state, {
      type: 'PROCESS_EVENT',
      event: {
        step: 'investigate',
        phase: 'agent_investigation_end',
        data: {
          finding_id: 'f_benign_01',
          customer_id: 'cust_1001',
          verdict: 'benign',
          confidence: 0.6,
          evidence_count: 1,
        },
        timestamp: '2026-10-18T08:00:02Z',
      },
    });

    expect(state.findings).toHaveLength(2);

    // Resolve side resolution with suspicious winning
    state = pipelineReducer(state, {
      type: 'PROCESS_EVENT',
      event: {
        step: 'resolve',
        phase: 'resolve_side_resolution',
        data: {
          customer_id: 'cust_1001',
          winning_side: 'suspicious',
          side_scores: {
            suspicious: { total_score: 0.85, confidence: 0.9, evidence_count: 4, skill_score: 1.0, verdict: 'suspicious', best_finding_id: 'f_susp_01' },
            benign: { total_score: 0.45, confidence: 0.6, evidence_count: 1, skill_score: 0.5, verdict: 'benign', best_finding_id: 'f_benign_01' },
          },
          upheld_finding_id: 'f_susp_01',
          superseded_finding_ids: ['f_benign_01'],
        },
        timestamp: '2026-10-18T08:00:03Z',
      },
    });

    expect(state.resolutions['cust_1001']).toBeDefined();
    expect(state.resolutions['cust_1001'].winning_side).toBe('suspicious');
    
    // Check superseded finding in state
    const benignFinding = state.findings.find((f) => f.finding_id === 'f_benign_01');
    expect(benignFinding?.status).toBe('superseded');

    const suspFinding = state.findings.find((f) => f.finding_id === 'f_susp_01');
    expect(suspFinding?.status).toBe('active');

    // Check dimmed node in graph
    const benignNode = state.nodes.find((n) => n.data.id === 'f_benign_01');
    expect(benignNode?.data.dimmed).toBe(true);
  });

  it('transitions to AWAITING_APPROVAL when an action is proposed', () => {
    const event: PipelineEvent = {
      step: 'propose',
      phase: 'propose_actions',
      data: {
        action_id: 'act_freeze_1001',
        customer_id: 'cust_1001',
        action_type: 'FREEZE_ACCOUNT',
        confidence: 0.92,
        reason: 'Corroborated fraud ring member',
        status: 'PENDING',
      },
      timestamp: '2026-10-18T08:00:04Z',
    };

    const state = pipelineReducer(INITIAL_PIPELINE_STATE, {
      type: 'PROCESS_EVENT',
      event,
    });

    expect(state.runStatus).toBe('AWAITING_APPROVAL');
    expect(state.actions).toHaveLength(1);
    expect(state.actions[0].action_id).toBe('act_freeze_1001');
    expect(state.actions[0].status).toBe('PENDING');
  });

  it('updates action status and metrics on approve / reject', () => {
    let state = pipelineReducer(INITIAL_PIPELINE_STATE, {
      type: 'PROCESS_EVENT',
      event: {
        step: 'propose',
        phase: 'propose_actions',
        data: {
          action_id: 'act_1',
          customer_id: 'cust_1001',
          action_type: 'FREEZE_ACCOUNT',
          status: 'PENDING',
        },
        timestamp: '2026-10-18T08:00:00Z',
      },
    });

    state = pipelineReducer(state, {
      type: 'UPDATE_ACTION_STATUS',
      actionId: 'act_1',
      status: 'EXECUTED',
      executionResult: { status: 'ACCOUNT_FROZEN' },
    });

    expect(state.actions[0].status).toBe('EXECUTED');
    expect(state.actions[0].execution_result?.status).toBe('ACCOUNT_FROZEN');
    expect(state.metrics.actions_approved).toBe(1);
  });
});
