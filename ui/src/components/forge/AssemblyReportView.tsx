import React from 'react';
import type { ForgeReport } from '../../api/contract';
import { asString } from './format';
import './forge.css';

export const AssemblyReportView: React.FC<{ report: ForgeReport }> = ({ report }) => {
  const overlaps = Object.entries(report.overlaps ?? {});
  const gaps = report.gaps ?? [];
  const missing = report.missing ?? [];
  return (
    <section className="forge-report" aria-labelledby="forge-report-title">
      <div className="forge-run-head">
        <h3 id="forge-report-title" className="forge-panel-title">
          Assembly report
        </h3>
        <span className="forge-status-label">{report.status}</span>
      </div>
      <p>{report.summary}</p>
      {missing.length > 0 && (
        <>
          <p className="forge-muted">Missing tasks</p>
          <ul>
            {missing.map((m) => (
              <li key={m} className="forge-file">
                {m}
              </li>
            ))}
          </ul>
        </>
      )}
      {overlaps.length > 0 && (
        <>
          <p className="forge-muted">Files touched by more than one task</p>
          <ul>
            {overlaps.map(([file, owners]) => (
              <li key={file}>
                <span className="forge-file">{file}</span> · {owners.join(', ')}
              </li>
            ))}
          </ul>
        </>
      )}
      {gaps.length > 0 && (
        <>
          <p className="forge-muted">Gaps</p>
          <ul>
            {gaps.map((g, i) => (
              <li key={i}>
                {asString(g.task_id)} · {asString(g.kind) || 'gap'}
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
};

export default AssemblyReportView;
