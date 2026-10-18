import { describe, it, expect } from 'vitest';
import { toElements, inferNodeType } from '../components/graph/toElements';
import type { TraceNode, TraceEdge } from '../api/contract';

describe('toElements converter', () => {
  it('infers node types correctly from props, label, and ID prefixes', () => {
    const node1: TraceNode = { id: 'cust-000', label: 'cust-000', props: {} };
    expect(inferNodeType(node1)).toBe('Customer');

    const node2: TraceNode = { id: 'ph-01', label: 'Phone 1', props: {} };
    expect(inferNodeType(node2)).toBe('Phone');

    const node3: TraceNode = { id: 'f-1', label: 'Finding 1', props: { type: 'Finding' } };
    expect(inferNodeType(node3)).toBe('Finding');

    const node4: TraceNode = { id: 'contr-01', label: 'Contract 1', props: {} };
    expect(inferNodeType(node4)).toBe('Contract');
  });

  it('marks on-path nodes and edges with on-path class', () => {
    const nodes: TraceNode[] = [
      { id: 'cust-000', label: 'cust-000', props: {} },
      { id: 'cust-001', label: 'cust-001', props: {} },
    ];
    const edges: TraceEdge[] = [
      { id: 'e1', src: 'cust-000', dst: 'cust-001', rel: 'KNOWS', on_path: true },
    ];

    const { elements } = toElements({
      nodes,
      edges,
      pathNodeIds: ['cust-000'],
    });

    const n0 = elements.nodes.find((n) => n.data.id === 'cust-000');
    expect(n0?.classes).toContain('on-path');

    const n1 = elements.nodes.find((n) => n.data.id === 'cust-001');
    expect(n1?.classes).not.toContain('on-path');

    const e0 = elements.edges.find((e) => e.data.id === 'e1');
    expect(e0?.classes).toContain('on-path');
  });

  it('marks superseded nodes and rejected edges with appropriate classes', () => {
    const nodes: TraceNode[] = [
      { id: 'f-1', label: 'Finding 1', props: { status: 'superseded' } },
    ];
    const edges: TraceEdge[] = [
      { id: 'e1', src: 'f-1', dst: 'cust-000', rel: 'REJECTED' },
    ];

    const { elements } = toElements({
      nodes: [...nodes, { id: 'cust-000', label: 'cust-000', props: {} }],
      edges,
    });

    const n = elements.nodes.find((n) => n.data.id === 'f-1');
    expect(n?.classes).toContain('superseded');

    const e = elements.edges.find((e) => e.data.id === 'e1');
    expect(e?.classes).toContain('rejected');
  });

  it('marks context nodes with context class and prepends x to violation labels', () => {
    const nodes: TraceNode[] = [
      { id: 'ctx-1', label: 'Context Node', props: {}, context: true },
      { id: 'viol-1', label: 'missing_endpoint', props: { type: 'Violation' } },
    ];

    const { elements } = toElements({ nodes, edges: [] });

    const ctx = elements.nodes.find((n) => n.data.id === 'ctx-1');
    expect(ctx?.classes).toContain('context');

    const viol = elements.nodes.find((n) => n.data.id === 'viol-1');
    expect(viol?.data.label).toBe('x missing_endpoint');
  });

  it('respects node and edge truncation caps', () => {
    const nodes: TraceNode[] = Array.from({ length: 600 }, (_, i) => ({
      id: `n_${i}`,
      label: `Node ${i}`,
      props: {},
    }));
    const edges: TraceEdge[] = Array.from({ length: 2000 }, (_, i) => ({
      id: `e_${i}`,
      src: `n_${i % 500}`,
      dst: `n_${(i + 1) % 500}`,
      rel: 'LINK',
    }));

    const result = toElements({ nodes, edges });
    expect(result.truncated).toBe(true);
    expect(result.elements.nodes.length).toBeLessThanOrEqual(500);
    expect(result.elements.edges.length).toBeLessThanOrEqual(1500);
  });
});
