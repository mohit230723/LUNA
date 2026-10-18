import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  isRunEventType,
  isRunEvent,
  isBlock,
  filterValidBlocks,
} from '../api/guards';
import { LiveApi, ApiError } from '../api/live';
import { getApi, getApiMode, setApiMode } from '../api/index';
import { mockApi } from '../api/mock/mockApi';

describe('Contract Runtime Guards', () => {
  it('validates run event types correctly', () => {
    expect(isRunEventType('routed')).toBe(true);
    expect(isRunEventType('traversal_step')).toBe(true);
    expect(isRunEventType('contract_violation')).toBe(true);
    expect(isRunEventType('completed')).toBe(true);
    expect(isRunEventType('invalid_type')).toBe(false);
    expect(isRunEventType(123)).toBe(false);
    expect(isRunEventType(null)).toBe(false);
  });

  it('validates run event objects correctly', () => {
    const validEvent = {
      run_id: 'run-1',
      seq: 1,
      ts: new Date().toISOString(),
      type: 'routed',
      data: { pack: 'investigate' },
    };
    expect(isRunEvent(validEvent)).toBe(true);

    expect(isRunEvent(null)).toBe(false);
    expect(isRunEvent({})).toBe(false);
    expect(isRunEvent({ ...validEvent, type: 'unknown_stage' })).toBe(false);
    expect(isRunEvent({ ...validEvent, seq: '1' })).toBe(false);
    expect(isRunEvent({ ...validEvent, data: null })).toBe(false);
  });

  it('validates block objects and filters unknown blocks safely', () => {
    const validTextBlock = { type: 'text', data: { markdown: 'hello' } };
    const validRoutingBlock = {
      type: 'routing',
      data: { pack: 'investigate', intent: 'test', confidence: 0.9, backend: 'scripted' },
    };
    const invalidBlock = { type: 'future_ai_block', data: { foo: 'bar' } };
    const malformedBlock = { type: 'text', data: null };

    expect(isBlock(validTextBlock)).toBe(true);
    expect(isBlock(validRoutingBlock)).toBe(true);
    expect(isBlock(invalidBlock)).toBe(false);
    expect(isBlock(malformedBlock)).toBe(false);

    const filtered = filterValidBlocks([
      validTextBlock,
      invalidBlock,
      validRoutingBlock,
      malformedBlock,
    ]);
    expect(filtered).toHaveLength(2);
    expect(filtered[0]).toEqual(validTextBlock);
    expect(filtered[1]).toEqual(validRoutingBlock);
  });
});

describe('LiveApi Client', () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it('formats GET and POST endpoints correctly', async () => {
    const api = new LiveApi('/api');

    const mockFetch = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
      if (url === '/api/health') {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({ status: 'ok', falkordb: true, llm: { provider: 'test', reachable: true } }),
        });
      }
      if (url === '/api/chat/conversations' && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve([{ id: 'c-1', title: 'Test Conv', updated_at: 'now' }]),
        });
      }
      if (url === '/api/chat/conversations' && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({ id: 'new-c' }),
        });
      }
      if (url === '/api/runs/r-1/cancel') {
        return Promise.resolve({
          ok: true,
          status: 204,
          json: () => Promise.resolve(),
        });
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({}),
      });
    });

    global.fetch = mockFetch as unknown as typeof fetch;

    const health = await api.health();
    expect(health.status).toBe('ok');

    const convs = await api.listConversations();
    expect(convs).toHaveLength(1);
    expect(convs[0]?.id).toBe('c-1');

    const created = await api.createConversation();
    expect(created.id).toBe('new-c');

    await api.cancelRun('r-1');
    expect(mockFetch).toHaveBeenCalledWith('/api/runs/r-1/cancel', expect.objectContaining({ method: 'POST' }));
  });

  it('surfaces ApiError with status, error, and detail on HTTP failure', async () => {
    const api = new LiveApi('/api');

    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      statusText: 'Bad Request',
      json: () => Promise.resolve({ error: 'Validation failed', detail: 'Invalid CID cust-999' }),
    } as unknown as Response);

    await expect(api.getTrace('bad-run')).rejects.toThrow('Validation failed: Invalid CID cust-999');

    try {
      await api.getTrace('bad-run');
    } catch (err: unknown) {
      expect(err).toBeInstanceOf(ApiError);
      const apiErr = err as ApiError;
      expect(apiErr.status).toBe(400);
      expect(apiErr.error).toBe('Validation failed');
      expect(apiErr.detail).toBe('Invalid CID cust-999');
    }
  });

  it('filters invalid message blocks in getConversation', async () => {
    const api = new LiveApi('/api');

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () =>
        Promise.resolve({
          id: 'c-1',
          title: 'Conv',
          messages: [
            {
              id: 'm-1',
              role: 'assistant',
              created_at: 'now',
              blocks: [
                { type: 'text', data: { markdown: 'Hello' } },
                { type: 'unknown_block_from_future', data: {} },
              ],
            },
          ],
        }),
    } as unknown as Response);

    const conv = await api.getConversation('c-1');
    expect(conv.messages[0]?.blocks).toHaveLength(1);
    expect(conv.messages[0]?.blocks[0]?.type).toBe('text');
  });

  it('generates correct artifactsZipUrl', () => {
    const api = new LiveApi('/api');
    expect(api.artifactsZipUrl('run-123')).toBe('/api/runs/run-123/artifacts.zip');
  });
});

describe('API Mode Switching', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('defaults to mock or env configuration', () => {
    expect(getApiMode()).toBe('mock');
    expect(getApi()).toBe(mockApi);
  });

  it('switches to live mode when configured in luna.prefs', () => {
    setApiMode('live');
    expect(getApiMode()).toBe('live');
    expect(localStorage.getItem('luna.prefs')).toContain('"apiMode":"live"');

    const currentApi = getApi();
    expect(currentApi).toBeInstanceOf(LiveApi);

    setApiMode('mock');
    expect(getApiMode()).toBe('mock');
    expect(getApi()).toBe(mockApi);
  });

  it('forge: forgeRun GETs the run and uploadForgeSkill posts multipart', async () => {
    const api = new LiveApi('/api');
    const mockFetch = vi.fn().mockImplementation((url: string) =>
      Promise.resolve({
        ok: true,
        status: 200,
        json: () =>
          Promise.resolve(url.endsWith('/upload') ? { skill_id: 's', status: 'pending_review', warnings: [] } : { run: {}, tasks: [], report: null }),
      })
    );
    global.fetch = mockFetch as unknown as typeof fetch;

    await api.forgeRun('r1');
    expect(mockFetch.mock.calls[0]![0]).toBe('/api/forge/runs/r1');

    const skill = new File(['x'], 'SKILL.md');
    const ref = new File(['y'], 'ref.md');
    await api.uploadForgeSkill(skill, [ref, ref]);
    const [url, init] = mockFetch.mock.calls[1]!;
    expect(url).toBe('/api/forge/skills/upload');
    expect(init.method).toBe('POST');
    const body = init.body as FormData;
    expect(body.get('skill')).toBeInstanceOf(File);
    expect(body.getAll('references')).toHaveLength(2);
  });
});
