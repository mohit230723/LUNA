import React from 'react';
import { X } from 'lucide-react';
import { IconButton } from '../ui/IconButton';
import { GhostButton } from '../ui/GhostButton';
import { Badge } from '../ui/Badge';
import type { TraceNode, TraceStep, FindingInfo } from '../../api/contract';
import styles from './NodeDetail.module.css';

export interface NodeDetailProps {
  node: TraceNode | null;
  steps?: TraceStep[];
  findings?: FindingInfo[];
  onClose: () => void;
  onWhy?: (target: string) => void;
  onExpand?: (cid: string) => void;
}

export const NodeDetail: React.FC<NodeDetailProps> = ({
  node,
  steps = [],
  findings = [],
  onClose,
  onWhy,
  onExpand,
}) => {
  if (!node) return null;

  const nodeType = (node.props?.type as string) || (node.id.startsWith('cust-') ? 'Customer' : 'Entity');

  // Filter steps that touch this node
  const touchedSteps = steps.filter((s) => s.from === node.id || s.to === node.id);

  // Filter findings about this node
  const relatedFindings = findings.filter(
    (f) => f.subject === node.id || f.evidence_cids?.includes(node.id)
  );

  // Check if contract
  const isContract = nodeType.toLowerCase() === 'contract';

  return (
    <aside className={styles.container} aria-label={`Details for node ${node.id}`}>
      {/* Header */}
      <div className={styles.header}>
        <div className={styles.titleArea}>
          <span className={styles.nodeType}>{nodeType}</span>
          <span className={styles.nodeId}>{node.id}</span>
        </div>
        <IconButton aria-label="Close node detail" onClick={onClose}>
          <X size={16} strokeWidth={1.5} />
        </IconButton>
      </div>

      <div className={styles.body}>
        {/* Properties Table */}
        <div className={styles.section}>
          <div className={styles.sectionTitle}>PROPERTIES</div>
          <table className={styles.propTable}>
            <tbody>
              <tr className={styles.propRow}>
                <td className={styles.propKey}>label</td>
                <td className={styles.propVal}>{node.label}</td>
              </tr>
              {Object.entries(node.props || {}).map(([k, v]) => {
                if (k === 'type') return null;
                const displayVal = typeof v === 'object' ? JSON.stringify(v) : String(v);
                return (
                  <tr key={k} className={styles.propRow}>
                    <td className={styles.propKey}>{k}</td>
                    <td className={styles.propVal}>{displayVal}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Contract-specific details */}
        {isContract && (
          <div className={styles.section}>
            <div className={styles.sectionTitle}>CONTRACT DETAILS</div>
            <table className={styles.propTable}>
              <tbody>
                {Boolean(node.props?.provider) && (
                  <tr className={styles.propRow}>
                    <td className={styles.propKey}>provider</td>
                    <td className={styles.propVal}>{String(node.props?.provider)}</td>
                  </tr>
                )}
                {Boolean(node.props?.consumer) && (
                  <tr className={styles.propRow}>
                    <td className={styles.propKey}>consumer</td>
                    <td className={styles.propVal}>{String(node.props?.consumer)}</td>
                  </tr>
                )}
                {Boolean(node.props?.artifacts) && (
                  <tr className={styles.propRow}>
                    <td className={styles.propKey}>artifacts</td>
                    <td className={styles.propVal}>
                      {Array.isArray(node.props?.artifacts)
                        ? node.props.artifacts.join(', ')
                        : String(node.props?.artifacts)}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* Touched By */}
        {touchedSteps.length > 0 && (
          <div className={styles.section}>
            <div className={styles.sectionTitle}>TOUCHED BY ({touchedSteps.length})</div>
            {touchedSteps.map((s) => (
              <div key={s.seq} className={styles.touchedItem}>
                <div>Step {s.seq}: -[{s.rel}]-</div>
                <div>{s.tool || 'graph traversal'} · {s.agent_id || 'orchestrator'}</div>
              </div>
            ))}
          </div>
        )}

        {/* Findings */}
        {relatedFindings.length > 0 && (
          <div className={styles.section}>
            <div className={styles.sectionTitle}>FINDINGS ({relatedFindings.length})</div>
            {relatedFindings.map((f) => (
              <div key={f.id} className={styles.findingItem}>
                <div className={styles.findingHeader}>
                  <Badge size="compact">
                    {f.verdict === 'suspicious' ? 'SUSPICIOUS' : 'BENIGN'}
                  </Badge>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>
                    {(f.confidence * 100).toFixed(0)}%
                  </span>
                </div>
                <div style={{ fontSize: 13, color: 'var(--color-smoke)' }}>
                  Skill: {f.skill_id}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Action Buttons */}
        <div className={styles.actionsRow}>
          {onWhy && (
            <GhostButton onClick={() => onWhy(node.id)}>
              WHY
            </GhostButton>
          )}
          {onExpand && (
            <GhostButton onClick={() => onExpand(node.id)}>
              EXPAND NEIGHBORS
            </GhostButton>
          )}
        </div>
      </div>
    </aside>
  );
};
