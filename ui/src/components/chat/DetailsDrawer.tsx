import React, { useState, useEffect } from 'react';
import { X, ChevronRight, ChevronDown } from 'lucide-react';
import { IconButton } from '../ui/IconButton';
import { Tabs } from '../ui/Tabs';
import { Badge } from '../ui/Badge';
import { getApi } from '../../api';
import type {
  SkillAssignment,
  AgentInfo,
  FindingInfo,
  WhyResponse,
  FileNode,
} from '../../api/contract';
import styles from './DetailsDrawer.module.css';

export interface DetailsDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  runId?: string;
  initialTab?: 'skills' | 'agents' | 'findings' | 'why' | 'files';
  whyTarget?: string;
  skillsData?: SkillAssignment[];
  agentsData?: AgentInfo[];
  findingsData?: FindingInfo[];
  filesData?: FileNode[];
  onFocusNode?: (cid: string) => void;
  onSelectFile?: (path: string) => void;
}

export const DetailsDrawer: React.FC<DetailsDrawerProps> = ({
  isOpen,
  onClose,
  runId,
  initialTab = 'skills',
  whyTarget,
  skillsData = [],
  agentsData = [],
  findingsData = [],
  filesData = [],
  onFocusNode,
  onSelectFile,
}) => {
  const [activeTab, setActiveTab] = useState<'skills' | 'agents' | 'findings' | 'why' | 'files'>(
    initialTab
  );
  const [currentTarget, setCurrentTarget] = useState<string>(whyTarget || '');
  const [whyData, setWhyData] = useState<WhyResponse | null>(null);
  const [findingFilter, setFindingFilter] = useState<'all' | 'active' | 'superseded'>('all');
  const [expandedAgent, setExpandedAgent] = useState<string | null>(null);

  useEffect(() => {
    setActiveTab(initialTab);
  }, [initialTab]);

  useEffect(() => {
    if (whyTarget) {
      setCurrentTarget(whyTarget);
    } else if (findingsData.length > 0 && !currentTarget) {
      const firstTarget = findingsData[0]?.subject;
      if (firstTarget) setCurrentTarget(firstTarget);
    }
  }, [whyTarget, findingsData]);

  // Load Why data
  useEffect(() => {
    if (!runId || !currentTarget) return;
    const loadWhy = async () => {
      try {
        const api = getApi();
        const data = await api.getWhy(runId, currentTarget);
        setWhyData(data);
      } catch {
        setWhyData(null);
      }
    };
    loadWhy();
  }, [runId, currentTarget]);

  if (!isOpen) return null;

  const filteredFindings = findingsData.filter((f) => {
    if (findingFilter === 'all') return true;
    return f.status === findingFilter;
  });

  return (
    <aside className={styles.container} aria-label="Run Details">
      <div className={styles.header}>
        <span className={styles.title}>RUN DETAILS</span>
        <IconButton aria-label="Close details drawer" onClick={onClose}>
          <X size={16} strokeWidth={1.5} />
        </IconButton>
      </div>

      <div className={styles.tabsRow}>
        <Tabs
          activeId={activeTab}
          onChange={(t) => setActiveTab(t as any)}
          tabs={[
            { id: 'skills', label: 'SKILLS' },
            { id: 'agents', label: 'AGENTS' },
            { id: 'findings', label: 'FINDINGS' },
            { id: 'why', label: 'WHY' },
            { id: 'files', label: 'FILES' },
          ]}
        />
      </div>

      <div className={styles.body}>
        {/* TAB: SKILLS */}
        {activeTab === 'skills' && (
          <div>
            <span className={styles.sectionTitle}>SKILL ASSIGNMENTS</span>
            {skillsData.length === 0 ? (
              <span style={{ fontSize: '13px', color: 'var(--color-smoke)' }}>
                No skills assigned
              </span>
            ) : (
              skillsData.map((s) => (
                <div
                  key={s.subject}
                  style={{
                    padding: '12px',
                    border: '1px solid var(--color-graphite)',
                    borderRadius: 'var(--radius-card)',
                    marginBottom: 10,
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: '12px', color: 'var(--color-chalk)' }}>
                      {s.subject}
                    </span>
                    <Badge size="compact">{s.backend.toUpperCase()}</Badge>
                  </div>
                  <div style={{ fontSize: '13px', color: 'var(--color-ash)' }}>
                    Chosen: <strong>{s.chosen}</strong>
                    {s.fit !== undefined && ` (Fit: ${s.fit.toFixed(2)})`}
                  </div>
                  {s.rejected.length > 0 && (
                    <div style={{ marginTop: 8, fontSize: '11px', color: 'var(--color-smoke)' }}>
                      Rejected: {s.rejected.map((r) => `${r.skill} (${r.reason})`).join(', ')}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        )}

        {/* TAB: AGENTS */}
        {activeTab === 'agents' && (
          <div>
            <span className={styles.sectionTitle}>SUB-AGENTS & TOOL LOGS</span>
            {agentsData.map((agent) => {
              const isExp = expandedAgent === agent.id;
              return (
                <div
                  key={agent.id}
                  style={{
                    border: '1px solid var(--color-graphite)',
                    borderRadius: 'var(--radius-card)',
                    marginBottom: 10,
                    overflow: 'hidden',
                  }}
                >
                  <div
                    style={{
                      padding: '10px 12px',
                      backgroundColor: 'var(--color-carbon)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      cursor: 'pointer',
                    }}
                    onClick={() => setExpandedAgent(isExp ? null : agent.id)}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      {isExp ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                      <span style={{ fontSize: '13px', color: 'var(--color-chalk)' }}>
                        {agent.skill}
                      </span>
                    </div>
                    <Badge size="compact">{agent.status.toUpperCase()}</Badge>
                  </div>

                  {isExp && (
                    <div style={{ padding: '12px', display: 'flex', flexDirection: 'column', gap: 6 }}>
                      <span style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--color-smoke)' }}>
                        Agent ID: {agent.id}
                      </span>
                      <span style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--color-smoke)' }}>
                        Tool calls: {agent.tool_calls}
                      </span>
                      {agent.hops_walked !== undefined && (
                        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--color-smoke)' }}>
                          Hops walked: {agent.hops_walked}
                        </span>
                      )}
                      {agent.files_written !== undefined && (
                        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--color-smoke)' }}>
                          Files written: {agent.files_written}
                        </span>
                      )}
                      {agent.reason && (
                        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--color-smoke)' }}>
                          Error: {agent.reason}
                        </span>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* TAB: FINDINGS */}
        {activeTab === 'findings' && (
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <span className={styles.sectionTitle}>FINDINGS</span>
              <div style={{ display: 'flex', gap: 6 }}>
                {(['all', 'active', 'superseded'] as const).map((filter) => (
                  <button
                    key={filter}
                    type="button"
                    style={{
                      background: findingFilter === filter ? 'var(--color-badge-bg)' : 'transparent',
                      border: '1px solid var(--color-graphite)',
                      borderRadius: 4,
                      color: findingFilter === filter ? 'var(--color-chalk)' : 'var(--color-smoke)',
                      fontSize: '11px',
                      fontFamily: 'var(--font-mono)',
                      padding: '2px 6px',
                      cursor: 'pointer',
                    }}
                    onClick={() => setFindingFilter(filter)}
                  >
                    {filter.toUpperCase()}
                  </button>
                ))}
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {filteredFindings.map((f) => (
                <div
                  key={f.id}
                  style={{
                    padding: '10px 12px',
                    border: '1px solid var(--color-graphite)',
                    borderRadius: 'var(--radius-card)',
                    opacity: f.status === 'superseded' ? 0.6 : 1,
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: '12px', color: 'var(--color-chalk)' }}>
                      {f.subject}
                    </span>
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--color-smoke)' }}>
                      {f.verdict.toUpperCase()} ({f.confidence.toFixed(2)})
                    </span>
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--color-ash)' }}>
                    Skill: {f.skill_id}
                  </div>
                  {f.status === 'superseded' && (
                    <div style={{ fontSize: '11px', color: 'var(--color-smoke)', textDecoration: 'line-through' }}>
                      SUPERSEDED
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* TAB: WHY */}
        {activeTab === 'why' && (
          <div>
            <span className={styles.sectionTitle}>WHY EXPLANATION</span>

            {/* Target selector if multiple */}
            {findingsData.length > 0 && (
              <div style={{ marginBottom: 12 }}>
                <select
                  value={currentTarget}
                  onChange={(e) => setCurrentTarget(e.target.value)}
                  style={{
                    width: '100%',
                    backgroundColor: 'var(--color-carbon)',
                    border: '1px solid var(--color-graphite)',
                    borderRadius: 'var(--radius-card)',
                    color: 'var(--color-chalk)',
                    padding: '8px 12px',
                    fontFamily: 'var(--font-mono)',
                    fontSize: '12px',
                    outline: 'none',
                  }}
                >
                  {Array.from(new Set(findingsData.map((f) => f.subject))).map((target) => (
                    <option key={target} value={target}>
                      {target}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {whyData ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                <div className={styles.whyNarrative}>{whyData.narrative}</div>

                {whyData.decision && (
                  <div className={styles.decisionBox}>
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--color-smoke)' }}>
                      DECISION {whyData.decision.id}
                    </span>
                    <span style={{ fontSize: '13px', color: 'var(--color-chalk)' }}>
                      Verdict: <strong>{whyData.decision.chosen_verdict}</strong>
                    </span>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 2, marginTop: 4 }}>
                      {Object.entries(whyData.decision.components).map(([k, v]) => (
                        <div
                          key={k}
                          style={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            fontFamily: 'var(--font-mono)',
                            fontSize: '11px',
                            color: 'var(--color-smoke)',
                          }}
                        >
                          <span>{k}:</span>
                          <span>{v.toFixed(2)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {whyData.chain_node_ids.length > 0 && (
                  <div>
                    <span className={styles.sectionTitle}>EVIDENCE CHAIN</span>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                      {whyData.chain_node_ids.map((id) => (
                        <span
                          key={id}
                          className={styles.toolCallItem}
                          style={{ cursor: 'pointer' }}
                          onClick={() => onFocusNode && onFocusNode(id)}
                        >
                          {id}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <span style={{ fontSize: '13px', color: 'var(--color-smoke)' }}>
                Select an evidence target above to inspect the decision.
              </span>
            )}
          </div>
        )}

        {/* TAB: FILES */}
        {activeTab === 'files' && (
          <div>
            <span className={styles.sectionTitle}>FILES</span>
            {filesData.length === 0 ? (
              <span style={{ fontSize: '13px', color: 'var(--color-smoke)' }}>
                No generated files for this run
              </span>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                {filesData.map((f) => (
                  <div
                    key={f.path}
                    style={{
                      fontFamily: 'var(--font-mono)',
                      fontSize: '12px',
                      color: 'var(--color-chalk)',
                      cursor: 'pointer',
                      padding: '4px 6px',
                      borderRadius: 4,
                    }}
                    onClick={() => onSelectFile && onSelectFile(f.path)}
                  >
                    {f.path}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </aside>
  );
};
