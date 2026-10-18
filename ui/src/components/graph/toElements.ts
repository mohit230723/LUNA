import type { ElementsDefinition } from 'cytoscape';
import type { TraceNode, TraceEdge, TraceStep } from '../../api/contract';

export interface ToElementsOptions {
  nodes: TraceNode[];
  edges: TraceEdge[];
  pathNodeIds?: string[];
  revealedSteps?: TraceStep[];
  activeStepSeq?: number;
  showAll?: boolean;
  maxNodes?: number;
  maxEdges?: number;
}

export function inferNodeType(node: TraceNode): string {
  if (typeof node.props?.type === 'string' && node.props.type.trim()) {
    return node.props.type;
  }
  const idLower = node.id.toLowerCase();
  const labelLower = (node.label || '').toLowerCase();

  if (idLower.startsWith('cust-') || labelLower.includes('customer')) return 'Customer';
  if (idLower.startsWith('ph-') || labelLower.includes('phone')) return 'Phone';
  if (idLower.startsWith('ba-') || labelLower.includes('bankaccount') || labelLower.includes('account')) return 'BankAccount';
  if (idLower.startsWith('addr-') || labelLower.includes('address')) return 'Address';
  if (idLower.startsWith('claim-') || labelLower.includes('claim')) return 'InsuranceClaim';
  if (idLower.startsWith('prov-') || labelLower.includes('provider')) return 'Provider';
  if (idLower.startsWith('req-') || labelLower.includes('requirement')) return 'Requirement';
  if (idLower.startsWith('cmp-') || labelLower.includes('component')) return 'Component';
  if (idLower.startsWith('skill-') || labelLower.includes('skill')) return 'SkillRef';
  if (idLower.startsWith('ag-') || labelLower.includes('agent')) return 'Agent';
  if (idLower.startsWith('art-') || labelLower.includes('artifact') || labelLower.includes('file')) return 'Artifact';
  if (idLower.startsWith('contr-') || labelLower.includes('contract')) return 'Contract';
  if (idLower.startsWith('viol-') || labelLower.includes('violation')) return 'Violation';
  if (idLower.startsWith('act-') || labelLower.includes('action')) return 'Action';
  if (labelLower.includes('finding')) return 'Finding';

  return 'Entity';
}

export function toElements({
  nodes,
  edges,
  pathNodeIds = [],
  revealedSteps,
  activeStepSeq,
  showAll: _showAll = true,
  maxNodes = 500,
  maxEdges = 1500,
}: ToElementsOptions): { elements: ElementsDefinition; truncated: boolean } {
  const pathNodeSet = new Set(pathNodeIds);

  // If steps are given and not showAll, restrict revealed path steps
  const activeStep = revealedSteps?.find((s) => s.seq === activeStepSeq);

  // Apply node limits
  const isTruncated = nodes.length > maxNodes || edges.length > maxEdges;
  const slicedNodes = nodes.slice(0, maxNodes);
  const validNodeIds = new Set(slicedNodes.map((n) => n.id));

  // Filter edges to only connect present nodes
  const slicedEdges = edges
    .filter((e) => validNodeIds.has(e.src) && validNodeIds.has(e.dst))
    .slice(0, maxEdges);

  const cyNodes = slicedNodes.map((node) => {
    const nodeType = inferNodeType(node);
    const isOnPath = pathNodeSet.has(node.id);
    const isContext = Boolean(node.context);
    const isSuperseded =
      node.props?.status === 'superseded' ||
      node.props?.superseded === true;

    let displayLabel = node.label || node.id;
    if (nodeType === 'Violation' && !displayLabel.startsWith('x ')) {
      displayLabel = `x ${displayLabel}`;
    }

    const classes = [
      nodeType.toLowerCase(),
      isOnPath ? 'on-path' : '',
      isContext ? 'context' : '',
      isSuperseded ? 'superseded' : '',
    ]
      .filter(Boolean)
      .join(' ');

    return {
      data: {
        id: node.id,
        label: displayLabel,
        type: nodeType,
        status: node.props?.status,
        on_path: isOnPath,
        context: isContext,
        ...node.props,
      },
      classes,
    };
  });

  const cyEdges = slicedEdges.map((edge, index) => {
    const isOnPath = Boolean(edge.on_path);
    const isRejected =
      edge.rel === 'REJECTED' || edge.rel === 'rejected' || edge.rel.toLowerCase().includes('reject');

    const isActiveStep =
      Boolean(activeStep && (
        (activeStep.from === edge.src && activeStep.to === edge.dst) ||
        (activeStep.from === edge.dst && activeStep.to === edge.src)
      ));

    const classes = [
      isOnPath ? 'on-path' : '',
      isRejected ? 'rejected' : '',
      isActiveStep ? 'active-step' : '',
    ]
      .filter(Boolean)
      .join(' ');

    return {
      data: {
        id: edge.id || `e_${edge.src}_${edge.dst}_${index}`,
        source: edge.src,
        target: edge.dst,
        rel: edge.rel,
        label: edge.rel,
        on_path: isOnPath,
      },
      classes,
    };
  });

  return {
    elements: {
      nodes: cyNodes,
      edges: cyEdges,
    },
    truncated: isTruncated,
  };
}
