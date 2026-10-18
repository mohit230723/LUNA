export type Pack = 'investigate' | 'build';
export type Backend = 'llm' | 'rules' | 'scripted';
export type RunStatus = 'queued' | 'streaming' | 'needs_input' | 'done' | 'failed' | 'cancelled';

export type SourceKind = 'text' | 'csv' | 'json' | 'jsonl' | 'xlsx' | 'sqlite' | 'txt' | 'md';
export type SourceStatus = 'pending' | 'parsed' | 'failed';

export interface SourceInfo {
  id: string;
  name: string;
  kind: SourceKind;
  bytes: number;
  status: SourceStatus;
  error?: string;
  stats?: { chunks?: number; rows?: number; tables?: number };
}

export type CaseStatus = 'draft' | 'building' | 'ready' | 'stale' | 'failed';

export interface LlmInfo {
  provider: string;
  model: string;
  remote: boolean;
  reachable: boolean;
}

export interface CaseSummary {
  id: string;
  title: string;
  status: CaseStatus;
  updated_at: string;
}

export interface GraphStats {
  nodes: number;
  edges: number;
  sources: number;
  by_label: Record<string, number>;
  by_rel: Record<string, number>;
  top_entities: { cid: string; name: string; type: string; degree: number }[];
  warnings: string[];
  extraction?: {
    chunks_total: number;
    chunks_ok: number;
    entities_kept: number;
    entities_dropped: number;
    relations_kept: number;
    relations_dropped: number;
    model: string;
  };
}

export interface CaseDetail {
  id: string;
  title: string;
  status: CaseStatus;
  sources: SourceInfo[];
  stats: GraphStats | null;
  messages: Message[];
  llm: LlmInfo;
  build_error?: string;
}

export type BuildEventType =
  | 'source_parsed'
  | 'mapping_planned'
  | 'extract_progress'
  | 'resolve_done'
  | 'load_done'
  | 'completed'
  | 'failed'
  | 'cancelled';

export interface BuildEvent {
  build_id: string;
  seq: number;
  ts: string;
  type: BuildEventType;
  data: Record<string, unknown>;
}

export interface Health {
  status: 'ok' | 'degraded';
  falkordb: boolean;
  llm: LlmInfo;
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
  | { type: 'answer'; data: { text: string; cited_cids: string[]; backend: Backend; model?: string } }
  | { type: 'graph_summary'; data: GraphStats };

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
  kind: 'path' | 'link' | 'cluster' | 'timeline' | 'fact' | 'absence';
  claim: string;
  subject_cids: string[];
  evidence_cids: string[];
  confidence: number;
  status: 'active' | 'superseded';
  backend: Backend;
  verdict?: 'suspicious' | 'benign';
  subject?: string;
  fallback_reason?: string;
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
  | 'understood'
  | 'entities_resolved'
  | 'plan'
  | 'skill_assigned'
  | 'agent_started'
  | 'tool_call'
  | 'traversal_step'
  | 'finding'
  | 'agent_done'
  | 'agent_failed'
  | 'promoted'
  | 'answer'
  | 'needs_input'
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
  seq: number;
  from: string;
  to: string;
  rel: string;
  tool: string;
  agent_id: string;
  note: string;
  focus: string;
  value: { title: string; subtitle: string; properties: { k: string; v: string }[] };
  source?: { name: string; locator: string; quote?: string };
}

export interface TraceResponse {
  mode: 'traversal';
  nodes: TraceNode[];
  edges: TraceEdge[];
  steps: TraceStep[];
  path_node_ids: string[];
  summary: string;
  truncated: boolean;
  explored_steps: number;
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
  max_hops: number;
  investigators: number;
  pack?: 'auto' | Pack;
  mode?: 'scripted' | 'live';
  strict_llm?: boolean;
  parallel?: number;
}

export interface Api {
  health(): Promise<Health>;
  listConversations(): Promise<CaseSummary[]>;
  createConversation(): Promise<{ id: string }>;
  getConversation(id: string): Promise<Conversation>;
  deleteConversation(conversationId: string): Promise<void>;

  // Case & Ingestion methods
  getCase(conversationId: string): Promise<CaseDetail>;
  uploadText(conversationId: string, body: { name?: string; text: string }): Promise<SourceInfo>;
  uploadFiles(conversationId: string, files: File[]): Promise<SourceInfo[]>;
  removeSource(conversationId: string, sourceId: string): Promise<void>;
  startBuild(conversationId: string, opts: { acknowledge_remote: boolean }): Promise<{ build_id: string }>;
  subscribeBuild(
    conversationId: string,
    buildId: string,
    opts: {
      lastEventId?: number;
      onEvent: (e: BuildEvent) => void;
      onState: (s: 'open' | 'reconnecting' | 'closed') => void;
    }
  ): () => void;
  cancelBuild(conversationId: string, buildId: string): Promise<void>;
  getSuggestions(conversationId: string): Promise<string[]>;

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
  expandNode(cid: string, hops: number, conversationId?: string): Promise<GraphData>;
}
