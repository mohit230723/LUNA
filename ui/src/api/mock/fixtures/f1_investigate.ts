import {
  ActionRequest,
  ActionResult,
  Block,
  FindingInfo,
  RunEvent,
  SkillAssignment,
  TraceResponse,
  WhyResponse,
} from '../../contract';

export const F1_RUN_ID = 'run_investigate_001';

export const F1_SKILL_ASSIGNMENTS: SkillAssignment[] = [
  {
    subject: 'trace_connections',
    chosen: 'connection-tracer',
    fit: 0.94,
    backend: 'scripted',
    rejected: [{ skill: 'bulk-linker', reason: 'policy_restricted' }],
  },
  {
    subject: 'link_subtask',
    chosen: 'entity-linker',
    fit: 0.88,
    backend: 'scripted',
    rejected: [{ skill: 'bulk-linker', reason: 'policy_restricted' }],
  },
  {
    subject: 'community_subtask',
    chosen: 'community-analyzer',
    fit: 0.91,
    backend: 'scripted',
    rejected: [{ skill: 'ring-detector-lite', reason: 'lower_track_record' }],
  },
];

export const F1_FINDINGS: FindingInfo[] = [
  {
    id: 'f_01',
    agent_id: 'agent_tracer',
    skill_id: 'connection-tracer',
    subject: 'cust-000',
    verdict: 'suspicious',
    confidence: 0.92,
    status: 'active',
    backend: 'scripted',
    evidence_cids: ['cust-000', 'ph-ring-01', 'cust-003'],
  },
  {
    id: 'f_02',
    agent_id: 'agent_tracer',
    skill_id: 'connection-tracer',
    subject: 'cust-003',
    verdict: 'suspicious',
    confidence: 0.89,
    status: 'active',
    backend: 'scripted',
    evidence_cids: ['cust-003', 'ba-ring-01', 'cust-005'],
  },
  {
    id: 'f_03',
    agent_id: 'agent_linker',
    skill_id: 'entity-linker',
    subject: 'cust-005',
    verdict: 'suspicious',
    confidence: 0.95,
    status: 'active',
    backend: 'scripted',
    evidence_cids: ['cust-005', 'claim-017', 'prov-ring'],
  },
  {
    id: 'f_04',
    agent_id: 'agent_analyzer',
    skill_id: 'community-analyzer',
    subject: 'cust-000',
    verdict: 'suspicious',
    confidence: 0.87,
    status: 'active',
    backend: 'scripted',
    evidence_cids: ['cust-000', 'ba-ring-01'],
  },
  {
    id: 'f_05',
    agent_id: 'agent_linker',
    skill_id: 'entity-linker',
    subject: 'cust-010',
    verdict: 'suspicious',
    confidence: 0.64,
    status: 'superseded',
    backend: 'scripted',
    fallback_reason: 'Lone weak finding superseded by community analysis',
    evidence_cids: ['cust-010', 'addr-decoy-01'],
  },
  {
    id: 'f_06',
    agent_id: 'agent_analyzer',
    skill_id: 'community-analyzer',
    subject: 'cust-010',
    verdict: 'benign',
    confidence: 0.81,
    status: 'active',
    backend: 'scripted',
    evidence_cids: ['cust-010'],
  },
];

export const F1_ACTION_REQUEST: ActionRequest = {
  action_id: 'act_flag_001',
  kind: 'flag_for_review',
  status: 'PENDING',
  targets: ['cust-000', 'cust-003', 'cust-005'],
  reason: 'Corroborated auto insurance fraud ring sharing phone, bank account, and provider',
};

export const F1_ACTION_RESULT: ActionResult = {
  ok: true,
  metrics: {
    precision: 1.0,
    recall: 0.375,
    f1: 0.545,
  },
};

