import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, act, fireEvent, within, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import type { ForgeEvent, ForgeReport, ForgeRunDetail } from '../api/contract';
import { MockApi } from '../api/mock/mockApi';
import { Platform } from '../pages/Platform';

// Cytoscape needs a real canvas/layout engine; stub it so ForgeDag mounts in jsdom.
vi.mock('cytoscape', () => {
  const chain = () => {
    const c: Record<string, unknown> = {};
    for (const k of ['on', 'off', 'run', 'fit', 'addClass', 'removeClass', 'unselect', 'select', 'style']) {
      c[k] = () => c;
    }
    return c;
  };
  const factory = Object.assign(
    vi.fn(() => {
      const cy = chain();
      cy.json = () => cy;
      cy.elements = () => chain();
      cy.nodes = () => chain();
      cy.getElementById = () => chain();
      cy.layout = () => chain();
      cy.destroy = () => undefined;
      cy.batch = (fn: () => void) => fn();
      cy.add = () => chain();
      cy.remove = () => chain();
      return cy;
    }),
    { use: vi.fn() }
  );
  return { default: factory };
});
vi.mock('cytoscape-dagre', () => ({ default: () => undefined }));

const RUN_ID = 'run-portfolio-1';

let api: MockApi;
let emit: (e: ForgeEvent) => void;
let serverRun: ForgeRunDetail;

vi.mock('../api', async (importOriginal) => {
  const orig = await importOriginal<typeof import('../api')>();
  return { ...orig, getApi: () => api };
});

const REPORT: ForgeReport = {
  run_id: RUN_ID,
  status: 'complete',
  missing: [],
  tasks: [],
  overlaps: {},
  gaps: [],
  summary: '3/3 tasks complete across 3 waves',
};

async function setup() {
  serverRun = await new MockApi().forgeRun(RUN_ID);
  serverRun.tasks[1]!.candidates = [
    { skill_id: 'react-vite-pages', score: 0.9, overlap: 3, rejected_reason: '' },
    { skill_id: 'ui-styling', score: 0.4, overlap: 1, rejected_reason: 'lower score' },
  ];
  api = new MockApi();
  api.forgeRun = vi.fn(async (id: string) => {
    if (id !== RUN_ID) throw new Error('nope');
    return JSON.parse(JSON.stringify(serverRun)) as ForgeRunDetail;
  });
  api.subscribeForge = (opts) => {
    emit = opts.onEvent;
    opts.onState('open');
    return () => opts.onState('closed');
  };
}

function renderPlatform(entry = '/platform') {
  render(
    <MemoryRouter initialEntries={[entry]}>
      <Routes>
        <Route path="/platform" element={<Platform />} />
        <Route path="/platform/:conversationId" element={<Platform />} />
      </Routes>
    </MemoryRouter>
  );
}

describe('Platform Agents tab', () => {
  beforeEach(async () => {
    await setup();
    Object.assign(navigator, { clipboard: { writeText: vi.fn(() => Promise.resolve()) } });
  });

  it('defaults to the Agents tab and shows both connect snippets', async () => {
    await renderPlatform();
    const tab = screen.getByRole('tab', { name: 'Agents' });
    expect(tab).toHaveAttribute('aria-selected', 'true');
    expect(await screen.findByText(/claude mcp add --transport http luna/)).toBeInTheDocument();
    expect(screen.getByText(/"serverUrl"/)).toBeInTheDocument();
    expect(screen.getByText(/Agent panel → MCP menu → Manage MCP Servers → View raw config/)).toBeInTheDocument();
    // token variants hidden when no token is required
    expect(screen.queryByText(/Bearer <token>/)).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: /copy claude code command/i }));
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
      'claude mcp add --transport http luna http://localhost:8000/mcp'
    );
  });

  it('lists connected and idle agents', async () => {
    await renderPlatform();
    const list = await screen.findByRole('list', { name: /connected agents/i });
    expect(within(list).getByText('claude-code')).toBeInTheDocument();
    expect(within(list).getByText('antigravity')).toBeInTheDocument();
    expect(within(list).getByText(/idle/i)).toBeInTheDocument();
    expect(within(list).getByText(/^connected$/i)).toBeInTheDocument();
  });

  it('renders the run DAG task cards with skills', async () => {
    await renderPlatform();
    const card = await screen.findByRole('article', { name: /implement frontend/i });
    expect(within(card).getByText('react-vite-pages')).toBeInTheDocument();
    expect(within(card).getByText(/claimed/i)).toBeInTheDocument();
    expect(within(card).getByText(/Why this skill\?/)).toBeInTheDocument();
    expect(within(card).getByText(/lower score/)).toBeInTheDocument();
    expect(screen.getByRole('article', { name: /scaffold project/i })).toHaveTextContent('project-scaffold');
  });

  it('applies live task_updated events', async () => {
    await renderPlatform();
    const card = await screen.findByRole('article', { name: /implement frontend/i });
    await waitFor(() => expect(emit).toBeDefined());
    serverRun.tasks[1] = {
      ...serverRun.tasks[1]!,
      status: 'done',
      result: { summary: 'Pages built', files: ['src/App.tsx'], checks: [{ id: 'c1', passed: true }] },
    };
    act(() => {
      emit({
        seq: 1,
        ts: '2026-10-19T09:10:00+00:00',
        type: 'task_updated',
        data: {
          run_id: RUN_ID,
          task_id: 'implement_frontend',
          status: 'done',
          result: { summary: 'Pages built', files: ['src/App.tsx'], checks: [{ id: 'c1', passed: true }] },
        },
      });
    });
    expect(await within(card).findByText(/done/i)).toBeInTheDocument();
    expect(within(card).getByText('Pages built')).toBeInTheDocument();
    expect(within(card).getByText('src/App.tsx')).toBeInTheDocument();
    // Ruling 9: refetches the run after the event
    await waitFor(() => expect(api.forgeRun).toHaveBeenCalledTimes(2), { timeout: 2000 });
  });

  it('shows assembled report after run_assembled', async () => {
    await renderPlatform();
    await screen.findByRole('article', { name: /implement frontend/i });
    await waitFor(() => expect(emit).toBeDefined());
    serverRun.report = REPORT;
    act(() => {
      emit({ seq: 3, ts: '2026-10-19T09:20:00+00:00', type: 'run_assembled', data: { run_id: RUN_ID, report: REPORT } });
    });
    expect(await screen.findByText(/3\/3 tasks complete/)).toBeInTheDocument();
  });

  it('Cases tab still renders case workspace', async () => {
    await renderPlatform('/platform?tab=cases');
    expect(screen.getByRole('tab', { name: 'Cases' })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('heading', { name: 'LUNA Case Workspace' })).toBeInTheDocument();
    expect(screen.queryByText(/claude mcp add/)).toBeNull();
  });

  it('switches tabs with arrow keys', async () => {
    await renderPlatform();
    const agents = screen.getByRole('tab', { name: 'Agents' });
    act(() => {
      fireEvent.keyDown(agents, { key: 'ArrowRight' });
    });
    const cases = screen.getByRole('tab', { name: 'Cases' });
    expect(cases).toHaveAttribute('aria-selected', 'true');
    expect(cases).toHaveFocus();
  });
});
