import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { Home } from '../pages/Home';

describe('Home Page', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders all sections with correct Hyperstudio content and links', async () => {
    await act(async () => {
      render(
        <MemoryRouter>
          <Home />
        </MemoryRouter>
      );
    });

    // 1. Hero
    expect(
      screen.getByRole('heading', { level: 1, name: 'Agents that act on connected data.' })
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /Give LUNA a case or a build\. It plans the work as a graph, equips sub-agents with skills by query/i
      )
    ).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: /OPEN THE PLATFORM/i }).length).toBeGreaterThan(0);

    // 1b. Two ways to use LUNA (Cases and coding agents over MCP)
    expect(screen.getByText('Investigate connected data')).toBeInTheDocument();
    expect(screen.getByText('Give your coding agent skills')).toBeInTheDocument();
    expect(screen.getByLabelText('Connect command')).toHaveTextContent('claude mcp add --transport http luna');

    // 2. FeatureGrid ("WHAT IT DOES")
    expect(screen.getByText('WHAT IT DOES')).toBeInTheDocument();
    expect(screen.getByText('Four ideas, built into the graph.')).toBeInTheDocument();
    expect(screen.getByText('SKILLS ASSIGNED BY QUERY')).toBeInTheDocument();
    expect(screen.getByText('ISOLATED AGENT GRAPHS')).toBeInTheDocument();
    expect(screen.getByText('CHECKED EVIDENCE')).toBeInTheDocument();
    expect(screen.getByText('APPROVAL-GATED ACTIONS')).toBeInTheDocument();

    // 3. UseCases ("TWO WAYS TO USE IT")
    expect(screen.getByText('TWO WAYS TO USE IT')).toBeInTheDocument();
    expect(screen.getByText('Investigate or build.')).toBeInTheDocument();
    expect(screen.getByText('INVESTIGATE')).toBeInTheDocument();
    expect(screen.getByText('BUILD')).toBeInTheDocument();
    expect(
      screen.getByText('Who is connected to the fraud involving customer cust-000?')
    ).toBeInTheDocument();
    expect(
      screen.getByText('Build a todo app: React + Vite frontend, Express backend, Postgres database.')
    ).toBeInTheDocument();

    const promptLinks = screen.getAllByRole('link', { name: /TRY THIS PROMPT ↗/i });
    expect(promptLinks.length).toBe(2);
    expect(promptLinks[0]).toHaveAttribute(
      'href',
      expect.stringContaining(encodeURIComponent('Who is connected to the fraud'))
    );

    // 4. FlowSteps ("HOW A REQUEST FLOWS")
    expect(screen.getByText('HOW A REQUEST FLOWS')).toBeInTheDocument();
    expect(screen.getByText('From prompt to traceable answer.')).toBeInTheDocument();
    expect(screen.getByText('01')).toBeInTheDocument();
    expect(screen.getByText('ROUTE')).toBeInTheDocument();
    expect(screen.getByText('05')).toBeInTheDocument();
    expect(screen.getByText('VERIFY AND ANSWER')).toBeInTheDocument();

    // 5. Manifesto ("Why graphs?")
    expect(screen.getByText('Why graphs?')).toBeInTheDocument();
    expect(
      screen.getByText('It does not make the agents smarter. It makes their work checkable.')
    ).toBeInTheDocument();

    // 6. UnderTheHood ("UNDER THE HOOD")
    expect(screen.getByText('UNDER THE HOOD')).toBeInTheDocument();
    expect(screen.getByText('FALKORDB')).toBeInTheDocument();
    expect(screen.getByText('MCP TOOL SCOPING')).toBeInTheDocument();
    expect(screen.getByText('PARAMETERIZED CYPHER')).toBeInTheDocument();
    expect(screen.getByText('READ-ONLY NATURAL LANGUAGE QUERIES')).toBeInTheDocument();
    expect(screen.getByText('PROVENANCE CHECKS')).toBeInTheDocument();
    expect(screen.getByText('APPROVAL GATE')).toBeInTheDocument();
    expect(
      screen.getByText(/Limits: build quality depends on the model you connect/i)
    ).toBeInTheDocument();

    // 7. FinalCta
    expect(screen.getByText('Try it on a real prompt.')).toBeInTheDocument();
  });
});
