import {
  ActionRequest,
  ActionResult,
  Api,
  Conversation,
  ConversationSummary,
  FileNode,
  GraphData,
  Health,
  Pack,
  RunEvent,
  SendOptions,
  SkillInfo,
  TraceResponse,
  WhyResponse,
} from '../contract';
import { createMockEventSource } from './mockEventSource';
import {
  F1_ACTION_RESULT,
  F1_BLOCKS,
  F1_EVENTS,
  F1_RUN_ID,
  F1_TRACE,
  F1_WHY,
} from './fixtures/f1_investigate';
import {
  F2_ACTION_RESULT_NOT_EXECUTED,
  F2_ACTION_RESULT_SUCCESS,
  F2_BLOCKS,
  F2_EVENTS,
  F2_FILES_TREE,
  F2_FILE_CONTENTS,
  F2_RUN_ID,
  F2_TRACE,
} from './fixtures/f2_build';
import { F3_BLOCKS, F3_EVENTS, F3_RUN_ID, F3_TRACE } from './fixtures/f3_followup';
import { F4_BLOCKS, F4_EVENTS, F4_RUN_ID } from './fixtures/f4_clarification';
import {
  F5_ALL_FAIL_EVENTS,
  F5_ALL_FAIL_ID,
  F5_PARTIAL_BLOCKS,
  F5_PARTIAL_EVENTS,
  F5_PARTIAL_FAIL_ID,
} from './fixtures/f5_failure';
import { ATLAS_GRAPH_FIXTURE, ATLAS_SKILLS_FIXTURE } from './fixtures/atlas_skills';

export class MockApi implements Api {
  private conversations: Map<string, Conversation> = new Map();
  private runEventsMap: Map<string, RunEvent[]> = new Map();
  private runActionStatus: Map<string, ActionRequest['status']> = new Map();
  public mockSpeedMultiplier = 1;
  public devFailAll = false;
  public devFailPartial = false;
  public devBuildCheckFail = false;

  constructor() {
    const envSpeed =
      typeof import.meta !== 'undefined' && import.meta.env?.VITE_MOCK_SPEED
        ? Number(import.meta.env.VITE_MOCK_SPEED)
        : typeof process !== 'undefined' && process.env?.NODE_ENV === 'test'
        ? 0
        : 1;
    this.mockSpeedMultiplier = isNaN(envSpeed) ? 1 : envSpeed;
    this.initDefaultFixtures();
  }

  public getSpeedMultiplier(): number {
    try {
      const prefs = localStorage.getItem('luna.prefs');
      if (prefs) {
        const parsed = JSON.parse(prefs);
        if (parsed.mockSpeed !== undefined) {
          const s = Number(parsed.mockSpeed);
          if (!isNaN(s) && s >= 0) return s;
        }
      }
    } catch {
      // ignore
    }
    return this.mockSpeedMultiplier;
  }

  private initDefaultFixtures() {
    this.runEventsMap.set(F1_RUN_ID, F1_EVENTS);
    this.runEventsMap.set(F2_RUN_ID, F2_EVENTS);
    this.runEventsMap.set(F3_RUN_ID, F3_EVENTS);
    this.runEventsMap.set(F4_RUN_ID, F4_EVENTS);
    this.runEventsMap.set(F5_PARTIAL_FAIL_ID, F5_PARTIAL_EVENTS);
    this.runEventsMap.set(F5_ALL_FAIL_ID, F5_ALL_FAIL_EVENTS);
  }

  async health(): Promise<Health> {
    return {
      status: 'ok',
      falkordb: true,
      llm: { provider: 'mock-llm', model: 'mock', remote: false, reachable: true },
    };
  }

  async listConversations(): Promise<CaseSummary[]> {
    const list: CaseSummary[] = [];
    this.conversations.forEach((conv) => {
      const lastMsg = conv.messages[conv.messages.length - 1];
      list.push({
        id: conv.id,
        title: conv.title,
        status: 'ready',
        updated_at: lastMsg?.created_at || new Date().toISOString(),
      });
    });
    return list;
  }

