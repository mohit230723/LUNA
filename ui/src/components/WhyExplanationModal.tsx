import React from 'react';
import { CustomerExplanation } from '../types';
import {
  X,
  ShieldAlert,
  CheckCircle2,
  HelpCircle,
  Share2,
  FileText,
  Layers,
  Sparkles,
} from 'lucide-react';

interface WhyExplanationModalProps {
  explanation: CustomerExplanation | null;
  isOpen: boolean;
  onClose: () => void;
  onHighlightSubgraph: (nodeIds: string[]) => void;
}

export const WhyExplanationModal: React.FC<WhyExplanationModalProps> = ({
  explanation,
  isOpen,
  onClose,
  onHighlightSubgraph,
}) => {
  if (!isOpen || !explanation) return null;

  const isSuspicious = explanation.winning_side === 'suspicious';
  const subgraphNodeIds = explanation.subgraph?.nodes?.map((n) => n.id) || [];

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(9, 13, 19, 0.8)',
        backdropFilter: 'blur(8px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 100,
        padding: '20px',
      }}
      onClick={onClose}
    >
      <div
        className="obsidian-panel"
        style={{
          width: '100%',
          maxWidth: '740px',
          maxHeight: '85vh',
          background: 'var(--bg-panel)',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: 'var(--shadow-md)',
          overflow: 'hidden',
          border: '1px solid var(--border-accent)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '14px 20px',
            borderBottom: '1px solid var(--border-default)',
            background: 'var(--bg-surface)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: '32px',
                height: '32px',
                borderRadius: '6px',
                background: isSuspicious ? 'rgba(248, 81, 73, 0.15)' : 'rgba(63, 185, 80, 0.15)',
                color: isSuspicious ? 'var(--verdict-suspicious)' : 'var(--verdict-benign)',
              }}
            >
              {isSuspicious ? <ShieldAlert size={18} /> : <CheckCircle2 size={18} />}
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '15px', fontWeight: 700 }}>
                  Why: Customer {explanation.customer_id}
                </span>
                <span
                  className={`badge ${isSuspicious ? 'badge-suspicious' : 'badge-benign'}`}
                >
                  {explanation.winning_side || 'Unresolved'}
                </span>
              </div>
              <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                Provenance & Multi-Agent Evidence Chain
              </span>
            </div>
          </div>

          <button
            onClick={onClose}
            className="btn"
            style={{ padding: '4px 8px', borderRadius: '4px' }}
          >
            <X size={16} />
          </button>
        </div>

        {/* Content Body */}
        <div
          style={{
            flex: 1,
            overflowY: 'auto',
            padding: '20px',
            display: 'flex',
            flexDirection: 'column',
            gap: '16px',
          }}
        >
          {/* Narrative Card */}
          <div
            style={{
              padding: '14px',
              borderRadius: '8px',
              background: 'var(--bg-canvas)',
              border: '1px solid var(--border-default)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '8px' }}>
              <FileText size={14} color="var(--accent-blue)" />
              <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                Investigative Narrative
              </span>
            </div>
            <p
              style={{
                fontSize: '13px',
                lineHeight: '1.6',
                color: 'var(--text-primary)',
                whiteSpace: 'pre-line',
              }}
            >
              {explanation.narrative}
            </p>
          </div>

          {/* Corroboration Breakdown */}
          {explanation.corroboration && (
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(3, 1fr)',
                gap: '10px',
                padding: '12px',
                borderRadius: '8px',
                background: 'var(--bg-surface)',
                border: '1px solid var(--border-default)',
              }}
            >
              <div>
                <span style={{ fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                  Corroborated Status
                </span>
                <div style={{ marginTop: '4px' }}>
                  <span
                    className={`badge ${
                      explanation.corroboration.corroborated ? 'badge-benign' : 'badge-amber'
                    }`}
                  >
                    {explanation.corroboration.corroborated ? 'Corroborated' : 'Uncorroborated'}
                  </span>
                </div>
              </div>

              <div>
                <span style={{ fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                  Distinct Skills
                </span>
                <div style={{ marginTop: '4px', fontSize: '12px', fontFamily: 'var(--font-mono)' }}>
                  {explanation.corroboration.distinct_skills?.join(', ') || 'None'}
                </div>
              </div>

              <div>
                <span style={{ fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                  Best Confidence
                </span>
                <div style={{ marginTop: '4px', fontSize: '13px', fontFamily: 'var(--font-mono)', fontWeight: 700 }}>
                  {(explanation.corroboration.best_confidence * 100).toFixed(0)}%
                </div>
              </div>
            </div>
          )}

          {/* Supporting Findings */}
          <div>
            <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
              Supporting Active Findings ({explanation.supporting_findings?.length || 0})
            </span>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginTop: '6px' }}>
              {(explanation.supporting_findings || []).map((f) => (
                <div
                  key={f.finding_id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '8px 12px',
                    borderRadius: '6px',
                    background: 'var(--bg-surface)',
                    border: '1px solid var(--border-default)',
                    fontSize: '12px',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span
                      className={`badge ${f.verdict === 'suspicious' ? 'badge-suspicious' : 'badge-benign'}`}
                      style={{ fontSize: '9px' }}
                    >
                      {f.verdict}
                    </span>
                    <span style={{ fontFamily: 'var(--font-mono)' }}>{f.finding_id}</span>
                    <span style={{ color: 'var(--text-muted)' }}>via {f.skill_id}</span>
                  </div>
                  <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-cyan)' }}>
                    Conf: {(f.confidence * 100).toFixed(0)}%
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Superseded Findings (if any) */}
          {(explanation.superseded_findings || []).length > 0 && (
            <div>
              <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                Superseded Contested Findings ({explanation.superseded_findings.length})
              </span>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginTop: '6px' }}>
                {explanation.superseded_findings.map((f) => (
                  <div
                    key={f.finding_id}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '8px 12px',
                      borderRadius: '6px',
                      background: 'rgba(139, 148, 158, 0.05)',
                      border: '1px solid var(--border-subtle)',
                      fontSize: '12px',
                      opacity: 0.6,
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span className="badge badge-superseded" style={{ fontSize: '9px' }}>
                        superseded
                      </span>
                      <span style={{ fontFamily: 'var(--font-mono)' }}>{f.finding_id}</span>
                      <span style={{ color: 'var(--text-muted)' }}>({f.verdict} / {f.skill_id})</span>
                    </div>
                    <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                      Conf: {(f.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Action Justification */}
          {explanation.action && (
            <div
              style={{
                padding: '12px',
                borderRadius: '8px',
                background: 'rgba(88, 166, 255, 0.05)',
                border: '1px solid var(--border-accent)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px' }}>
                <Sparkles size={14} color="var(--accent-blue)" />
                <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--accent-blue)', textTransform: 'uppercase' }}>
                  Action Justification
                </span>
              </div>
              <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary)' }}>
                {explanation.action.action_type} (Status: {explanation.action.status})
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                {explanation.action.reason}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '12px 20px',
            borderTop: '1px solid var(--border-default)',
            background: 'var(--bg-surface)',
          }}
        >
          <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
            Evidence Subgraph: {subgraphNodeIds.length} nodes
          </span>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              className="btn btn-primary"
              onClick={() => {
                onHighlightSubgraph(subgraphNodeIds);
                onClose();
              }}
              disabled={subgraphNodeIds.length === 0}
            >
              <Share2 size={13} />
              Highlight Evidence Subgraph
            </button>
            <button className="btn" onClick={onClose}>
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
