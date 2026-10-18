export type Pack = 'investigate' | 'build';
export type Backend = 'llm' | 'rules' | 'scripted';
export type RunStatus = 'queued' | 'streaming' | 'needs_input' | 'done' | 'failed' | 'cancelled';

export interface Health {
  status: 'ok' | 'degraded';
  falkordb: boolean;
  llm: { provider: string; reachable: boolean };
}

export interface ConversationSummary {
  id: string;
  title: string;
  updated_at: string;
}

export interface Conversation {
  id: string;
  title: string;
  messages: Message[];
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  created_at: string;
  run_id?: string;
  status?: 'streaming' | 'needs_input' | 'done' | 'failed';
  blocks: Block[];
}

export type Block =
  | { type: 'text'; data: { markdown: string } }
  | { type: 'routing'; data: { pack: Pack; intent: string; confidence: number; backend: Backend } }
  | { type: 'plan'; data: { subtasks?: Subtask[]; components?: ComponentInfo[]; contracts?: ContractInfo[] } }
  | { type: 'skills'; data: { assignments: SkillAssignment[] } }
  | { type: 'agents'; data: { agents: AgentInfo[] } }
  | { type: 'trace_preview'; data: { run_id: string; mode: 'traversal' | 'blueprint'; path_node_ids: string[]; summary: string } }
  | { type: 'findings'; data: { items: FindingInfo[] } }
  | { type: 'files'; data: { tree: FileNode[]; zip_url: string; contracts_implemented: number; contracts_total: number; open_violations: ViolationInfo[] } }
  | { type: 'action_request'; data: ActionRequest }
  | { type: 'needs_input'; data: { question: string; options: string[]; allow_free_text?: boolean } }
  | { type: 'warning'; data: { text: string } }
  | { type: 'answer'; data: { text: string; cited_cids: string[]; backend: Backend } };

export interface Subtask {
  id: string;
  description: string;
  capability: string;
}

export interface ComponentInfo {
  id: string;
  name: string;
  kind: 'frontend' | 'backend' | 'database' | 'docs' | 'infra';
  tech: string;
}

export interface ContractInfo {
  id: string;
  kind: 'endpoint' | 'table' | 'env' | 'port';
  key: string;
  status: 'declared' | 'implemented' | 'violated';
}

export interface RejectedSkill {
  skill: string;
  reason: 'policy_restricted' | 'lower_track_record' | 'tech_mismatch';
}

export interface SkillAssignment {
  subject: string;
  chosen: string;
  fit?: number;
  backend: Backend;
  rejected: RejectedSkill[];
  reassigned_from?: string;
}

export interface AgentInfo {
  id: string;
  skill: string;
  status: 'pending' | 'running' | 'done' | 'failed';
  tool_calls: number;
  files_written?: number;
  hops_walked?: number;
  backend: Backend;
  reason?: string;
}

export interface FindingInfo {
  id: string;
  agent_id: string;
  skill_id: string;
  subject: string;
  verdict: 'suspicious' | 'benign';
  confidence: number;
  status: 'active' | 'superseded';
  backend: Backend;
  fallback_reason?: string;
  evidence_cids: string[];
}

export interface FileNode {
  path: string;
  kind: 'file' | 'dir';
  bytes?: number;
  children?: FileNode[];
}

export interface ViolationInfo {
  id: string;
  kind: string;
  detail: string;
  status: 'open' | 'resolved';
}

export interface ActionRequest {
  [key: string]: unknown;
  action_id: string;
  kind: 'flag_for_review' | 'run_build_check';
  status: 'PENDING' | 'APPROVED' | 'REJECTED' | 'EXECUTED' | 'FAILED';
  targets?: string[];
  commands?: { cmd: string; timeout_s: number }[];
  approver?: string;
  reason?: string;
  result?: ActionResult;
}

