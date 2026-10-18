import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import {
  Button,
  GhostButton,
  IconButton,
  Badge,
  StatusDot,
  Card,
  Modal,
  Drawer,
  Tabs,
  Markdown,
} from '../components/ui';

describe('UI Primitives', () => {
  it('Button renders text and optional arrow', () => {
    render(<Button showArrow>Try the Platform</Button>);
    expect(screen.getByText('Try the Platform')).toBeInTheDocument();
    expect(screen.getByText('↗')).toBeInTheDocument();
  });

  it('GhostButton renders uppercase action', () => {
    render(<GhostButton>How It Works</GhostButton>);
    expect(screen.getByText('How It Works')).toBeInTheDocument();
  });

  it('IconButton renders with accessible label', () => {
    render(
      <IconButton aria-label="Close panel">
        <span>X</span>
      </IconButton>
    );
    expect(screen.getByLabelText('Close panel')).toBeInTheDocument();
  });

  it('Badge renders text and optional pulse dot', () => {
    const { container } = render(<Badge hasPulseDot>Backend Online</Badge>);
    expect(screen.getByText('Backend Online')).toBeInTheDocument();
    expect(container.querySelector('[aria-hidden="true"]')).toBeInTheDocument();
  });

  it('StatusDot renders vocabulary statuses correctly', () => {
    const { rerender } = render(<StatusDot status="pending" />);
    expect(screen.getByText('PENDING')).toBeInTheDocument();

    rerender(<StatusDot status="running" />);
    expect(screen.getByText('RUNNING')).toBeInTheDocument();

    rerender(<StatusDot status="done" />);
    expect(screen.getByText('DONE')).toBeInTheDocument();

    rerender(<StatusDot status="failed" />);
    expect(screen.getByText('FAILED')).toBeInTheDocument();

    rerender(<StatusDot status="needs_input" />);
    expect(screen.getByText('NEEDS INPUT')).toBeInTheDocument();

    rerender(<StatusDot status="superseded" />);
    expect(screen.getByText('SUPERSEDED')).toBeInTheDocument();
  });

  it('Card renders with variant classes', () => {
    const { container, rerender } = render(<Card variant="failed">Failed Card</Card>);
    expect(container.firstChild).toHaveClass(/failed/);

    rerender(<Card variant="warning">Warning Card</Card>);
    expect(container.firstChild).toHaveClass(/warning/);
  });

  it('Modal renders content and dismisses on Escape key', () => {
    const onClose = vi.fn();
    render(
      <Modal isOpen={true} onClose={onClose} title="Test Modal">
        <div>Modal Body</div>
      </Modal>
    );
    expect(screen.getByText('Test Modal')).toBeInTheDocument();
    expect(screen.getByText('Modal Body')).toBeInTheDocument();

    fireEvent.keyDown(window, { key: 'Escape' });
    expect(onClose).toHaveBeenCalled();
  });

  it('Drawer renders and dismisses on Escape key', () => {
    const onClose = vi.fn();
    render(
      <Drawer isOpen={true} onClose={onClose} title="Details">
        <div>Drawer Content</div>
      </Drawer>
    );
    expect(screen.getByText('Details')).toBeInTheDocument();
    expect(screen.getByText('Drawer Content')).toBeInTheDocument();

    fireEvent.keyDown(window, { key: 'Escape' });
    expect(onClose).toHaveBeenCalled();
  });

  it('Tabs switches active tab on click', () => {
    const onChange = vi.fn();
    render(
      <Tabs
        tabs={[
          { id: 'tab1', label: 'Tab 1' },
          { id: 'tab2', label: 'Tab 2' },
        ]}
        activeId="tab1"
        onChange={onChange}
      />
    );
    fireEvent.click(screen.getByText('Tab 2'));
    expect(onChange).toHaveBeenCalledWith('tab2');
  });

  it('Markdown sanitizes malicious script tags and renders content', () => {
    const { container } = render(
      <Markdown content="Safe content <script>alert('xss')</script>" />
    );
    expect(screen.getByText(/Safe content/)).toBeInTheDocument();
    expect(container.querySelector('script')).toBeNull();
  });

  it('Markdown renders clickable CID chips when matching pattern', () => {
    const onCidClick = vi.fn();
    render(
      <Markdown content="Referenced customer `cust-000` in trace" onCidClick={onCidClick} />
    );
    const chip = screen.getByRole('button', { name: 'cust-000' });
    expect(chip).toBeInTheDocument();
    fireEvent.click(chip);
    expect(onCidClick).toHaveBeenCalledWith('cust-000');
  });
});
