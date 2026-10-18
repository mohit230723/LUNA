import {
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
} from './contract';
import { isRunEvent, filterValidBlocks } from './guards';

export class ApiError extends Error {
  error: string;
  detail?: string;
  status: number;

  constructor(status: number, error: string, detail?: string) {
    super(detail ? `${error}: ${detail}` : error);
    this.name = 'ApiError';
    this.status = status;
    this.error = error;
    this.detail = detail;
  }
}

export class LiveApi implements Api {
  private baseUrl: string;

  constructor(baseUrl?: string) {
    this.baseUrl = baseUrl || (import.meta.env.VITE_API_BASE as string) || '/api';
    // Remove trailing slash if present
    if (this.baseUrl.endsWith('/')) {
      this.baseUrl = this.baseUrl.slice(0, -1);
    }
  }

  private async request<T>(path: string, options?: RequestInit): Promise<T> {
    const url = `${this.baseUrl}${path}`;
    const res = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(options?.headers || {}),
      },
    });

    if (!res.ok) {
      let errPayload: { error?: string; detail?: string } = {};
      try {
        errPayload = await res.json();
      } catch {
        // non-JSON response
      }
      throw new ApiError(
        res.status,
        errPayload.error || res.statusText || 'Request failed',
        errPayload.detail
      );
    }

    if (res.status === 204) {
      return undefined as unknown as T;
    }

    return (await res.json()) as T;
  }

  async health(): Promise<Health> {
    return this.request<Health>('/health');
  }

  async listConversations(): Promise<ConversationSummary[]> {
    return this.request<ConversationSummary[]>('/chat/conversations');
  }

  async createConversation(): Promise<{ id: string }> {
    return this.request<{ id: string }>('/chat/conversations', {
      method: 'POST',
    });
  }

  async getConversation(id: string): Promise<Conversation> {
    const conv = await this.request<Conversation>(`/chat/conversations/${encodeURIComponent(id)}`);
    if (conv && Array.isArray(conv.messages)) {
      conv.messages = conv.messages.map((m) => ({
        ...m,
        blocks: filterValidBlocks(m.blocks),
      }));
    }
    return conv;
  }

  async sendMessage(
    conversationId: string,
    body: { content: string; options: SendOptions }
  ): Promise<{ message_id: string; run_id: string }> {
    return this.request<{ message_id: string; run_id: string }>(
      `/chat/conversations/${encodeURIComponent(conversationId)}/messages`,
      {
        method: 'POST',
        body: JSON.stringify(body),
      }
    );
  }

  subscribeRun(
    runId: string,
    opts: {
      lastEventId?: number;
      onEvent: (e: RunEvent) => void;
      onState: (s: 'open' | 'reconnecting' | 'closed') => void;
    }
  ): () => void {
    let urlStr = `${this.baseUrl}/runs/${encodeURIComponent(runId)}/events`;
    if (opts.lastEventId !== undefined) {
      urlStr += `?last_event_id=${encodeURIComponent(String(opts.lastEventId))}`;
    }

    // Handle relative or absolute URLs
    const fullUrl = urlStr.startsWith('http')
      ? urlStr
      : `${window.location.origin}${urlStr}`;

    const es = new EventSource(fullUrl);

    es.onopen = () => {
      opts.onState('open');
    };

    es.onerror = () => {
      if (es.readyState === EventSource.CLOSED) {
        opts.onState('closed');
      } else {
        opts.onState('reconnecting');
      }
    };

    es.addEventListener('pipeline_event', (e: MessageEvent) => {
      try {
        const parsed = JSON.parse(e.data);
        if (isRunEvent(parsed)) {
          opts.onEvent(parsed);
        } else if (import.meta.env.DEV) {
          console.warn('Unknown or malformed pipeline event received:', parsed);
        }
      } catch (err) {
        if (import.meta.env.DEV) {
          console.warn('Failed to parse SSE pipeline_event data:', e.data, err);
        }
      }
    });

    return () => {
      es.close();
      opts.onState('closed');
    };
  }

  async answerRun(runId: string, choice: string): Promise<void> {
    await this.request<void>(`/runs/${encodeURIComponent(runId)}/answer`, {
      method: 'POST',
      body: JSON.stringify({ choice }),
    });
  }

  async cancelRun(runId: string): Promise<void> {
    await this.request<void>(`/runs/${encodeURIComponent(runId)}/cancel`, {
      method: 'POST',
    });
  }

  async approveAction(
    runId: string,
    actionId: string,
    approver: string
  ): Promise<ActionResult> {
    return this.request<ActionResult>(
      `/runs/${encodeURIComponent(runId)}/actions/${encodeURIComponent(actionId)}/approve`,
      {
        method: 'POST',
        body: JSON.stringify({ approver }),
      }
    );
  }

  async rejectAction(
    runId: string,
    actionId: string,
    approver: string,
    reason: string
  ): Promise<void> {
    await this.request<void>(
      `/runs/${encodeURIComponent(runId)}/actions/${encodeURIComponent(actionId)}/reject`,
      {
        method: 'POST',
        body: JSON.stringify({ approver, reason }),
      }
    );
  }

  async getTrace(runId: string): Promise<TraceResponse> {
    return this.request<TraceResponse>(`/runs/${encodeURIComponent(runId)}/trace`);
  }

  async getWhy(runId: string, target: string): Promise<WhyResponse> {
    return this.request<WhyResponse>(
      `/runs/${encodeURIComponent(runId)}/why/${encodeURIComponent(target)}`
    );
  }

  async getArtifacts(runId: string): Promise<FileNode[]> {
    return this.request<FileNode[]>(`/runs/${encodeURIComponent(runId)}/artifacts`);
  }

  async getArtifactFile(
    runId: string,
    path: string
  ): Promise<{ path: string; content: string; truncated: boolean }> {
    return this.request<{ path: string; content: string; truncated: boolean }>(
      `/runs/${encodeURIComponent(runId)}/artifacts/file?path=${encodeURIComponent(path)}`
    );
  }

  artifactsZipUrl(runId: string): string {
    return `${this.baseUrl}/runs/${encodeURIComponent(runId)}/artifacts.zip`;
  }

  async getAtlasSkills(pack?: Pack): Promise<SkillInfo[]> {
    const query = pack ? `?pack=${encodeURIComponent(pack)}` : '';
    return this.request<SkillInfo[]>(`/atlas/skills${query}`);
  }

  async getAtlasGraph(): Promise<GraphData> {
    return this.request<GraphData>('/atlas/graph');
  }

  async expandNode(cid: string, hops: number): Promise<GraphData> {
    return this.request<GraphData>(
      `/graphs/domain?cid=${encodeURIComponent(cid)}&hops=${encodeURIComponent(String(hops))}`
    );
  }
}

export const liveApi = new LiveApi();