export const F1_TRACE: TraceResponse = {
  mode: 'traversal',
  summary:
    'cust-000 shares a phone with cust-003, who pays from the same account as cust-005, who filed a claim treated by prov-ring.',
  path_node_ids: [
    'cust-000',
    'ph-ring-01',
    'cust-003',
    'ba-ring-01',
    'cust-005',
    'claim-017',
    'prov-ring',
  ],
  nodes: [
    { id: 'cust-000', label: 'cust-000', props: { type: 'Customer', name: 'Alba Chen', risk: 0.92 } },
    { id: 'ph-ring-01', label: 'ph-ring-01', props: { type: 'Phone', number: '+1-555-0199' } },
    { id: 'cust-003', label: 'cust-003', props: { type: 'Customer', name: 'Boris Vance', risk: 0.89 } },
    { id: 'ba-ring-01', label: 'ba-ring-01', props: { type: 'BankAccount', iban: 'US89-BANK-0012' } },
    { id: 'cust-005', label: 'cust-005', props: { type: 'Customer', name: 'Clara Diaz', risk: 0.95 } },
    { id: 'claim-017', label: 'claim-017', props: { type: 'InsuranceClaim', amount: 24500, staged: true } },
    { id: 'prov-ring', label: 'prov-ring', props: { type: 'Provider', specialty: 'Collision Repair' } },
    // Context nodes (1 hop)
    { id: 'cust-001', label: 'cust-001', props: { type: 'Customer' }, context: true },
    { id: 'cust-004', label: 'cust-004', props: { type: 'Customer' }, context: true },
    { id: 'addr-ring-01', label: 'addr-ring-01', props: { type: 'Address' }, context: true },
    { id: 'cust-010', label: 'cust-010', props: { type: 'Customer', note: 'Decoy Family' }, context: true },
    { id: 'addr-decoy-01', label: 'addr-decoy-01', props: { type: 'Address' }, context: true },
  ],
  edges: [
    { id: 'e_01', src: 'cust-000', dst: 'ph-ring-01', rel: 'USES_PHONE', on_path: true },
    { id: 'e_02', src: 'cust-003', dst: 'ph-ring-01', rel: 'USES_PHONE', on_path: true },
    { id: 'e_03', src: 'cust-003', dst: 'ba-ring-01', rel: 'PAYS_FROM', on_path: true },
    { id: 'e_04', src: 'cust-005', dst: 'ba-ring-01', rel: 'PAYS_FROM', on_path: true },
    { id: 'e_05', src: 'cust-005', dst: 'claim-017', rel: 'FILED', on_path: true },
    { id: 'e_06', src: 'claim-017', dst: 'prov-ring', rel: 'TREATED_BY', on_path: true },
    // Context edges
    { id: 'e_ctx_01', src: 'cust-001', dst: 'addr-ring-01', rel: 'LIVES_AT' },
    { id: 'e_ctx_02', src: 'cust-000', dst: 'addr-ring-01', rel: 'LIVES_AT' },
    { id: 'e_ctx_03', src: 'cust-010', dst: 'addr-decoy-01', rel: 'LIVES_AT' },
  ],
  steps: [
    { seq: 1, from: 'cust-000', to: 'ph-ring-01', rel: 'USES_PHONE', tool: 'trace_connections', agent_id: 'agent_tracer', note: 'Customer registered primary contact number.' },
    { seq: 2, from: 'ph-ring-01', to: 'cust-003', rel: 'USES_PHONE', tool: 'trace_connections', agent_id: 'agent_tracer', note: 'Identical phone shared on concurrent auto claim.' },
    { seq: 3, from: 'cust-003', to: 'ba-ring-01', rel: 'PAYS_FROM', tool: 'shared_attribute_links', agent_id: 'agent_linker', note: 'Shared banking account detected.' },
    { seq: 4, from: 'ba-ring-01', to: 'cust-005', rel: 'PAYS_FROM', tool: 'shared_attribute_links', agent_id: 'agent_linker', note: 'Direct payment link to third claimant.' },
    { seq: 5, from: 'cust-005', to: 'claim-017', rel: 'FILED', tool: 'trace_connections', agent_id: 'agent_tracer', note: 'Claimant filed high-severity damage claim.' },
    { seq: 6, from: 'claim-017', to: 'prov-ring', rel: 'TREATED_BY', tool: 'trace_connections', agent_id: 'agent_tracer', note: 'Repairs performed at flagged collision provider.' },
  ],
  truncated: false,
};

