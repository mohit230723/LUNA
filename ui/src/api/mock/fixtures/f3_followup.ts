import { Block, RunEvent, TraceResponse } from '../../contract';

export const F3_RUN_ID = 'run_followup_003';

export const F3_TRACE: TraceResponse = {
  mode: 'traversal',
  summary: 'cust-003 is connected to cust-005 via shared bank account ba-ring-01.',
  path_node_ids: ['cust-003', 'ba-ring-01', 'cust-005'],
  nodes: [
    { id: 'cust-003', label: 'cust-003', props: { type: 'Customer', name: 'Boris Vance' } },
    { id: 'ba-ring-01', label: 'ba-ring-01', props: { type: 'BankAccount' } },
    { id: 'cust-005', label: 'cust-005', props: { type: 'Customer', name: 'Clara Diaz' } },
  ],
  edges: [
    { id: 'e_f3_01', src: 'cust-003', dst: 'ba-ring-01', rel: 'PAYS_FROM', on_path: true },
    { id: 'e_f3_02', src: 'cust-005', dst: 'ba-ring-01', rel: 'PAYS_FROM', on_path: true },
  ],
  steps: [
    { seq: 1, from: 'cust-003', to: 'ba-ring-01', rel: 'PAYS_FROM', tool: 'trace_connections', agent_id: 'agent_tracer', note: 'Customer pays from shared corporate account' },
    { seq: 2, from: 'ba-ring-01', to: 'cust-005', rel: 'PAYS_FROM', tool: 'trace_connections', agent_id: 'agent_tracer', note: 'Co-claimant pays from identical account' },
  ],
  truncated: false,
};

export const F3_BLOCKS: Block[] = [
  {
    type: 'routing',
    data: {
      pack: 'investigate',
      intent: 'Trace secondary connections for customer cust-003',
      confidence: 0.99,
      backend: 'scripted',
    },
  },
  {
    type: 'answer',
    data: {
      text: `Customer \`cust-003\` was previously flagged as part of the \`cust-000\` ring. Further inspection reveals direct account linkage through bank account \`ba-ring-01\` to \`cust-005\`.\n\nNo additional action proposed beyond the pending freeze on \`cust-003\`.`,
      cited_cids: ['cust-003', 'ba-ring-01', 'cust-005'],
      backend: 'scripted',
    },
  },
];

export const F3_EVENTS: RunEvent[] = [
  { run_id: F3_RUN_ID, seq: 1, ts: '2026-10-18T09:20:00Z', type: 'routed', backend: 'scripted', data: { pack: 'investigate' } },
  { run_id: F3_RUN_ID, seq: 2, ts: '2026-10-18T09:20:01Z', type: 'agent_started', backend: 'scripted', data: { agent_id: 'agent_tracer', skill: 'connection-tracer' } },
  { run_id: F3_RUN_ID, seq: 3, ts: '2026-10-18T09:20:02Z', type: 'traversal_step', backend: 'scripted', data: F3_TRACE.steps[0]! },
  { run_id: F3_RUN_ID, seq: 4, ts: '2026-10-18T09:20:03Z', type: 'traversal_step', backend: 'scripted', data: F3_TRACE.steps[1]! },
  { run_id: F3_RUN_ID, seq: 5, ts: '2026-10-18T09:20:04Z', type: 'agent_done', backend: 'scripted', data: { agent_id: 'agent_tracer' } },
  { run_id: F3_RUN_ID, seq: 6, ts: '2026-10-18T09:20:05Z', type: 'answer', backend: 'scripted', data: { text: F3_BLOCKS[1]?.data } },
  { run_id: F3_RUN_ID, seq: 7, ts: '2026-10-18T09:20:06Z', type: 'completed', backend: 'scripted', data: { run_id: F3_RUN_ID } },
];
