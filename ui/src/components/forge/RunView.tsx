import React from 'react';
import type { ForgeRunDetail } from '../../api/contract';
import { ForgeDag } from './ForgeDag';
import { TaskCard } from './TaskCard';
import { AssemblyReportView } from './AssemblyReportView';
import { asString } from './format';
import './forge.css';

export interface RunViewProps {
  run: ForgeRunDetail;
  now: number;
  selectedTaskId: string | null;
  onSelectTask: (taskId: string) => void;
}

export const RunView: React.FC<RunViewProps> = ({ run, now, selectedTaskId, onSelectTask }) => {
  const tasks = [...run.tasks].sort((a, b) => a.wave - b.wave);
  // The assembly report is the source of truth for completion (ruling 9).
  const status = run.report ? run.report.status : asString(run.run.status) || 'running';
  return (
    <section className="forge-panel" aria-labelledby="forge-run-title">
      <div className="forge-run-head">
        <h2 id="forge-run-title" className="forge-run-prompt">
          {asString(run.run.prompt) || run.run.run_id}
        </h2>
        <span className="forge-status-label">Run {status}</span>
      </div>
      <ForgeDag tasks={tasks} selectedTaskId={selectedTaskId} onSelect={onSelectTask} />
      <div className="forge-cards">
        {tasks.map((t) => (
          <TaskCard
            key={t.task_id}
            task={t}
            now={now}
            selected={t.task_id === selectedTaskId}
            onSelect={onSelectTask}
          />
        ))}
      </div>
      {run.report && <AssemblyReportView report={run.report} />}
    </section>
  );
};

export default RunView;
