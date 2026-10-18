import {
  ActionResult,
  Api,
  BuildEvent,
  CaseDetail,
  CaseSummary,
  Conversation,
  FileNode,
  GraphData,
  Health,
  RunEvent,
  SendOptions,
  SkillInfo,
  SourceInfo,
  TraceResponse,
  WhyResponse,
} from '../api/contract';
import { forgeMockMethods } from '../api/mock/forgeMock';
import { createMockEventSource } from '../api/mock/mockEventSource';
import {
  F1_ACTION_RESULT,
  F1_BLOCKS,
  F1_EVENTS,
  F1_RUN_ID,
  F1_TRACE,
  F1_WHY,
} from '../api/mock/fixtures/f1_investigate';
import {
  F2_FILES_TREE,
  F2_FILE_CONTENTS,
} from '../api/mock/fixtures/f2_build';
import { ATLAS_GRAPH_FIXTURE, ATLAS_SKILLS_FIXTURE } from '../api/mock/fixtures/atlas_skills';

export class MockApi implements Api {
  forgeConnect = forgeMockMethods.forgeConnect;
  forgeAgents = forgeMockMethods.forgeAgents;
  forgeRuns = forgeMockMethods.forgeRuns;
  forgeRun = forgeMockMethods.forgeRun;
  subscribeForge = forgeMockMethods.subscribeForge;
  forgeSkills = forgeMockMethods.forgeSkills;
  forgeSkill = forgeMockMethods.forgeSkill;
  uploadForgeSkill = forgeMockMethods.uploadForgeSkill;
  approveForgeSkill = forgeMockMethods.approveForgeSkill;
  rejectForgeSkill = forgeMockMethods.rejectForgeSkill;
  reimportForgeSkills = forgeMockMethods.reimportForgeSkills;

  private conversations: Map<string, Conversation> = new Map();
  private cases: Map<string, CaseDetail> = new Map();
  public mockSpeedMultiplier = 1;

  constructor() {
    this.seedConversations();
  }

  private seedConversations() {
    this.conversations.set('conv_001', {
      id: 'conv_001',
      title: 'Investigation: cust-000',
      messages: [
        {
          id: 'msg_u_001',
          role: 'user',
          created_at: new Date(Date.now() - 3600000).toISOString(),
          blocks: [
            {
              type: 'text',
              data: { markdown: 'Who is connected to the fraud involving customer cust-000?' },
            },
          ],
        },
        {
          id: 'msg_a_001',
          role: 'assistant',
          created_at: new Date(Date.now() - 3590000).toISOString(),
          run_id: F1_RUN_ID,
          status: 'done',
          blocks: F1_BLOCKS,
        },
      ],
    });

    this.cases.set('conv_001', {
      id: 'conv_001',
      title: 'Investigation: cust-000',
      status: 'ready',
      sources: [
        { id: 'src_1', name: 'cases_2026.csv', kind: 'csv', bytes: 14200, status: 'parsed' },
        { id: 'src_2', name: 'notes.txt', kind: 'txt', bytes: 4800, status: 'parsed' },
      ],
      stats: {
        nodes: 18,
        edges: 32,
        sources: 2,
        by_label: { Person: 6, BankAccount: 4, Phone: 4, Address: 4 },
        by_rel: { USES_PHONE: 12, HAS_ACCOUNT: 10, LIVES_AT: 10 },
        top_entities: [
          { cid: 'cust-000', name: 'Alice Moreno', type: 'Person', degree: 8 },
          { cid: 'cust-003', name: 'Bob Chen', type: 'Person', degree: 6 },
        ],
        warnings: [],
      },
      messages: this.conversations.get('conv_001')!.messages,
      llm: { provider: 'mock', model: 'mock-llm', remote: false, reachable: true },
    });
  }

  async health(): Promise<Health> {
    return {
      status: 'ok',
      falkordb: true,
      llm: { provider: 'mock', model: 'mock-v1', remote: false, reachable: true },
    };
  }

  async listConversations(): Promise<CaseSummary[]> {
    const list: CaseSummary[] = [];
    for (const [id, c] of this.cases.entries()) {
      list.push({
        id,
        title: c.title,
        status: c.status,
        updated_at: new Date().toISOString(),
      });
    }
    return list;
  }

  async createConversation(): Promise<{ id: string }> {
    const id = `case_${Date.now().toString(36)}`;
    const newCase: CaseDetail = {
      id,
      title: 'New case',
      status: 'draft',
      sources: [],
      stats: null,
      messages: [],
      llm: { provider: 'mock', model: 'mock-v1', remote: false, reachable: true },
    };
    this.cases.set(id, newCase);
    this.conversations.set(id, { id, title: 'New case', messages: [] });
    return { id };
  }

  async deleteConversation(conversationId: string): Promise<void> {
    this.cases.delete(conversationId);
    this.conversations.delete(conversationId);
  }

  async getConversation(id: string): Promise<Conversation> {
    const conv = this.conversations.get(id);
    if (!conv) {
      throw new Error(`Conversation ${id} not found`);
    }
    return conv;
  }

  async getCase(conversationId: string): Promise<CaseDetail> {
    const detail = this.cases.get(conversationId);
    if (!detail) {
      return {
        id: conversationId,
        title: 'New case',
        status: 'draft',
        sources: [],
        stats: null,
        messages: [],
        llm: { provider: 'mock', model: 'mock-v1', remote: false, reachable: true },
      };
    }
    return detail;
  }

