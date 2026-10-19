import React from 'react';
import type { ForgeTask } from '../../api/contract';
import { asArray, asNumber, asString, countdown } from './format';
import './forge.css';

export interface TaskCardProps {
  task: ForgeTask;
  now: number;
  selected?: boolean;
  onSelect?: (taskId: string) => void;
}

interface Check {
  id: string;
  passed: boolean;
  detail: string;
}

function readChecks(result: Record<string, unknown> | null): Check[] {
  return asArray(result?.checks).flatMap((c) => {
    if (!c || typeof c !== 'object') return [];
    const o = c as Record<string, unknown>;
    return [{ id: asString(o.id), passed: o.passed === true, detail: asString(o.detail) || asString(o.note) }];
  });
}

export const TaskCard: React.FC<TaskCardProps> = ({ task, now, selected = false, onSelect }) => {
  const titleId = `forge-task-${task.task_id}-title`;
  // Session ids are long hex strings; show a short handle unless the agent gave itself a label.
  const rawClaimer = task.agent_label || task.claimed_by;
  const claimer = rawClaimer && !task.agent_label && rawClaimer.length > 14 ? `${rawClaimer.slice(0, 8)}…` : rawClaimer;
  const lease = task.status === 'claimed' ? countdown(task.lease_expires_at, now) : null;
  const result = task.result;
  const summary = asString(result?.summary);
  const files = asArray(result?.files).filter((f): f is string => typeof f === 'string');
  const checks = readChecks(result);
  const passed = checks.filter((c) => c.passed).length;

  return (
    <article
      className={`forge-task status-${task.status}${selected ? ' is-selected' : ''}`}
      aria-labelledby={titleId}
    >
      <div className="forge-task-head">
        <h3 id={titleId} className="forge-task-title">
          {onSelect ? (
            <button
              type="button"
              className="forge-task-select"
              aria-pressed={selected}
              onClick={() => onSelect(task.task_id)}
            >
              {task.title || task.task_id}
            </button>
          ) : (
            task.title || task.task_id
          )}
        </h3>
        <span className="forge-status-label">{task.status}</span>
      </div>

      <div className="forge-kv">
        <span>Skill</span>
        <span>{task.skill_id || 'none'}</span>
      </div>
      <div className="forge-kv">
        <span>Wave</span>
        <span>{task.wave}</span>
      </div>
      {claimer && (
        <div className="forge-kv">
          <span>Agent</span>
          <span>{claimer}</span>
        </div>
      )}
      {lease && (
        <div className="forge-kv">
          <span>Lease</span>
          <span aria-label={`Lease expires in ${lease}`}>{lease}</span>
        </div>
      )}

      {task.candidates.length > 0 && (
        <details>
          <summary>Why this skill?</summary>
          <ul>
            {task.candidates.map((c, i) => {
              const sid = asString(c.skill_id);
              const score = asNumber(c.score);
              const reason = asString(c.rejected_reason);
              const parts = [
                sid,
                score !== null ? `score ${score.toFixed(2)}` : '',
                reason ? `rejected: ${reason}` : sid === task.skill_id ? 'chosen' : '',
              ].filter(Boolean);
              return <li key={`${sid}-${i}`}>{parts.join(' · ')}</li>;
            })}
          </ul>
        </details>
      )}

      {result && (
        <div>
          {summary && <p>{summary}</p>}
          {files.length > 0 && (
            <ul aria-label="Files">
              {files.map((f) => (
                <li key={f} className="forge-file">
                  {f}
                </li>
              ))}
            </ul>
          )}
          {checks.length > 0 && (
            <>
              <p className="forge-muted">
                {passed}/{checks.length} checks passed
              </p>
              <ul aria-label="Checks">
                {checks.map((c) => (
                  <li key={c.id}>
                    {c.passed ? 'pass' : 'fail'} · {c.id}
                    {c.detail && ` · ${c.detail}`}
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
    </article>
  );
};

export default TaskCard;
