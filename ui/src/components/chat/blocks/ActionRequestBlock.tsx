import React, { useState } from 'react';
import { Button } from '../../ui/Button';
import { GhostButton } from '../../ui/GhostButton';
import { ApproverModal } from '../ApproverModal';
import type { ActionRequest, ActionResult } from '../../../api/contract';
import styles from './blocks.module.css';

export interface ActionRequestBlockProps {
  action: ActionRequest;
  onApprove: (approver: string) => Promise<ActionResult>;
  onReject: (approver: string, reason: string) => Promise<void>;
  onFocusNode?: (cid: string) => void;
}

export const ActionRequestBlock: React.FC<ActionRequestBlockProps> = ({
  action,
  onApprove,
  onReject,
  onFocusNode,
}) => {
  const [modalMode, setModalMode] = useState<'approve' | 'reject' | null>(null);
  const [loading, setLoading] = useState(false);

  const isPending = action.status === 'PENDING';
  const isRejected = action.status === 'REJECTED';

  const handleModalSubmit = async (val: string) => {
    setLoading(true);
    try {
      if (modalMode === 'approve') {
        await onApprove(val);
      } else if (modalMode === 'reject') {
        const approverName = localStorage.getItem('luna.approver') || 'User';
        await onReject(approverName, val);
      }
    } finally {
      setLoading(false);
      setModalMode(null);
    }
  };

  return (
    <div className={styles.actionCard}>
      <div className={styles.blockHeader}>
        <h4 className={styles.blockTitle}>
          {isPending ? 'APPROVAL NEEDED' : `ACTION ${action.status}`}
        </h4>
        {action.approver && (
          <span className={styles.monoMeta}>
            BY {action.approver.toUpperCase()}
          </span>
        )}
      </div>

      {/* Description of action */}
      {action.kind === 'flag_for_review' && action.targets && (
        <div>
          <p style={{ margin: '0 0 8px 0', fontSize: '14px', color: 'var(--color-chalk)' }}>
            Flag {action.targets.length} customer{action.targets.length > 1 ? 's' : ''} for suspicious fraud ring activity:
          </p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {action.targets.map((cid) => (
              <span
                key={cid}
                className={styles.cidChip}
                onClick={() => onFocusNode && onFocusNode(cid)}
                role="button"
                tabIndex={0}
              >
                {cid}
              </span>
            ))}
          </div>
        </div>
      )}

      {action.kind === 'run_build_check' && action.commands && (
        <div>
          <p style={{ margin: '0 0 8px 0', fontSize: '14px', color: 'var(--color-chalk)' }}>
            Execute verification build checks in project sandbox:
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {action.commands.map((cmd) => (
              <div
                key={cmd.cmd}
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: '12px',
                  backgroundColor: 'var(--color-obsidian)',
                  padding: '6px 10px',
                  borderRadius: 4,
                  color: 'var(--color-ash)',
                }}
              >
                $ {cmd.cmd} (timeout: {cmd.timeout_s}s)
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Rejection reason */}
      {isRejected && action.reason && (
        <div style={{ fontSize: '13px', color: 'var(--color-smoke)' }}>
          Reason: {action.reason}
        </div>
      )}

      {/* Execution Results */}
      {action.status === 'EXECUTED' && action.result && (
        <div
          style={{
            marginTop: 8,
            padding: '12px',
            backgroundColor: 'var(--color-obsidian)',
            border: '1px solid var(--color-graphite)',
            borderRadius: 'var(--radius-card)',
          }}
        >
          <span className={styles.monoMeta} style={{ display: 'block', marginBottom: 6 }}>
            EXECUTION RESULT
          </span>

          {action.result.metrics ? (
            <div style={{ display: 'flex', gap: 16, fontFamily: 'var(--font-mono)', fontSize: '12px' }}>
              <span>Precision: {action.result.metrics.precision.toFixed(3)}</span>
              <span>Recall: {action.result.metrics.recall.toFixed(3)}</span>
              <span>F1: {action.result.metrics.f1.toFixed(3)}</span>
            </div>
          ) : action.result.metrics === null ? (
            <span style={{ fontSize: '12px', color: 'var(--color-smoke)', fontFamily: 'var(--font-mono)' }}>
              metrics not available
            </span>
          ) : null}

          {action.result.commands && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 8 }}>
              {action.result.commands.map((c) => (
                <div key={c.cmd} style={{ fontFamily: 'var(--font-mono)', fontSize: '12px' }}>
                  {c.executed ? (
                    <div>
                      <span style={{ color: 'var(--color-chalk)' }}>$ {c.cmd}</span> (exit: {c.exit_code})
                      {c.log_tail && (
                        <pre style={{ margin: '4px 0 0 0', color: 'var(--color-smoke)', fontSize: '11px' }}>
                          {c.log_tail}
                        </pre>
                      )}
                    </div>
                  ) : (
                    <span style={{ color: 'var(--color-smoke)' }}>
                      NOT EXECUTED: {c.note || 'Skipped'}
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Action Buttons if Pending */}
      {isPending && (
        <div className={styles.actionButtonRow}>
          <Button disabled={loading} onClick={() => setModalMode('approve')}>
            APPROVE
          </Button>
          <GhostButton disabled={loading} onClick={() => setModalMode('reject')}>
            REJECT
          </GhostButton>
        </div>
      )}

      {/* Approver / Rejection modal */}
      {modalMode && (
        <ApproverModal
          isOpen={true}
          mode={modalMode}
          onClose={() => setModalMode(null)}
          onSubmit={handleModalSubmit}
        />
      )}
    </div>
  );
};