export const F1_BLOCKS: Block[] = [
  {
    type: 'routing',
    data: {
      pack: 'investigate',
      intent: 'Trace fraud ring connections from seed customer',
      confidence: 0.98,
      backend: 'scripted',
    },
  },
  {
    type: 'plan',
    data: {
      subtasks: [
        { id: 'sub_01', description: 'Trace shared phones and addresses from seed', capability: 'trace_connections' },
        { id: 'sub_02', description: 'Resolve banking and transaction links', capability: 'shared_attribute_links' },
        { id: 'sub_03', description: 'Analyze community graph clusters and identify ring boundaries', capability: 'cluster_community' },
      ],
    },
  },
  {
    type: 'skills',
    data: {
      assignments: F1_SKILL_ASSIGNMENTS,
    },
  },
  {
    type: 'agents',
    data: {
      agents: [
        { id: 'agent_tracer', skill: 'connection-tracer', status: 'done', tool_calls: 4, hops_walked: 2, backend: 'scripted' },
        { id: 'agent_linker', skill: 'entity-linker', status: 'done', tool_calls: 3, hops_walked: 2, backend: 'scripted' },
        { id: 'agent_analyzer', skill: 'community-analyzer', status: 'done', tool_calls: 2, hops_walked: 3, backend: 'scripted' },
      ],
    },
  },
  {
    type: 'findings',
    data: {
      items: F1_FINDINGS,
    },
  },
  {
    type: 'action_request',
    data: F1_ACTION_REQUEST,
  },
  {
    type: 'answer',
    data: {
      text: `Customer \`cust-000\` is directly connected to a high-confidence staged accident ring spanning 3 customers, a shared phone, a common bank account, and a flagged collision center.\n\nThe connection chain travels through \`cust-000\` via phone \`ph-ring-01\` to \`cust-003\`, continuing through bank account \`ba-ring-01\` to \`cust-005\`, who submitted claim \`claim-017\` serviced by provider \`prov-ring\`.\n\nNOT CHECKED: claims outside the 2-hop slice; no external data. Decoy customer \`cust-010\` was investigated and corroborated as benign.`,
      cited_cids: ['cust-000', 'ph-ring-01', 'cust-003', 'ba-ring-01', 'cust-005', 'claim-017', 'prov-ring'],
      backend: 'scripted',
    },
  },
];

