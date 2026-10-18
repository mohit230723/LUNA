import React from 'react';
import type { ForgeRunSummary } from '../../api/contract';
import './forge.css';

export interface RunListProps {
  runs: ForgeRunSummary[];
  selectedId: string | null;
  onSelect: (runId: string) => void;
}

export const RunList: React.FC<RunListProps> = ({ runs, selectedId, onSelect }) => {
  return (
    <section className="forge-panel" aria-labelledby="forge-runs-title">
      <h2 id="forge-runs-title" className="forge-panel-title">
        Build runs
      </h2>
      {runs.length === 0 ? (
        <p className="forge-muted">No runs yet. Ask a connected agent to build something.</p>
      ) : (
        <ul className="forge-list" aria-label="Build runs">
          {runs.map((r) => (
            <li key={r.run_id}>
              <button
                type="button"
                className="forge-run-btn"
                aria-current={r.run_id === selectedId ? 'true' : undefined}
                onClick={() => onSelect(r.run_id)}
              >
                {r.prompt || r.run_id}
                <span className="forge-run-meta">
                  {r.status} · {r.task_count} tasks
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
};

export default RunList;
