import { Block } from '../../contract';

export const F5_PARTIAL_FAIL_ID = 'run_fail_partial_005';
export const F5_ALL_FAIL_ID = 'run_fail_all_005';

export const F5_PARTIAL_BLOCKS: Block[] = [
  {
    type: 'routing',
    data: { pack: 'investigate', intent: 'Deep network traversal', confidence: 0.9, backend: 'scripted' },
  },
  {
    type: 'agents',
    data: {
      agents: [
        { id: 'agent_tracer', skill: 'connection-tracer', status: 'done', tool_calls: 3, backend: 'scripted' },
        { id: 'agent_deep', skill: 'graph-rag-investigator', status: 'failed', tool_calls: 1, reason: 'timeout after 120 s', backend: 'scripted' },
      ],
    },
  },
  {
    type: 'warning',
    data: {
      text: 'Partial execution failure: Agent agent_deep (graph-rag-investigator) timed out after 120 s. Results derived from remaining agents.',
    },
  },
  {
    type: 'answer',
    data: {
      text: 'Analysis completed using connection tracer data. Secondary GraphRAG inspection was skipped due to agent timeout.',
      cited_cids: [],
      backend: 'scripted',
    },
  },
];

export const F5_PARTIAL_EVENTS: any[] = [
  { run_id: F5_PARTIAL_FAIL_ID, seq: 1, ts: '2026-10-18T09:40:00Z', type: 'routed', backend: 'scripted', data: { pack: 'investigate' } },
  { run_id: F5_PARTIAL_FAIL_ID, seq: 2, ts: '2026-10-18T09:40:01Z', type: 'agent_started', backend: 'scripted', data: { agent_id: 'agent_tracer', skill: 'connection-tracer' } },
  { run_id: F5_PARTIAL_FAIL_ID, seq: 3, ts: '2026-10-18T09:40:02Z', type: 'agent_started', backend: 'scripted', data: { agent_id: 'agent_deep', skill: 'graph-rag-investigator' } },
  { run_id: F5_PARTIAL_FAIL_ID, seq: 4, ts: '2026-10-18T09:40:03Z', type: 'agent_failed', backend: 'scripted', data: { agent_id: 'agent_deep', reason: 'timeout after 120 s' } },
  { run_id: F5_PARTIAL_FAIL_ID, seq: 5, ts: '2026-10-18T09:40:04Z', type: 'agent_done', backend: 'scripted', data: { agent_id: 'agent_tracer' } },
  { run_id: F5_PARTIAL_FAIL_ID, seq: 6, ts: '2026-10-18T09:40:05Z', type: 'answer', backend: 'scripted', data: { text: F5_PARTIAL_BLOCKS[3]?.data } },
  { run_id: F5_PARTIAL_FAIL_ID, seq: 7, ts: '2026-10-18T09:40:06Z', type: 'completed', backend: 'scripted', data: { run_id: F5_PARTIAL_FAIL_ID } },
];

export const F5_ALL_FAIL_EVENTS: any[] = [
  { run_id: F5_ALL_FAIL_ID, seq: 1, ts: '2026-10-18T09:45:00Z', type: 'routed', backend: 'scripted', data: { pack: 'investigate' } },
  { run_id: F5_ALL_FAIL_ID, seq: 2, ts: '2026-10-18T09:45:01Z', type: 'agent_started', backend: 'scripted', data: { agent_id: 'agent_tracer', skill: 'connection-tracer' } },
  { run_id: F5_ALL_FAIL_ID, seq: 3, ts: '2026-10-18T09:45:02Z', type: 'agent_failed', backend: 'scripted', data: { agent_id: 'agent_tracer', reason: 'connection refused to graph database' } },
  { run_id: F5_ALL_FAIL_ID, seq: 4, ts: '2026-10-18T09:45:03Z', type: 'failed', backend: 'scripted', data: { reason: 'All sub-agents failed. Graph connection unavailable.' } },
];
