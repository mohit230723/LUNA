import React, { useState } from 'react';
import type { ForgeSkillSummary } from '../../api/contract';
import './forge.css';

export interface ReviewQueueProps {
  skills: ForgeSkillSummary[];
  onApprove: (id: string) => Promise<void>;
  onReject: (id: string) => Promise<void>;
}

export const ReviewQueue: React.FC<ReviewQueueProps> = ({ skills, onApprove, onReject }) => {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pending = skills.filter((s) => s.status === 'pending_review');

  const act = async (id: string, fn: (id: string) => Promise<void>) => {
    setBusy(id);
    setError(null);
    try {
      await fn(id);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'The action failed.');
    } finally {
      setBusy(null);
    }
  };

  return (
    <section className="forge-panel" aria-labelledby="forge-review-title">
      <h2 className="forge-panel-title" id="forge-review-title">
        Review queue
      </h2>
      {error && (
        <p className="forge-error" role="alert">
          {error}
        </p>
      )}
      {pending.length === 0 ? (
        <p className="forge-muted">No skills awaiting review.</p>
      ) : (
        <ul className="forge-list">
          {pending.map((s) => (
            <li key={s.id} className="forge-agent">
              <span>
                <span className="forge-agent-name">{s.name}</span>
                {s.warnings_count > 0 && <span className="forge-muted"> · {s.warnings_count} warning(s)</span>}
              </span>
              <span className="forge-actions">
                <button
                  type="button"
                  className="forge-btn"
                  disabled={busy === s.id}
                  aria-label={`Approve ${s.name}`}
                  onClick={() => act(s.id, onApprove)}
                >
                  Approve
                </button>
                <button
                  type="button"
                  className="forge-btn"
                  disabled={busy === s.id}
                  aria-label={`Reject ${s.name}`}
                  onClick={() => act(s.id, onReject)}
                >
                  Reject
                </button>
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
};

export default ReviewQueue;
