import { describe, it, expect } from 'vitest';
import { transformScopeToCytoscape } from '../utils/cytoscapeStyles';
import { GraphScopeData } from '../types';

describe('cytoscapeStyles', () => {
  it('correctly transforms graph nodes and assigns shapes and labels', () => {
    const scopeData: GraphScopeData = {
      nodes: [
        { id: 'cust_alpha', label: 'Customer Alpha', type: 'Customer' },
        { id: 'f_01', label: 'Suspicious Finding', type: 'Finding', status: 'active', verdict: 'suspicious' },
        { id: 'f_02', label: 'Superseded Finding', type: 'Finding', status: 'superseded', verdict: 'benign' },
      ],
      edges: [
        { source: 'cust_alpha', target: 'f_01', type: 'HAS_FINDING' },
        { source: 'f_01', target: 'f_02', type: 'SUPERSEDES' },
      ],
    };

    const elements = transformScopeToCytoscape(scopeData);
    expect(elements).toHaveLength(5); // 3 nodes + 2 edges

    const custNode = elements.find((el) => el.data.id === 'cust_alpha');
    expect(custNode).toBeDefined();
    expect(custNode?.group).toBe('nodes');
    expect(custNode?.data.type).toBe('Customer');

    const supersededNode = elements.find((el) => el.data.id === 'f_02');
    expect(supersededNode?.data.dimmed).toBe(true);

    const supersedesEdge = elements.find((el) => el.data.source === 'f_01' && el.data.target === 'f_02');
    expect(supersedesEdge).toBeDefined();
    expect(supersedesEdge?.group).toBe('edges');
    expect(supersedesEdge?.data.dashed).toBe(true);
  });

  it('infers node types from ID prefixes if type is missing', () => {
    const scopeData: GraphScopeData = {
      nodes: [
        { id: 'cust_42', label: 'cust_42' },
        { id: 'f_99', label: 'f_99' },
        { id: 'act_1', label: 'act_1' },
      ],
      edges: [],
    };

    const elements = transformScopeToCytoscape(scopeData);
    const cNode = elements.find((el) => el.data.id === 'cust_42');
    const fNode = elements.find((el) => el.data.id === 'f_99');
    const aNode = elements.find((el) => el.data.id === 'act_1');

    expect(cNode?.data.type).toBe('Customer');
    expect(fNode?.data.type).toBe('Finding');
    expect(aNode?.data.type).toBe('Action');
  });
});
