export type StepName =
  | 'detect'
  | 'score'
  | 'distribute'
  | 'investigate'
  | 'resolve'
  | 'target'
  | 'propose'
  | 'act'
  | 'review';

export interface PipelineEvent {
  step: StepName | string;
  phase: string;
  data: Record<string, any>;
  timestamp: string;
  id?: number | string;
}

export type Verdict = 'suspicious' | 'benign' | 'inconclusive';
export type FindingStatus = 'active' | 'superseded';

export interface Finding {
  finding_id: string;
  run_id: string;
  customer_id: string;
  agent_id: string;
  skill_id: string;
  verdict: Verdict;
  confidence: number;
  evidence_count: number;
  evidence_summary?: string;
  status: FindingStatus;
  backend?: string;
  timestamp?: string;
}

export interface SideScoreBreakdown {
  verdict: Verdict;
  confidence: number;
  evidence_count: number;
  skill_score: number;
  total_score: number;
  best_finding_id: string;
}

export interface CustomerResolution {
  customer_id: string;
  winning_side: Verdict;
  side_scores: Record<Verdict, SideScoreBreakdown>;
  upheld_finding_id: string;
  superseded_finding_ids: string[];
  resolved_at?: string;
}

export interface ProposedAction {
  action_id: string;
  run_id: string;
  customer_id: string;
  action_type: string;
  confidence: number;
  reason: string;
  status: 'PENDING' | 'APPROVED' | 'REJECTED' | 'EXECUTED' | 'FAILED';
  approval_token?: string;
  execution_result?: Record<string, any>;
  created_at?: string;
}

export interface CustomerExplanation {
  customer_id: string;
  narrative: string;
  winning_side: Verdict | null;
  corroboration: {
    corroborated: boolean;
    active_suspicious_count: number;
    distinct_skills: string[];
    best_confidence: number;
  };
  supporting_findings: Finding[];
  superseded_findings: Finding[];
  action: {
    action_type: string;
    status: string;
    confidence: number;
    reason: string;
  } | null;
  subgraph: {
    nodes: Array<{ id: string; label: string; [key: string]: any }>;
    edges: Array<{ id: string; source: string; target: string; type: string; [key: string]: any }>;
  };
}

export interface GraphNode {
  data: {
    id: string;
    label: string;
    type: string;
    status?: string;
    verdict?: string;
    confidence?: number;
    score?: number;
    properties?: Record<string, any>;
    dimmed?: boolean;
    highlighted?: boolean;
  };
}

export interface GraphEdge {
  data: {
    id: string;
    source: string;
    target: string;
    label?: string;
    type: string;
    dashed?: boolean;
    highlighted?: boolean;
    properties?: Record<string, any>;
  };
}

export interface GraphScopeData {
  nodes: Array<{ id: string; label: string; [key: string]: any }>;
  edges: Array<{ source: string; target: string; type: string; [key: string]: any }>;
}

export interface PipelineMetrics {
  total_customers?: number;
  seeds_flagged?: number;
  findings_count?: number;
  contested_customers?: number;
  actions_proposed?: number;
  actions_approved?: number;
  actions_rejected?: number;
  run_status: 'IDLE' | 'RUNNING' | 'PAUSED' | 'AWAITING_APPROVAL' | 'COMPLETED' | 'ERROR';
}

export interface ReplayRecording {
  replay_version: string;
  run_id: string;
  total_events: number;
  events: PipelineEvent[];
  final_result?: Record<string, any>;
  graph_snapshots?: Record<string, GraphScopeData>;
}