export const F1_EVENTS: RunEvent[] = [
  { run_id: F1_RUN_ID, seq: 1, ts: '2026-10-18T09:00:00Z', type: 'routed', backend: 'scripted', data: { pack: 'investigate', intent: 'Trace fraud ring connections' } },
  { run_id: F1_RUN_ID, seq: 2, ts: '2026-10-18T09:00:01Z', type: 'skill_assigned', backend: 'scripted', data: { assignments: F1_SKILL_ASSIGNMENTS } },
  { run_id: F1_RUN_ID, seq: 3, ts: '2026-10-18T09:00:02Z', type: 'skill_fit', backend: 'scripted', data: { fit: 0.94 } },
  { run_id: F1_RUN_ID, seq: 4, ts: '2026-10-18T09:00:03Z', type: 'agent_started', backend: 'scripted', data: { agent_id: 'agent_tracer', skill: 'connection-tracer' } },
  { run_id: F1_RUN_ID, seq: 5, ts: '2026-10-18T09:00:04Z', type: 'tool_call', backend: 'scripted', data: { agent_id: 'agent_tracer', tool: 'trace_connections', args: { cid: 'cust-000' } } },
  { run_id: F1_RUN_ID, seq: 6, ts: '2026-10-18T09:00:05Z', type: 'traversal_step', backend: 'scripted', data: F1_TRACE.steps[0]! },
  { run_id: F1_RUN_ID, seq: 7, ts: '2026-10-18T09:00:06Z', type: 'agent_started', backend: 'scripted', data: { agent_id: 'agent_linker', skill: 'entity-linker' } },
  { run_id: F1_RUN_ID, seq: 8, ts: '2026-10-18T09:00:07Z', type: 'tool_call', backend: 'scripted', data: { agent_id: 'agent_linker', tool: 'shared_attribute_links', args: { cid: 'cust-003' } } },
  { run_id: F1_RUN_ID, seq: 9, ts: '2026-10-18T09:00:08Z', type: 'traversal_step', backend: 'scripted', data: F1_TRACE.steps[1]! },
  { run_id: F1_RUN_ID, seq: 10, ts: '2026-10-18T09:00:09Z', type: 'agent_started', backend: 'scripted', data: { agent_id: 'agent_analyzer', skill: 'community-analyzer' } },
  { run_id: F1_RUN_ID, seq: 11, ts: '2026-10-18T09:00:10Z', type: 'promoted', backend: 'scripted', data: { findings: F1_FINDINGS.slice(0, 4) } },
  { run_id: F1_RUN_ID, seq: 12, ts: '2026-10-18T09:00:11Z', type: 'conflict_resolved', backend: 'scripted', data: { customer_id: 'cust-010', winning: 'benign', superseded: ['f_05'] } },
  { run_id: F1_RUN_ID, seq: 13, ts: '2026-10-18T09:00:12Z', type: 'agent_done', backend: 'scripted', data: { agent_id: 'agent_tracer' } },
  { run_id: F1_RUN_ID, seq: 14, ts: '2026-10-18T09:00:13Z', type: 'agent_done', backend: 'scripted', data: { agent_id: 'agent_linker' } },
  { run_id: F1_RUN_ID, seq: 15, ts: '2026-10-18T09:00:14Z', type: 'agent_done', backend: 'scripted', data: { agent_id: 'agent_analyzer' } },
  { run_id: F1_RUN_ID, seq: 16, ts: '2026-10-18T09:00:15Z', type: 'action_proposed', backend: 'scripted', data: F1_ACTION_REQUEST },
  { run_id: F1_RUN_ID, seq: 17, ts: '2026-10-18T09:00:16Z', type: 'answer', backend: 'scripted', data: { text: F1_BLOCKS[6]?.data } },
  { run_id: F1_RUN_ID, seq: 18, ts: '2026-10-18T09:00:17Z', type: 'completed', backend: 'scripted', data: { run_id: F1_RUN_ID } },
];

export const F1_WHY: Record<string, WhyResponse> = {
  'cust-000': {
    target: 'cust-000',
    narrative: 'Customer cust-000 was flagged as a central node in an auto collision ring. Corroborated by 2 distinct skills (connection-tracer at 92% and community-analyzer at 87%). Shares phone ph-ring-01 with co-conspirator cust-003.',
    findings: [F1_FINDINGS[0]!, F1_FINDINGS[3]!],
    decision: {
      id: 'dec_000',
      chosen_verdict: 'suspicious',
      components: { confidence: 0.92, evidence: 0.8, reputation: 0.9 },
      weights: { w_conf: 0.5, w_evid: 0.2, w_skill: 0.3 },
      skill_scores: { 'connection-tracer': 0.9 },
    },
    chain_node_ids: ['cust-000', 'ph-ring-01', 'cust-003'],
  },
  'cust-010': {
    target: 'cust-010',
    narrative: 'Customer cust-010 is part of an uncorroborated decoy family cluster. Contradictory finding f_05 (suspicious 0.64) was superseded by community analysis f_06 (benign 0.81). Winning side: BENIGN.',
    findings: [F1_FINDINGS[4]!, F1_FINDINGS[5]!],
    decision: {
      id: 'dec_010',
      chosen_verdict: 'benign',
      components: { confidence: 0.81, evidence: 0.2, reputation: 0.85 },
      weights: { w_conf: 0.5, w_evid: 0.2, w_skill: 0.3 },
      skill_scores: { 'community-analyzer': 0.85 },
    },
    chain_node_ids: ['cust-010', 'addr-decoy-01'],
  },
};
