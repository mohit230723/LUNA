import React, { useState } from 'react';
import { CustomerResolution, ProposedAction } from '../types';
import {
  Check,
  X,
  AlertTriangle,
  Scale,
  Award,
  ShieldCheck,
  Clock,
  Sparkles,
} from 'lucide-react';

interface DecisionPanelProps {
  runId: string;
  resolutions: Record<string, CustomerResolution>;
  actions: ProposedAction[];
  onApproveAction: (actionId: string) => Promise<void>;
  onRejectAction: (actionId: string, reason: string) => Promise<void>;
  selectedCustomerId?: string | null;
}

export const DecisionPanel: React.FC<DecisionPanelProps> = ({
  runId,
  resolutions,
  actions,
  onApproveAction,
  onRejectAction,
  selectedCustomerId,
}) => {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [rejectReason, setRejectReason] = useState('');
  const [showRejectInput, setShowRejectInput] = useState<string | null>(null);

  const resolutionKeys = Object.keys(resolutions);
  const pendingAction = actions.find((a) => a.status === 'PENDING') || actions[actions.length - 1];

  const handleApprove = async (actionId: string) => {
    setIsSubmitting(true);
    try {
      await onApproveAction(actionId);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleReject = async (actionId: string) => {
    setIsSubmitting(true);
    try {
      await onRejectAction(actionId, rejectReason || 'Rejected by investigator via console');
      setShowRejectInput(null);
      setRejectReason('');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        background: 'var(--bg-surface)',
        borderLeft: '1px solid var(--border-default)',
        overflowY: 'auto',
        padding: '16px',
        gap: '16px',
      }}
    >
      {/* Panel Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Scale size={16} color="var(--accent-blue)" />
          <span style={{ fontSize: '13px', fontWeight: 700, letterSpacing: '0.02em' }}>
            DECISION ENGINE & RESOLUTION
          </span>
        </div>
      </div>

      {/* Human Approval Gate (Interactive) */}
      <div
        className="obsidian-panel"
        style={{
          padding: '14px',
          borderColor: pendingAction?.status === 'PENDING' ? 'var(--badge-amber)' : 'var(--border-default)',
          background:
            pendingAction?.status === 'PENDING'
              ? 'rgba(210, 153, 34, 0.05)'
              : pendingAction?.status === 'APPROVED' || pendingAction?.status === 'EXECUTED'
              ? 'rgba(63, 185, 80, 0.05)'
              : 'var(--bg-panel)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
          <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
            Action Proposal Gate (HIL)
          </span>
          {pendingAction ? (
            <span
              className={`badge ${
                pendingAction.status === 'PENDING'
                  ? 'badge-amber'
                  : pendingAction.status === 'APPROVED' || pendingAction.status === 'EXECUTED'
                  ? 'badge-benign'
                  : 'badge-suspicious'
              }`}
            >
              {pendingAction.status === 'PENDING' ? <Clock size={10} /> : <ShieldCheck size={10} />}
              {pendingAction.status}
            </span>
          ) : (
            <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Idle</span>
          )}
        </div>

        {pendingAction ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ fontSize: '14px', fontWeight: 700, color: 'var(--accent-blue)' }}>
                  {pendingAction.action_type}
                </span>
                <span style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                  Target: <strong style={{ color: 'var(--text-primary)' }}>{pendingAction.customer_id}</strong>
                </span>
              </div>
              <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px', lineHeight: '1.4' }}>
                {pendingAction.reason}
              </p>
            </div>

            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                fontSize: '11px',
                fontFamily: 'var(--font-mono)',
                color: 'var(--text-muted)',
                padding: '6px 8px',
                background: 'var(--bg-canvas)',
                borderRadius: '4px',
                border: '1px solid var(--border-default)',
              }}
            >
              <span>Confidence: {(pendingAction.confidence * 100).toFixed(0)}%</span>
              <span>Action ID: {pendingAction.action_id.slice(0, 12)}</span>
            </div>

            {/* Action Buttons for PENDING */}
            {pendingAction.status === 'PENDING' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '4px' }}>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button
                    className="btn btn-approve"
                    onClick={() => handleApprove(pendingAction.action_id)}
                    disabled={isSubmitting}
                    style={{ flex: 1, padding: '8px 12px' }}
                  >
                    <Check size={14} />
                    Approve Action
                  </button>
                  <button
                    className="btn btn-reject"
                    onClick={() =>
                      setShowRejectInput(showRejectInput === pendingAction.action_id ? null : pendingAction.action_id)
                    }
                    disabled={isSubmitting}
                    style={{ flex: 1, padding: '8px 12px' }}
                  >
                    <X size={14} />
                    Reject
                  </button>
                </div>

                {showRejectInput === pendingAction.action_id && (
                  <div style={{ display: 'flex', gap: '6px', marginTop: '4px' }}>
                    <input
                      type="text"
                      placeholder="Reason for rejection..."
                      value={rejectReason}
                      onChange={(e) => setRejectReason(e.target.value)}
                      style={{
                        flex: 1,
                        background: 'var(--bg-canvas)',
                        border: '1px solid var(--border-danger)',
                        color: 'var(--text-primary)',
                        padding: '6px 8px',
                        fontSize: '11px',
                        borderRadius: '4px',
                        outline: 'none',
                      }}
                    />
                    <button
                      className="btn btn-reject"
                      onClick={() => handleReject(pendingAction.action_id)}
                      disabled={isSubmitting}
                      style={{ fontSize: '11px', padding: '6px 10px' }}
                    >
                      Confirm Reject
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* Execution Result Banner */}
            {pendingAction.execution_result && (
              <div
                style={{
                  padding: '8px 10px',
                  borderRadius: '6px',
                  background: 'rgba(63, 185, 80, 0.1)',
                  border: '1px solid rgba(63, 185, 80, 0.3)',
                  fontSize: '11px',
                  color: 'var(--verdict-benign)',
                  fontFamily: 'var(--font-mono)',
                }}
              >
                <div style={{ fontWeight: 700, marginBottom: '2px' }}>Execution Succeeded:</div>
                <div>Status: {pendingAction.execution_result.status || 'OK'}</div>
                {pendingAction.execution_result.timestamp && (
                  <div>Time: {pendingAction.execution_result.timestamp}</div>
                )}
              </div>
            )}
          </div>
        ) : (
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', textAlign: 'center', padding: '10px 0' }}>
            No action proposed yet. Waiting for investigation & resolution stages.
          </div>
        )}
      </div>

      {/* Side Resolution Breakdown */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
            Contested Customer Resolutions ({resolutionKeys.length})
          </span>
          <span style={{ fontSize: '10px', fontFamily: 'var(--font-mono)', color: 'var(--accent-cyan)' }}>
            S = 0.5*conf + 0.2*evid + 0.3*rep
          </span>
        </div>

        {resolutionKeys.length === 0 ? (
          <div
            style={{
              padding: '16px',
              border: '1px dashed var(--border-default)',
              borderRadius: '6px',
              textAlign: 'center',
              fontSize: '12px',
              color: 'var(--text-muted)',
            }}
          >
            No contested verdicts yet.
          </div>
        ) : (
          resolutionKeys.map((cid) => {
            const res = resolutions[cid];
            const isSelected = selectedCustomerId === cid;
            const scores = res.side_scores || {};
            const suspiciousScore = scores.suspicious?.total_score ?? 0;
            const benignScore = scores.benign?.total_score ?? 0;
            const isSuspiciousWinner = res.winning_side === 'suspicious';

            return (
              <div
                key={cid}
                className="obsidian-panel"
                style={{
                  padding: '12px',
                  border: '1px solid',
                  borderColor: isSelected ? 'var(--accent-blue)' : 'var(--border-default)',
                  background: isSelected ? 'rgba(88, 166, 255, 0.04)' : 'var(--bg-panel)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '8px',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: '12px', fontWeight: 700 }}>
                    {cid}
                  </span>
                  <span
                    className={`badge ${isSuspiciousWinner ? 'badge-suspicious' : 'badge-benign'}`}
                    style={{ fontSize: '10px' }}
                  >
                    <Award size={10} />
                    Winner: {res.winning_side}
                  </span>
                </div>

                {/* Score Comparison Bars */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginTop: '4px' }}>
                  {/* Suspicious Side */}
                  <div
                    style={{
                      padding: '8px',
                      background: 'rgba(248, 81, 73, 0.05)',
                      border: '1px solid',
                      borderColor: isSuspiciousWinner ? 'var(--verdict-suspicious)' : 'var(--border-subtle)',
                      borderRadius: '6px',
                      fontSize: '11px',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--verdict-suspicious)' }}>
                      <strong>Suspicious</strong>
                      <span style={{ fontFamily: 'var(--font-mono)' }}>{suspiciousScore.toFixed(3)}</span>
                    </div>
                    {scores.suspicious && (
                      <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginTop: '4px' }}>
                        <div>Conf: {(scores.suspicious.confidence * 100).toFixed(0)}%</div>
                        <div>Evid: {scores.suspicious.evidence_count}</div>
                        <div>Rep: {scores.suspicious.skill_score.toFixed(2)}</div>
                      </div>
                    )}
                  </div>

                  {/* Benign Side */}
                  <div
                    style={{
                      padding: '8px',
                      background: 'rgba(63, 185, 80, 0.05)',
                      border: '1px solid',
                      borderColor: !isSuspiciousWinner ? 'var(--verdict-benign)' : 'var(--border-subtle)',
                      borderRadius: '6px',
                      fontSize: '11px',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--verdict-benign)' }}>
                      <strong>Benign</strong>
                      <span style={{ fontFamily: 'var(--font-mono)' }}>{benignScore.toFixed(3)}</span>
                    </div>
                    {scores.benign && (
                      <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginTop: '4px' }}>
                        <div>Conf: {(scores.benign.confidence * 100).toFixed(0)}%</div>
                        <div>Evid: {scores.benign.evidence_count}</div>
                        <div>Rep: {scores.benign.skill_score.toFixed(2)}</div>
                      </div>
                    )}
                  </div>
                </div>

                {/* Superseded Notice */}
                {res.superseded_finding_ids?.length > 0 && (
                  <div style={{ fontSize: '10px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                    Superseded: {res.superseded_finding_ids.join(', ')}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
