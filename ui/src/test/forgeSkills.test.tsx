import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, within, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { MockApi } from '../api/mock/mockApi';
import { Platform } from '../pages/Platform';

// Cytoscape needs a real canvas/layout engine; stub it so the graphs mount in jsdom.
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

let api: MockApi;
vi.mock('../api', async (importOriginal) => {
  const orig = await importOriginal<typeof import('../api')>();
  return { ...orig, getApi: () => api };
});

function renderSkills() {
  render(
    <MemoryRouter initialEntries={['/platform?tab=skills']}>
      <Routes>
        <Route path="/platform" element={<Platform />} />
      </Routes>
    </MemoryRouter>
  );
}

describe('Platform Skills tab', () => {
  beforeEach(() => {
    api = new MockApi();
    api.subscribeForge = (opts) => {
      opts.onState('open');
      return () => undefined;
    };
  });

  it('filters skills by status', async () => {
    renderSkills();
    const table = await screen.findByRole('table', { name: /skills/i });
    expect(within(table).getAllByRole('row')).toHaveLength(8); // header + 7
    fireEvent.change(screen.getByLabelText(/^status$/i), { target: { value: 'pending_review' } });
    expect(within(table).getAllByRole('row')).toHaveLength(2);
    expect(within(table).getByText('SEO Audit')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/^status$/i), { target: { value: 'all' } });
    fireEvent.change(screen.getByLabelText(/^technology$/i), { target: { value: 'TailwindCSS' } });
    expect(within(table).getAllByRole('row')).toHaveLength(2);
    fireEvent.change(screen.getByLabelText(/^technology$/i), { target: { value: 'all' } });
    fireEvent.change(screen.getByLabelText(/^capability$/i), { target: { value: 'implement_backend' } });
    expect(within(table).getAllByRole('row')).toHaveLength(3);
  });

  it('opens skill detail with sections, checklist and graph', async () => {
    renderSkills();
    const table = await screen.findByRole('table', { name: /skills/i });
    fireEvent.click(within(table).getByRole('button', { name: /react vite pages/i }));
    const detail = await screen.findByRole('region', { name: /skill detail/i });
    expect(await within(detail).findByText('Overview')).toBeInTheDocument();
    expect(within(detail).getByText('Output verified')).toBeInTheDocument();
    expect(within(detail).getByRole('img', { name: /neighbourhood/i })).toBeInTheDocument();
  });

  it('approving a pending skill moves it out of the review queue', async () => {
    renderSkills();
    const queue = await screen.findByRole('region', { name: /review queue/i });
    expect(within(queue).getByText('SEO Audit')).toBeInTheDocument();
    fireEvent.click(within(queue).getByRole('button', { name: /approve seo audit/i }));
    await waitFor(() => expect(within(queue).queryByText('SEO Audit')).toBeNull());
    expect(within(queue).getByText(/no skills awaiting review/i)).toBeInTheDocument();
    const table = screen.getByRole('table', { name: /skills/i });
    expect(within(table).getByText('SEO Audit').closest('tr')).toHaveTextContent(/approved/i);
  });

  it('shows upload warnings returned by the API', async () => {
    api.uploadForgeSkill = vi.fn(async () => ({
      skill_id: 'new-skill',
      status: 'pending_review',
      warnings: ['missing checklist section'],
    }));
    renderSkills();
    const input = await screen.findByLabelText(/skill\.md file/i);
    const file = new File(['# New'], 'SKILL.md', { type: 'text/markdown' });
    fireEvent.change(input, { target: { files: [file] } });
    fireEvent.click(screen.getByRole('button', { name: /^upload skill$/i }));
    expect(await screen.findByText(/missing checklist section/)).toBeInTheDocument();
    expect(api.uploadForgeSkill).toHaveBeenCalledWith(file, []);
  });

  it('re-imports repo skills', async () => {
    api.reimportForgeSkills = vi.fn(async () => [{ skill_id: 'a', status: 'approved', warnings: [] }]);
    renderSkills();
    fireEvent.click(await screen.findByRole('button', { name: /re-import repo skills/i }));
    await waitFor(() => expect(api.reimportForgeSkills).toHaveBeenCalled());
    expect(await screen.findByText(/re-imported 1 skill/i)).toBeInTheDocument();
  });
});
