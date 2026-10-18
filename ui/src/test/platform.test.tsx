import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, act, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { Platform } from '../pages/Platform';

describe('Platform Chat Page', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('renders empty state with 4 example prompt chips and fills composer on click', async () => {
    render(
      <MemoryRouter initialEntries={['/platform?tab=cases']}>
        <Routes>
          <Route path="/platform" element={<Platform />} />
          <Route path="/platform/:conversationId" element={<Platform />} />
        </Routes>
      </MemoryRouter>
    );

    // Empty state heading
    expect(screen.getByText('What should the agents work on?')).toBeInTheDocument();
    expect(
      screen.getByText('Ask a question about connected data, or describe something to build.')
    ).toBeInTheDocument();

    // 4 chips
    const chip1 = screen.getByText('Who is connected to the fraud involving customer cust-000?');
    expect(chip1).toBeInTheDocument();
    expect(screen.getByText('Is customer cust-010 part of a fraud ring?')).toBeInTheDocument();
    expect(
      screen.getByText('Build a todo app: React + Vite frontend, Express backend, Postgres database.')
    ).toBeInTheDocument();
    expect(screen.getByText('Build a notes API with Fastify and SQLite.')).toBeInTheDocument();

    // Click chip1 -> fills composer
    act(() => {
      fireEvent.click(chip1);
    });

    const textarea = screen.getByLabelText('Composer prompt input') as HTMLTextAreaElement;
    expect(textarea.value).toBe('Who is connected to the fraud involving customer cust-000?');
  });

  it('sends prompt, displays user message, and receives streaming assistant run', async () => {
    render(
      <MemoryRouter initialEntries={['/platform/test_conv_01?tab=cases']}>
        <Routes>
          <Route path="/platform/:conversationId" element={<Platform />} />
        </Routes>
      </MemoryRouter>
    );

    const chip = screen.getByText('Who is connected to the fraud involving customer cust-000?');
    act(() => {
      fireEvent.click(chip);
    });

    const textarea = screen.getByLabelText('Composer prompt input');
    await act(async () => {
      fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false });
    });

    // Assistant message header appears with LUNA label and backends
    await waitFor(() => {
      expect(screen.getAllByText('LUNA').length).toBeGreaterThanOrEqual(2);
      expect(screen.getByText('ROUTED TO INVESTIGATE')).toBeInTheDocument();
    });
  });

  it('approves action request and saves approver name in localStorage', async () => {
    render(
      <MemoryRouter initialEntries={['/platform?tab=cases']}>
        <Routes>
          <Route path="/platform" element={<Platform />} />
          <Route path="/platform/:conversationId" element={<Platform />} />
        </Routes>
      </MemoryRouter>
    );

    const chip = screen.getByText('Who is connected to the fraud involving customer cust-000?');
    act(() => {
      fireEvent.click(chip);
    });

    const textarea = screen.getByLabelText('Composer prompt input');
    await act(async () => {
      fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false });
    });

    // Wait for APPROVAL NEEDED block
    await waitFor(() => {
      expect(screen.getByText('APPROVAL NEEDED')).toBeInTheDocument();
    });

    const approveBtn = screen.getByRole('button', { name: 'APPROVE' });
    act(() => {
      fireEvent.click(approveBtn);
    });

    // Approver modal opens
    expect(screen.getByText('APPROVE ACTION')).toBeInTheDocument();
    const nameInput = screen.getByLabelText('Your Name');

    act(() => {
      fireEvent.change(nameInput, { target: { value: 'Agent Smith' } });
    });

    const confirmBtn = screen.getByRole('button', { name: 'CONFIRM APPROVAL' });
    await act(async () => {
      fireEvent.click(confirmBtn);
    });

    // Saved to localStorage
    expect(localStorage.getItem('luna.approver')).toBe('Agent Smith');
  });
});