  async createConversation(): Promise<{ id: string }> {
    const id = `conv_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
    this.conversations.set(id, {
      id,
      title: 'New Investigation',
      messages: [],
    });
    return { id };
  }

  async getConversation(id: string): Promise<Conversation> {
    const conv = this.conversations.get(id);
    if (!conv) {
      // Auto-create if not found
      const newConv: Conversation = { id, title: 'New Conversation', messages: [] };
      this.conversations.set(id, newConv);
      return newConv;
    }
    return conv;
  }

  async sendMessage(
    conversationId: string,
    body: { content: string; options: SendOptions }
  ): Promise<{ message_id: string; run_id: string }> {
    let conv = this.conversations.get(conversationId);
    if (!conv) {
      conv = { id: conversationId, title: body.content.slice(0, 48), messages: [] };
      this.conversations.set(conversationId, conv);
    } else if (conv.messages.length === 0) {
      conv.title = body.content.slice(0, 48);
    }

    const userMsgId = `msg_user_${Date.now()}`;
    conv.messages.push({
      id: userMsgId,
      role: 'user',
      created_at: new Date().toISOString(),
      blocks: [{ type: 'text', data: { markdown: body.content } }],
    });

    const assistantMsgId = `msg_asst_${Date.now()}`;
    let runId = F1_RUN_ID;

    // Routing rules matching Section 8
    const prompt = body.content.toLowerCase();
    const hasPriorF1 = conv.messages.some((m) => m.run_id === F1_RUN_ID);

    if (this.devFailAll) {
      runId = F5_ALL_FAIL_ID;
      conv.messages.push({
        id: assistantMsgId,
        role: 'assistant',
        created_at: new Date().toISOString(),
        run_id: runId,
        status: 'streaming',
        blocks: [],
      });
    } else if (this.devFailPartial) {
      runId = F5_PARTIAL_FAIL_ID;
      conv.messages.push({
        id: assistantMsgId,
        role: 'assistant',
        created_at: new Date().toISOString(),
        run_id: runId,
        status: 'streaming',
        blocks: F5_PARTIAL_BLOCKS,
      });
    } else if (/svelte/i.test(prompt)) {
      runId = F4_RUN_ID;
      conv.messages.push({
        id: assistantMsgId,
        role: 'assistant',
        created_at: new Date().toISOString(),
        run_id: runId,
        status: 'needs_input',
        blocks: F4_BLOCKS,
      });
    } else if (/cust-003/i.test(prompt) && hasPriorF1) {
      runId = F3_RUN_ID;
      conv.messages.push({
        id: assistantMsgId,
        role: 'assistant',
        created_at: new Date().toISOString(),
        run_id: runId,
        status: 'streaming',
        blocks: F3_BLOCKS,
      });
    } else if (/build|app|project|npm|api/i.test(prompt)) {
      runId = F2_RUN_ID;
      conv.messages.push({
        id: assistantMsgId,
        role: 'assistant',
        created_at: new Date().toISOString(),
        run_id: runId,
        status: 'streaming',
        blocks: F2_BLOCKS,
      });
    } else if (/who|connected|fraud|cust-|ring/i.test(prompt)) {
      runId = F1_RUN_ID;
      conv.messages.push({
        id: assistantMsgId,
        role: 'assistant',
        created_at: new Date().toISOString(),
        run_id: runId,
        status: 'streaming',
        blocks: F1_BLOCKS,
      });
    } else {
      // General prompt -> ask clarification
      runId = `run_clarify_${Date.now()}`;
      const clarifyBlocks = [
        {
          type: 'needs_input' as const,
          data: {
            question: 'Should I investigate connected data or build a project?',
            options: ['INVESTIGATE', 'BUILD'],
          },
        },
      ];
      conv.messages.push({
        id: assistantMsgId,
        role: 'assistant',
        created_at: new Date().toISOString(),
        run_id: runId,
        status: 'needs_input',
        blocks: clarifyBlocks,
      });
    }

    return { message_id: assistantMsgId, run_id: runId };
  }

  subscribeRun(
    runId: string,
    opts: {
      lastEventId?: number;
      onEvent: (e: RunEvent) => void;
      onState: (s: 'open' | 'reconnecting' | 'closed') => void;
    }
  ): () => void {
    const events = this.runEventsMap.get(runId) || F1_EVENTS;
    return createMockEventSource(events, opts, this.getSpeedMultiplier());
  }

  async answerRun(runId: string, choice: string): Promise<void> {
    // Resume run after clarification
    const chosenBlocks = /investigate/i.test(choice) ? F1_BLOCKS : F2_BLOCKS;
    const chosenEvents = /investigate/i.test(choice) ? F1_EVENTS : F2_EVENTS;
    this.runEventsMap.set(runId, chosenEvents);

    for (const conv of this.conversations.values()) {
      const msg = conv.messages.find((m) => m.run_id === runId);
      if (msg) {
        msg.status = 'done';
        msg.blocks = chosenBlocks;
      }
    }
  }

  async cancelRun(runId: string): Promise<void> {
    const events = this.runEventsMap.get(runId);
    if (events) {
      events.push({
        run_id: runId,
        seq: events.length + 1,
        ts: new Date().toISOString(),
        type: 'cancelled',
        data: { reason: 'Cancelled by operator' },
      });
    }
  }

  async approveAction(runId: string, actionId: string, _approver: string): Promise<ActionResult> {
    this.runActionStatus.set(actionId, 'APPROVED');
    if (runId === F2_RUN_ID) {
      return this.devBuildCheckFail ? F2_ACTION_RESULT_NOT_EXECUTED : F2_ACTION_RESULT_SUCCESS;
    }
    return F1_ACTION_RESULT;
  }

  async rejectAction(_runId: string, actionId: string, _approver: string, _reason: string): Promise<void> {
    this.runActionStatus.set(actionId, 'REJECTED');
  }

  async getTrace(runId: string): Promise<TraceResponse> {
    if (runId === F2_RUN_ID) return F2_TRACE;
    if (runId === F3_RUN_ID) return F3_TRACE;
    return F1_TRACE;
  }

  async getWhy(_runId: string, target: string): Promise<WhyResponse> {
    if (F1_WHY[target]) {
      return F1_WHY[target];
    }
    return {
      target,
      narrative: `Evidence chain analysis for ${target} confirmed active findings without contradictions.`,
      findings: [],
      chain_node_ids: [target],
    };
  }

  async getArtifacts(_runId: string): Promise<FileNode[]> {
    return F2_FILES_TREE;
  }

  async getArtifactFile(_runId: string, filePath: string): Promise<{ path: string; content: string; truncated: boolean }> {
    const content = F2_FILE_CONTENTS[filePath] || `// Content for ${filePath}\nexport default {};\n`;
    return {
      path: filePath,
      content,
      truncated: false,
    };
  }

  artifactsZipUrl(runId: string): string {
    return `/api/runs/${encodeURIComponent(runId)}/artifacts.zip`;
  }

  async getAtlasSkills(pack?: Pack): Promise<SkillInfo[]> {
    if (pack) {
      return ATLAS_SKILLS_FIXTURE.filter((s) => s.pack === pack);
    }
    return ATLAS_SKILLS_FIXTURE;
  }

  async getAtlasGraph(): Promise<GraphData> {
    return ATLAS_GRAPH_FIXTURE;
  }

  async expandNode(cid: string, _hops: number): Promise<GraphData> {
    const trace = F1_TRACE;
    const connectedEdges = trace.edges.filter((e) => e.src === cid || e.dst === cid);
    const nodeIds = new Set<string>([cid]);
    connectedEdges.forEach((e) => {
      nodeIds.add(e.src);
      nodeIds.add(e.dst);
    });
    const nodes = trace.nodes.filter((n) => nodeIds.has(n.id));
    return {
      nodes,
      edges: connectedEdges,
      truncated: false,
    };
  }
}

export const mockApi = new MockApi();
