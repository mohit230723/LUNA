import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { App } from '../App';
import { TopNav } from '../components/layout/TopNav';
import { Footer } from '../components/layout/Footer';

describe('Layout and Routing', () => {
  const originalTitle = document.title;

  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    document.title = originalTitle;
    vi.useRealTimers();
  });

  it('renders Home on root path and updates document title', async () => {
    await act(async () => {
      render(
        <MemoryRouter initialEntries={['/']}>
          <App />
        </MemoryRouter>
      );
    });

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
      'Agents that act on connected data.'
    );
    expect(document.title).toBe('LUNA OS');
  });

  it('renders How It Works page and title', async () => {
    await act(async () => {
      render(
        <MemoryRouter initialEntries={['/how-it-works']}>
          <App />
        </MemoryRouter>
      );
    });

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
      'One request, followed end to end.'
    );
    expect(document.title).toBe('How it works · LUNA OS');
  });

  it('renders Skill Atlas page and title', async () => {
    await act(async () => {
      render(
        <MemoryRouter initialEntries={['/skills']}>
          <App />
        </MemoryRouter>
      );
    });

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
      'Every skill the orchestrator can choose.'
    );
    expect(document.title).toBe('Skill Atlas · LUNA OS');
  });

  it('renders Platform page with compact nav and no footer', async () => {
    await act(async () => {
      render(
        <MemoryRouter initialEntries={['/platform']}>
          <App />
        </MemoryRouter>
      );
    });

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Platform');
    expect(document.title).toBe('Platform · LUNA OS');
    // Footer should not be present on platform
    expect(screen.queryByRole('contentinfo')).toBeNull();
  });

  it('renders 404 page on unknown route', async () => {
    await act(async () => {
      render(
        <MemoryRouter initialEntries={['/not-a-real-page']}>
          <App />
        </MemoryRouter>
      );
    });

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('404');
    expect(screen.getByText('That page is not in the graph.')).toBeInTheDocument();
    expect(document.title).toBe('Not found · LUNA OS');
  });

  it('renders TopNav with links and brand', async () => {
    await act(async () => {
      render(
        <MemoryRouter initialEntries={['/']}>
          <TopNav />
        </MemoryRouter>
      );
    });

    expect(screen.getByText('LUNA')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'HOME' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'HOW IT WORKS' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'SKILL ATLAS' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'PLATFORM' })).toBeInTheDocument();
  });

  it('renders Footer with brand, tagline, and open tooling note', async () => {
    await act(async () => {
      render(
        <MemoryRouter initialEntries={['/']}>
          <Footer />
        </MemoryRouter>
      );
    });

    expect(screen.getByText('LUNA OS')).toBeInTheDocument();
    expect(screen.getByText('Agents that act on connected data.')).toBeInTheDocument();
    expect(
      screen.getByText('Built on FalkorDB, MCP, and open tooling.')
    ).toBeInTheDocument();
  });
});