  async uploadText(conversationId: string, body: { name?: string; text: string }): Promise<SourceInfo> {
    const detail = await this.getCase(conversationId);
    const src: SourceInfo = {
      id: `src_${Date.now()}`,
      name: body.name || 'pasted_text.txt',
      kind: 'text',
      bytes: body.text.length,
      status: 'pending',
    };
    detail.sources.push(src);
    detail.status = detail.status === 'ready' ? 'stale' : detail.status;
    return src;
  }

  async uploadFiles(conversationId: string, files: File[]): Promise<SourceInfo[]> {
    const detail = await this.getCase(conversationId);
    const added: SourceInfo[] = [];
    for (const f of files) {
      const ext = f.name.split('.').pop()?.toLowerCase() || 'txt';
      const src: SourceInfo = {
        id: `src_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
        name: f.name,
        kind: ext as SourceInfo['kind'],
        bytes: f.size,
        status: 'pending',
      };
      detail.sources.push(src);
      added.push(src);
    }
    detail.status = detail.status === 'ready' ? 'stale' : detail.status;
    return added;
  }

  async removeSource(conversationId: string, sourceId: string): Promise<void> {
    const detail = await this.getCase(conversationId);
    detail.sources = detail.sources.filter((s) => s.id !== sourceId);
    detail.status = detail.status === 'ready' ? 'stale' : detail.status;
  }

  async startBuild(conversationId: string): Promise<{ build_id: string }> {
    const detail = await this.getCase(conversationId);
    detail.status = 'building';
    return { build_id: `bld_${Date.now()}` };
  }

  subscribeBuild(
    conversationId: string,
    buildId: string,
    opts: {
      onEvent: (e: BuildEvent) => void;
      onState: (s: 'open' | 'reconnecting' | 'closed') => void;
    }
  ): () => void {
    opts.onState('open');
    let seq = 1;
    const send = (type: BuildEvent['type'], data: Record<string, unknown>) => {
      opts.onEvent({ build_id: buildId, seq: seq++, ts: new Date().toISOString(), type, data });
    };

    const t1 = setTimeout(() => send('source_parsed', { source_id: 'src_1' }), 300);
    const t2 = setTimeout(() => send('extract_progress', { done: 10, total: 10, entities: 24, relations: 30, dropped: 0 }), 600);
    const t3 = setTimeout(() => send('resolve_done', { merged: 4, possible_duplicates: 1 }), 900);
    const t4 = setTimeout(() => send('load_done', { nodes: 24, edges: 30 }), 1200);
    const t5 = setTimeout(async () => {
      const detail = await this.getCase(conversationId);
      detail.status = 'ready';
      detail.stats = {
        nodes: 24,
        edges: 30,
        sources: detail.sources.length,
        by_label: { Person: 10, Organization: 6, Account: 8 },
        by_rel: { WORKS_FOR: 12, PAYS: 18 },
        top_entities: [{ cid: 'person:alice-01', name: 'Alice Moreno', type: 'Person', degree: 6 }],
        warnings: [],
      };
      send('completed', { stats: detail.stats });
      opts.onState('closed');
    }, 1500);

    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
      clearTimeout(t4);
      clearTimeout(t5);
      opts.onState('closed');
    };
  }

  async cancelBuild(conversationId: string): Promise<void> {
    const detail = await this.getCase(conversationId);
    detail.status = 'draft';
  }

  async getSuggestions(): Promise<string[]> {
    return [
      'Who is connected to Alice Moreno?',
      'How is Alice Moreno connected to Bob Chen?',
      'Which sources mention Acme Ltd?',
    ];
  }

  async sendMessage(
    _conversationId: string,
    _body: { content: string; options: SendOptions }
  ): Promise<{ message_id: string; run_id: string }> {
    const msgId = `msg_${Date.now()}`;
    const runId = F1_RUN_ID;
    return { message_id: msgId, run_id: runId };
  }

  subscribeRun(
    _runId: string,
    opts: {
      onEvent: (e: RunEvent) => void;
      onState: (s: 'open' | 'reconnecting' | 'closed') => void;
    }
  ): () => void {
    return createMockEventSource(F1_EVENTS, opts, 1);
  }

  async answerRun(): Promise<void> {}
  async cancelRun(): Promise<void> {}
  async approveAction(): Promise<ActionResult> {
    return F1_ACTION_RESULT;
  }
  async rejectAction(): Promise<void> {}
  async getTrace(): Promise<TraceResponse> {
    return F1_TRACE;
  }
  async getWhy(_runId?: string, target?: string): Promise<WhyResponse> {
    const whyMap = F1_WHY as unknown as Record<string, WhyResponse>;
    return (target && whyMap[target]) || Object.values(whyMap)[0]!;
  }
  async getArtifacts(): Promise<FileNode[]> {
    return F2_FILES_TREE;
  }
  async getArtifactFile(_runId: string, path: string): Promise<{ path: string; content: string; truncated: boolean }> {
    return { path, content: F2_FILE_CONTENTS[path] || '// Mock file', truncated: false };
  }
  artifactsZipUrl(): string {
    return '/api/runs/mock/artifacts.zip';
  }
  async getAtlasSkills(): Promise<SkillInfo[]> {
    return ATLAS_SKILLS_FIXTURE;
  }
  async getAtlasGraph(): Promise<GraphData> {
    return ATLAS_GRAPH_FIXTURE;
  }
  async expandNode(): Promise<GraphData> {
    return { nodes: [], edges: [], truncated: false };
  }
}

export const mockApi = new MockApi();
