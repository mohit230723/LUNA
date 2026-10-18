import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { getApi } from '../../api';
import type { ForgeSkillSummary } from '../../api/contract';
import { ReviewQueue } from './ReviewQueue';
import { SkillUpload } from './SkillUpload';
import { SkillDetail } from './SkillDetail';
import './forge.css';

const ALL = 'all';
const uniq = (xs: string[]) => [...new Set(xs)].sort((a, b) => a.localeCompare(b));

interface FilterProps {
  id: string;
  label: string;
  value: string;
  options: string[];
  onChange: (v: string) => void;
}

const Filter: React.FC<FilterProps> = ({ id, label, value, options, onChange }) => (
  <div className="forge-field">
    <label htmlFor={id}>{label}</label>
    <select id={id} value={value} onChange={(e) => onChange(e.target.value)}>
      <option value={ALL}>All</option>
      {options.map((o) => (
        <option key={o} value={o}>
          {o}
        </option>
      ))}
    </select>
  </div>
);

export const SkillsTab: React.FC = () => {
  const [skills, setSkills] = useState<ForgeSkillSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState(ALL);
  const [capability, setCapability] = useState(ALL);
  const [technology, setTechnology] = useState(ALL);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const mounted = useRef(true);

  const load = useCallback(async () => {
    try {
      const rows = await getApi().forgeSkills();
      if (!mounted.current) return;
      setSkills(rows);
      setError(null);
    } catch (e) {
      if (mounted.current) setError(e instanceof Error ? e.message : 'Could not load skills.');
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    load();
    return () => {
      mounted.current = false;
    };
  }, [load]);

  const rows = useMemo(() => skills ?? [], [skills]);
  const statuses = useMemo(() => uniq(rows.map((s) => s.status)), [rows]);
  const capabilities = useMemo(() => uniq(rows.flatMap((s) => s.capabilities)), [rows]);
  const technologies = useMemo(() => uniq(rows.flatMap((s) => s.technologies)), [rows]);
  const visible = rows.filter(
    (s) =>
      (status === ALL || s.status === status) &&
      (capability === ALL || s.capabilities.includes(capability)) &&
      (technology === ALL || s.technologies.includes(technology))
  );

  const approve = async (id: string) => {
    await getApi().approveForgeSkill(id);
    await load();
  };
  const reject = async (id: string) => {
    await getApi().rejectForgeSkill(id);
    await load();
  };

  return (
    <div className="forge-agents forge-skills">
      <div className="forge-col">
        <SkillUpload onChanged={load} />
        <ReviewQueue skills={rows} onApprove={approve} onReject={reject} />
      </div>
      <div className="forge-col">
        <section className="forge-panel" aria-labelledby="forge-skills-title">
          <h2 className="forge-panel-title" id="forge-skills-title">
            Skill library
          </h2>
          <div className="forge-filters">
            <Filter id="forge-filter-status" label="Status" value={status} options={statuses} onChange={setStatus} />
            <Filter
              id="forge-filter-capability"
              label="Capability"
              value={capability}
              options={capabilities}
              onChange={setCapability}
            />
            <Filter
              id="forge-filter-technology"
              label="Technology"
              value={technology}
              options={technologies}
              onChange={setTechnology}
            />
          </div>
          {error && (
            <p className="forge-error" role="alert">
              {error}{' '}
              <button type="button" className="forge-btn" onClick={load}>
                Retry
              </button>
            </p>
          )}
          {skills === null && !error ? (
            <p className="forge-muted">Loading skills…</p>
          ) : (
            <div className="forge-table-wrap">
              <table className="forge-table" aria-label="Skills">
                <thead>
                  <tr>
                    <th scope="col">Skill</th>
                    <th scope="col">Status</th>
                    <th scope="col">Source</th>
                    <th scope="col">Capabilities</th>
                    <th scope="col">Technologies</th>
                  </tr>
                </thead>
                <tbody>
                  {visible.map((s) => (
                    <tr key={s.id} className={s.id === selectedId ? 'is-selected' : undefined}>
                      <th scope="row">
                        <button
                          type="button"
                          className="forge-task-select"
                          aria-pressed={s.id === selectedId}
                          onClick={() => setSelectedId(s.id)}
                        >
                          {s.name}
                        </button>
                      </th>
                      <td>{s.status.replace('_', ' ')}</td>
                      <td>{s.source}</td>
                      <td>{s.capabilities.join(', ')}</td>
                      <td>{s.technologies.join(', ')}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {visible.length === 0 && skills !== null && <p className="forge-muted">No skills match these filters.</p>}
            </div>
          )}
        </section>
        {selectedId && <SkillDetail skillId={selectedId} onClose={() => setSelectedId(null)} />}
      </div>
    </div>
  );
};

export default SkillsTab;
