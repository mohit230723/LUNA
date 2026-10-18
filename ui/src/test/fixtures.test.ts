import { describe, it, expect } from 'vitest';
import { mockApi } from '../api/mock/mockApi';
import { F1_BLOCKS, F1_TRACE } from '../api/mock/fixtures/f1_investigate';
import { F2_TRACE } from '../api/mock/fixtures/f2_build';
import { F3_TRACE } from '../api/mock/fixtures/f3_followup';
import { ATLAS_SKILLS_FIXTURE } from '../api/mock/fixtures/atlas_skills';

describe('MockApi and Fixture Consistency', () => {
  it('F1: every cited CID in answer exists in trace nodes', () => {
    const answerBlock = F1_BLOCKS.find((b) => b.type === 'answer');
    expect(answerBlock).toBeDefined();
    if (answerBlock && answerBlock.type === 'answer') {
      const citedCids = answerBlock.data.cited_cids;
      expect(citedCids.length).toBeGreaterThan(0);
      const traceNodeIds = new Set(F1_TRACE.nodes.map((n) => n.id));
      for (const cid of citedCids) {
        expect(traceNodeIds.has(cid)).toBe(true);
      }
    }
  });

  it('F1: every traversal step endpoint exists in trace nodes', () => {
    const traceNodeIds = new Set(F1_TRACE.nodes.map((n) => n.id));
    for (const step of F1_TRACE.steps) {
      expect(traceNodeIds.has(step.from)).toBe(true);
      expect(traceNodeIds.has(step.to)).toBe(true);
    }
  });

  it('F2: every blueprint step endpoint exists in blueprint trace nodes', () => {
    const traceNodeIds = new Set(F2_TRACE.nodes.map((n) => n.id));
    for (const step of F2_TRACE.steps) {
      expect(traceNodeIds.has(step.from)).toBe(true);
      expect(traceNodeIds.has(step.to)).toBe(true);
    }
  });

  it('F3: every follow-up step endpoint exists in trace nodes', () => {
    const traceNodeIds = new Set(F3_TRACE.nodes.map((n) => n.id));
    for (const step of F3_TRACE.steps) {
      expect(traceNodeIds.has(step.from)).toBe(true);
      expect(traceNodeIds.has(step.to)).toBe(true);
    }
  });

  it('Atlas fixture has at least 22 skills across both packs', () => {
    expect(ATLAS_SKILLS_FIXTURE.length).toBeGreaterThanOrEqual(22);
    const restricted = ATLAS_SKILLS_FIXTURE.filter((s) => s.restricted);
    expect(restricted.length).toBeGreaterThanOrEqual(2);
    expect(restricted.some((s) => s.id === 'bulk-linker')).toBe(true);
    expect(restricted.some((s) => s.id === 'shell-runner')).toBe(true);
  });

  it('MockApi routes prompts accurately based on keywords', async () => {
    const { id: convId } = await mockApi.createConversation();

    // 1. Investigate
    const invRes = await mockApi.sendMessage(convId, {
      content: 'Who is connected to customer cust-000?',
      options: { pack: 'auto', mode: 'scripted', strict_llm: false, parallel: 3 },
    });
    expect(invRes.run_id).toBe('run_investigate_001');

    // 2. Follow-up on cust-003
    const followRes = await mockApi.sendMessage(convId, {
      content: 'What about cust-003?',
      options: { pack: 'auto', mode: 'scripted', strict_llm: false, parallel: 3 },
    });
    expect(followRes.run_id).toBe('run_followup_003');

    // 3. Build prompt
    const buildRes = await mockApi.sendMessage(convId, {
      content: 'Build a todo app: React frontend and Express backend',
      options: { pack: 'auto', mode: 'scripted', strict_llm: false, parallel: 3 },
    });
    expect(buildRes.run_id).toBe('run_build_002');

    // 4. Clarification prompt (Svelte)
    const clarRes = await mockApi.sendMessage(convId, {
      content: 'Build a project using Svelte',
      options: { pack: 'auto', mode: 'scripted', strict_llm: false, parallel: 3 },
    });
    expect(clarRes.run_id).toBe('run_clarification_004');
  });

  it('MockApi approves actions and returns non-trivial metrics', async () => {
    const res = await mockApi.approveAction('run_investigate_001', 'act_flag_001', 'Auditor Alice');
    expect(res.ok).toBe(true);
    expect(res.metrics?.precision).toBe(1.0);
    expect(res.metrics?.recall).toBe(0.375);
    expect(res.metrics?.f1).toBe(0.545);
  });
});