export interface ActionResult {
  ok: boolean;
  metrics?: { precision: number; recall: number; f1: number } | null;
  commands?: {
    cmd: string;
    exit_code: number | null;
    log_tail: string;
    executed: boolean;
    note?: string;
  }[];
}

export type RunEventType =
  | 'routed'
  | 'requirements'
  | 'blueprint'
  | 'skill_assigned'
  | 'skill_fit'
  | 'agent_started'
  | 'agent_progress'
  | 'tool_call'
  | 'traversal_step'
  | 'artifact_written'
  | 'contract_violation'
  | 'remediation'
  | 'agent_done'
  | 'agent_failed'
  | 'promoted'
  | 'conflict_resolved'
  | 'answer'
  | 'action_proposed'
  | 'needs_input'
  | 'approved'
  | 'executed'
  | 'learned'
  | 'completed'
  | 'failed'
  | 'cancelled';

export interface RunEvent {
  run_id: string;
  seq: number;
  ts: string;
  type: RunEventType;
  backend?: Backend;
  data: Record<string, unknown>;
}

export interface TraceNode {
  id: string;
  label: string;
  props: Record<string, unknown>;
  context?: boolean;
}

export interface TraceEdge {
  id: string;
  src: string;
  dst: string;
  rel: string;
  on_path?: boolean;
}

export interface TraceStep {
  [key: string]: unknown;
  seq: number;
  from: string;
  to: string;
  rel: string;
  tool: string;
  agent_id: string;
  note: string;
}

export interface TraceResponse {
  mode: 'traversal' | 'blueprint';
  nodes: TraceNode[];
  edges: TraceEdge[];
  steps: TraceStep[];
  path_node_ids: string[];
  summary: string;
  truncated: boolean;
}

export interface SkillInfo {
  id: string;
  name: string;
  pack: Pack;
  capabilities: string[];
  technologies: string[];
  requires: string[];
  tools: string[];
  score: number;
  runs: number;
  restricted: boolean;
  description: string;
  prompt_fragment: string;
}

export interface GraphData {
  nodes: TraceNode[];
  edges: TraceEdge[];
  truncated: boolean;
}

export interface WhyResponse {
  target: string;
  narrative: string;
  findings: FindingInfo[];
  decision?: {
    id: string;
    chosen_verdict: string;
    components: Record<string, number>;
    weights: Record<string, number>;
    skill_scores: Record<string, number>;
  };
  chain_node_ids: string[];
}

export interface SendOptions {
  pack: 'auto' | Pack;
  mode: 'scripted' | 'live';
  strict_llm: boolean;
  parallel: number;
}

export interface Api {
  health(): Promise<Health>;
  listConversations(): Promise<ConversationSummary[]>;
  createConversation(): Promise<{ id: string }>;
  getConversation(id: string): Promise<Conversation>;
  sendMessage(
    conversationId: string,
    body: { content: string; options: SendOptions }
  ): Promise<{ message_id: string; run_id: string }>;
  subscribeRun(
    runId: string,
    opts: {
      lastEventId?: number;
      onEvent: (e: RunEvent) => void;
      onState: (s: 'open' | 'reconnecting' | 'closed') => void;
    }
  ): () => void;
  answerRun(runId: string, choice: string): Promise<void>;
  cancelRun(runId: string): Promise<void>;
  approveAction(runId: string, actionId: string, approver: string): Promise<ActionResult>;
  rejectAction(runId: string, actionId: string, approver: string, reason: string): Promise<void>;
  getTrace(runId: string): Promise<TraceResponse>;
  getWhy(runId: string, target: string): Promise<WhyResponse>;
  getArtifacts(runId: string): Promise<FileNode[]>;
  getArtifactFile(runId: string, path: string): Promise<{ path: string; content: string; truncated: boolean }>;
  artifactsZipUrl(runId: string): string;
  getAtlasSkills(pack?: Pack): Promise<SkillInfo[]>;
  getAtlasGraph(): Promise<GraphData>;
  expandNode(cid: string, hops: number): Promise<GraphData>;
}
