import { describe, it, expect, vi } from 'vitest';
import { render, screen, act, fireEvent, waitFor } from '@testing-library/react';
import { TraceView } from '../components/graph/TraceView';

describe('TraceView Component', () => {
  it('loads trace data, renders toolbar, summary strip, and steps', async () => {
    const handleBack = vi.fn();

    render(
      <TraceView
        runId="run_f1"
        pack="investigate"
        onBack={handleBack}
      />
    );

    // Initial loading state
    expect(screen.getByText('TRACING...')).toBeInTheDocument();

    // After data loads
    await waitFor(() => {
      expect(screen.getByText(/TRACE · INVESTIGATE/i)).toBeInTheDocument();
    });

    // Mode badge
    expect(screen.getByText('TRAVERSAL')).toBeInTheDocument();

    // Summary strip
    expect(
      screen.getByText(
        'cust-000 shares a phone with cust-003, who pays from the same account as cust-005, who filed a claim treated by prov-ring.'
      )
    ).toBeInTheDocument();

    // Step list contains traversal steps
    expect(screen.getAllByText(/cust-000/i).length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText(/USES_PHONE/i).length).toBeGreaterThanOrEqual(1);
  });

  it('toggles legend visibility on legend button click', async () => {
    render(
      <TraceView
        runId="run_f1"
        pack="investigate"
        onBack={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText(/TRACE · INVESTIGATE/i)).toBeInTheDocument();
    });

    // Legend initially not visible
    expect(screen.queryByText('GRAPH LEGEND')).toBeNull();

    // Click Legend button
    const legendBtn = screen.getByRole('button', { name: 'LEGEND' });
    act(() => {
      fireEvent.click(legendBtn);
    });

    // Legend is now visible
    expect(screen.getByText('GRAPH LEGEND')).toBeInTheDocument();
    expect(screen.getByText('NODE SHAPES')).toBeInTheDocument();
    expect(screen.getByText('EDGE STYLES')).toBeInTheDocument();

    // Click Close button in legend
    const closeBtn = screen.getByRole('button', { name: 'Close legend' });
    act(() => {
      fireEvent.click(closeBtn);
    });

    expect(screen.queryByText('GRAPH LEGEND')).toBeNull();
  });

  it('calls onBack when back button is clicked', async () => {
    const handleBack = vi.fn();
    render(
      <TraceView
        runId="run_f1"
        pack="investigate"
        onBack={handleBack}
      />
    );

    await waitFor(() => {
      expect(screen.getByText(/TRACE · INVESTIGATE/i)).toBeInTheDocument();
    });

    const backBtn = screen.getByRole('button', { name: 'Back to conversation' });
    act(() => {
      fireEvent.click(backBtn);
    });

    expect(handleBack).toHaveBeenCalledTimes(1);
  });

  it('supports scrubber play, pause, seek, and speed changes', async () => {
    render(
      <TraceView
        runId="run_f1"
        pack="investigate"
        onBack={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText(/TRACE · INVESTIGATE/i)).toBeInTheDocument();
    });

    // Scrubber readout
    const readout = document.querySelector('footer div[class*="readout"]');
    expect(readout?.textContent).toContain('STEP');

    // Play/Pause button
    const playBtn = screen.getByRole('button', { name: /Play trace|Pause trace/i });
    expect(playBtn).toBeInTheDocument();

    // Step forward
    const nextBtn = screen.getByRole('button', { name: 'Step forward' });
    act(() => {
      fireEvent.click(nextBtn);
    });

    // Speed button
    const speed2x = screen.getByRole('button', { name: '2X' });
    act(() => {
      fireEvent.click(speed2x);
    });
  });
});
