import { describe, it, expect } from 'vitest';
import { render, screen, act, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';
import { MemoryRouter } from 'react-router-dom';
import { SkillAtlas } from '../pages/SkillAtlas';

describe('Skill Atlas Page', () => {
  it('loads and displays skills in list view', async () => {
    render(
      <MemoryRouter>
        <SkillAtlas />
      </MemoryRouter>
    );

    expect(
      screen.getByRole('heading', { level: 1, name: 'Every skill the orchestrator can choose.' })
    ).toBeInTheDocument();
    expect(
      screen.getByText('Scores are track records that update after approved runs.')
    ).toBeInTheDocument();

    // Wait for skills to load from api
    await waitFor(() => {
      expect(screen.getByText('Connection Tracer')).toBeInTheDocument();
    });

    expect(screen.getByText('React + Vite Frontend')).toBeInTheDocument();
    expect(screen.getByText('Express REST Backend')).toBeInTheDocument();
  });

  it('filters skills by search input', async () => {
    render(
      <MemoryRouter>
        <SkillAtlas />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Connection Tracer')).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText(
      'Search skills, technologies, capabilities'
    );

    act(() => {
      fireEvent.change(searchInput, { target: { value: 'postgres' } });
    });

    await waitFor(() => {
      expect(screen.getByText('PostgreSQL Relational Storage')).toBeInTheDocument();
      expect(screen.queryByText('React + Vite Frontend')).toBeNull();
    });
  });

  it('opens drawer on skill click and shows restricted policy notice for restricted skills', async () => {
    render(
      <MemoryRouter>
        <SkillAtlas />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Bulk Unfiltered Linker')).toBeInTheDocument();
    });

    const bulkLinkerRow = screen.getByText('Bulk Unfiltered Linker');
    act(() => {
      fireEvent.click(bulkLinkerRow);
    });

    await waitFor(() => {
      expect(
        screen.getByText(
          'Restricted by policy. The orchestrator always rejects this skill and records why.'
        )
      ).toBeInTheDocument();
    });

    expect(screen.getByText('TOOLS EXPOSED')).toBeInTheDocument();
    expect(screen.getByText('PROMPT FRAGMENT')).toBeInTheDocument();

    // Toggle prompt fragment
    const toggleBtn = screen.getByText('Show prompt fragment');
    act(() => {
      fireEvent.click(toggleBtn);
    });
    expect(screen.getByText('Hide prompt fragment')).toBeInTheDocument();
  });

  it('switches between list and graph views', async () => {
    render(
      <MemoryRouter>
        <SkillAtlas />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Connection Tracer')).toBeInTheDocument();
    });

    const graphTab = screen.getByRole('tab', { name: 'GRAPH' });
    act(() => {
      fireEvent.click(graphTab);
    });

    expect(screen.getByText('LEGEND')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Zoom in' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Fit graph to view' })).toBeInTheDocument();
  });
});
