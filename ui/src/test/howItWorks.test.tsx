import { describe, it, expect } from 'vitest';
import { render, screen, act, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { HowItWorks } from '../pages/HowItWorks';

describe('HowItWorks Page', () => {
  it('renders header, walkthrough stepper, and initial Route stage', () => {
    render(
      <MemoryRouter>
        <HowItWorks />
      </MemoryRouter>
    );

    // Title & subtitle
    expect(screen.getByText('One request, followed end to end.')).toBeInTheDocument();
    expect(
      screen.getByText('Pick a run below and step through what the system actually records.')
    ).toBeInTheDocument();

    // Stage 1 Route is initially expanded
    expect(screen.getByText('Route')).toBeInTheDocument();
    expect(screen.getByText('WHAT GETS STORED')).toBeInTheDocument();
    expect(screen.getByText('FIXTURE VALUES')).toBeInTheDocument();
  });

  it('navigates through stages using Next and Previous buttons', () => {
    render(
      <MemoryRouter>
        <HowItWorks />
      </MemoryRouter>
    );

    expect(screen.getByText('STAGE 1 OF 6')).toBeInTheDocument();

    const nextBtn = screen.getByRole('button', { name: 'NEXT' });
    act(() => {
      fireEvent.click(nextBtn);
    });

    expect(screen.getByText('STAGE 2 OF 6')).toBeInTheDocument();
    expect(screen.getByText('Plan')).toBeInTheDocument();

    const prevBtn = screen.getByRole('button', { name: 'PREVIOUS' });
    act(() => {
      fireEvent.click(prevBtn);
    });

    expect(screen.getByText('STAGE 1 OF 6')).toBeInTheDocument();
  });

  it('switches between INVESTIGATE RUN and BUILD RUN tabs', () => {
    render(
      <MemoryRouter>
        <HowItWorks />
      </MemoryRouter>
    );

    const buildTab = screen.getByRole('tab', { name: 'BUILD RUN' });
    act(() => {
      fireEvent.click(buildTab);
    });

    // Check build-specific content
    expect(screen.getByText(/Requirements: frontend=react\+vite/i)).toBeInTheDocument();
  });

  it('renders Glossary and Safety Model sections', () => {
    render(
      <MemoryRouter>
        <HowItWorks />
      </MemoryRouter>
    );

    // Glossary terms
    expect(screen.getByText('Atlas')).toBeInTheDocument();
    expect(screen.getByText('Pack')).toBeInTheDocument();
    expect(screen.getByText('Skill')).toBeInTheDocument();
    expect(screen.getByText('Slice')).toBeInTheDocument();
    expect(screen.getByText('Finding')).toBeInTheDocument();
    expect(screen.getByText('Contract')).toBeInTheDocument();
    expect(screen.getByText('Decision')).toBeInTheDocument();
    expect(screen.getByText('Action')).toBeInTheDocument();

    // Safety Model
    expect(screen.getByText('Files stay in a sandbox')).toBeInTheDocument();
    expect(screen.getByText('Nothing runs without approval')).toBeInTheDocument();
    expect(screen.getByText('Queries are constrained')).toBeInTheDocument();
  });
});
