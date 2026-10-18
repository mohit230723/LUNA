import React, { useEffect, useState, useMemo, useRef } from 'react';
import cytoscape, { Core } from 'cytoscape';
import dagre from 'cytoscape-dagre';
import { Lock, Plus, Minus, Maximize2 } from 'lucide-react';
import { PageShell } from '../components/layout/PageShell';
import { Badge } from '../components/ui/Badge';
import { GhostButton } from '../components/ui/GhostButton';
import { IconButton } from '../components/ui/IconButton';
import { Drawer } from '../components/ui/Drawer';
import { Tabs } from '../components/ui/Tabs';
import { ErrorState } from '../components/ui/ErrorState';
import { cytoscapeStyles } from '../components/graph/graphStyle';
import { getApi } from '../api';
import type { SkillInfo, GraphData, Pack } from '../api/contract';
import styles from './SkillAtlas.module.css';

try {
  cytoscape.use(dagre);
} catch {
  // Already registered
}

export const SkillAtlas: React.FC = () => {
  const [pack, setPack] = useState<'all' | Pack>('all');
  const [search, setSearch] = useState('');
  const [view, setView] = useState<'list' | 'graph'>('list');
  const [skills, setSkills] = useState<SkillInfo[]>([]);
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedSkill, setSelectedSkill] = useState<SkillInfo | null>(null);
  const [promptOpen, setPromptOpen] = useState(false);

  const cyContainerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);

  useEffect(() => {
    document.title = 'Skill Atlas · LUNA OS';
  }, []);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const api = getApi();
      const [skillsRes, graphRes] = await Promise.all([
        api.getAtlasSkills(pack === 'all' ? undefined : pack),
        api.getAtlasGraph(),
      ]);
      setSkills(skillsRes);
      setGraphData(graphRes);
    } catch {
      setError('Could not load the atlas.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [pack]);

  // Filter skills by search query
  const filteredSkills = useMemo(() => {
    if (!search.trim()) return skills;
    const q = search.toLowerCase();
    return skills.filter(
      (s) =>
        s.name.toLowerCase().includes(q) ||
        s.id.toLowerCase().includes(q) ||
        s.capabilities.some((c) => c.toLowerCase().includes(q)) ||
        s.technologies.some((t) => t.toLowerCase().includes(q))
    );
  }, [skills, search]);

  // Setup Graph view
  useEffect(() => {
    if (view !== 'graph' || !cyContainerRef.current || !graphData) return;

    // Filter nodes based on selected pack if needed
    const elements = {
      nodes: graphData.nodes.map((n) => ({
        data: {
          id: n.id,
          label: n.label,
          type: (n.props['type'] as string) || (n.id.startsWith('pack') ? 'Component' : 'SkillRef'),
        },
      })),
      edges: graphData.edges.map((e) => ({
        data: {
          id: e.id,
          source: e.src,
          target: e.dst,
          rel: e.rel,
        },
      })),
    };

    const cy = cytoscape({
      container: cyContainerRef.current,
      elements,
      style: cytoscapeStyles,
      layout: {
        name: 'dagre',
        rankDir: 'TB',
        nodeSep: 40,
        rankSep: 60,
        padding: 30,
      } as cytoscape.LayoutOptions,
      boxSelectionEnabled: false,
    });

    cyRef.current = cy;
    cy.fit(undefined, 30);

    // Node click to open drawer
    cy.on('tap', 'node', (evt) => {
      const node = evt.target;
      const skillId = node.id();
      const match = skills.find((s) => s.id === skillId);
      if (match) {
        setSelectedSkill(match);
      }
    });

    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  }, [view, graphData, skills]);

  const handleZoomIn = () => {
    if (cyRef.current) {
      cyRef.current.zoom(cyRef.current.zoom() * 1.2);
    }
  };

  const handleZoomOut = () => {
    if (cyRef.current) {
      cyRef.current.zoom(cyRef.current.zoom() * 0.8);
    }
  };

  const handleFit = () => {
    if (cyRef.current) {
      cyRef.current.fit(undefined, 30);
    }
  };

  return (
    <PageShell>
      <div className={styles.container}>
        {/* Header */}
        <div className={styles.header}>
          <span className={styles.label}>SKILL ATLAS</span>
          <h1 className={styles.heading}>Every skill the orchestrator can choose.</h1>
          <p className={styles.subheadline}>
            Scores are track records that update after approved runs.
          </p>
        </div>

        {/* Toolbar */}
        <div className={styles.toolbar}>
          <div className={styles.toolbarLeft}>
            <Tabs
              activeTab={pack}
              onChange={(tab) => setPack(tab as 'all' | Pack)}
              tabs={[
                { id: 'all', label: 'ALL' },
                { id: 'investigate', label: 'INVESTIGATE' },
                { id: 'build', label: 'BUILD' },
              ]}
            />
            <input
              type="text"
              className={styles.searchInput}
              placeholder="Search skills, technologies, capabilities"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              aria-label="Search skills, technologies, capabilities"
            />
          </div>

          <div className={styles.toolbarRight}>
            <Tabs
              activeTab={view}
              onChange={(v) => setView(v as 'list' | 'graph')}
              tabs={[
                { id: 'list', label: 'LIST' },
                { id: 'graph', label: 'GRAPH' },
              ]}
            />
            <span className={styles.statusLine}>{filteredSkills.length} skills</span>
          </div>
        </div>

        {/* Content States */}
        {loading ? (
          <div>
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className={styles.skeletonRow}>
                <div className={styles.skeletonBar} />
              </div>
            ))}
          </div>
        ) : error ? (
          <ErrorState
            title="Could not load the atlas."
            message="An unexpected error occurred while communicating with the atlas API."
            action={<GhostButton onClick={loadData}>RETRY</GhostButton>}
          />
        ) : filteredSkills.length === 0 ? (
          <div style={{ padding: '60px 0', textAlign: 'center', color: 'var(--color-smoke)' }}>
            No skills match.
          </div>
        ) : view === 'list' ? (
          <table className={styles.table}>
            <thead>
              <tr>
                <th className={styles.th}>SKILL</th>
                <th className={styles.th}>PACK</th>
                <th className={styles.th}>CAPABILITIES</th>
                <th className={styles.th}>TECHNOLOGIES</th>
                <th className={styles.th}>REQUIRES</th>
                <th className={styles.th}>SCORE & RUNS</th>
                <th className={styles.th}>STATUS</th>
              </tr>
            </thead>
            <tbody>
              {filteredSkills.map((skill) => (
                <tr
                  key={skill.id}
                  className={styles.row}
                  onClick={() => {
                    setSelectedSkill(skill);
                    setPromptOpen(false);
                  }}
                  tabIndex={0}
                  role="button"
                  aria-label={`View skill ${skill.name}`}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      setSelectedSkill(skill);
                      setPromptOpen(false);
                    }
                  }}
                >
                  <td className={styles.td}>
                    <div className={styles.skillInfo}>
                      <span className={styles.skillName}>{skill.name}</span>
                      <span className={styles.skillId}>{skill.id}</span>
                    </div>
                  </td>
                  <td className={styles.td}>
                    <Badge size="compact">{skill.pack.toUpperCase()}</Badge>
                  </td>
                  <td className={styles.td}>
                    <div className={styles.chips}>
                      {skill.capabilities.map((c) => (
                        <span key={c} className={styles.chip}>
                          {c}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className={styles.td}>
                    <div className={styles.chips}>
                      {skill.technologies.map((t) => (
                        <span key={t} className={styles.chip}>
                          {t}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className={styles.td}>
                    <span className={styles.requires}>
                      {skill.requires.length > 0 ? skill.requires.join(', ') : '—'}
                    </span>
                  </td>
                  <td className={styles.td}>
                    <div className={styles.scoreContainer}>
                      <div className={styles.scoreRow}>
                        <div className={styles.scoreBar} aria-label={`Score: ${skill.score}`}>
                          <div
                            className={styles.scoreFill}
                            style={{ flex: skill.score }}
                          />
                          <div
                            className={styles.scoreEmpty}
                            style={{ flex: 1 - skill.score }}
                          />
                        </div>
                        <span className={styles.scoreNum}>{skill.score.toFixed(2)}</span>
                      </div>
                      <span className={styles.runsText}>{skill.runs} runs</span>
                    </div>
                  </td>
                  <td className={styles.td}>
                    {skill.restricted ? (
                      <Badge size="compact">
                        <Lock size={12} strokeWidth={1.5} style={{ marginRight: 4 }} />
                        RESTRICTED
                      </Badge>
                    ) : (
                      <span className={styles.availableText}>AVAILABLE</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className={styles.graphContainer}>
            <div className={styles.graphControls}>
              <IconButton aria-label="Zoom in" onClick={handleZoomIn}>
                <Plus size={16} strokeWidth={1.5} />
              </IconButton>
              <IconButton aria-label="Zoom out" onClick={handleZoomOut}>
                <Minus size={16} strokeWidth={1.5} />
              </IconButton>
              <IconButton aria-label="Fit graph to view" onClick={handleFit}>
                <Maximize2 size={16} strokeWidth={1.5} />
              </IconButton>
            </div>

            <div className={styles.legendCard}>
              <span className={styles.legendTitle}>LEGEND</span>
              <div className={styles.legendItem}>
                <div className={styles.legendDot} style={{ backgroundColor: 'var(--color-card-slate)' }} />
                <span>Pack / Component</span>
              </div>
              <div className={styles.legendItem}>
                <div className={styles.legendDot} style={{ backgroundColor: 'var(--color-iron)' }} />
                <span>Skill</span>
              </div>
            </div>

            <div ref={cyContainerRef} className={styles.graphCanvas} />
          </div>
        )}

        {/* Skill Detail Drawer */}
        <Drawer
          isOpen={!!selectedSkill}
          onClose={() => setSelectedSkill(null)}
          title={selectedSkill ? selectedSkill.name : ''}
          width="440px"
        >
          {selectedSkill && (
            <div className={styles.drawerBody}>
              <div>
                <span className={styles.drawerSectionTitle}>DESCRIPTION</span>
                <p className={styles.drawerDesc}>{selectedSkill.description}</p>
              </div>

              {selectedSkill.restricted && (
                <div className={styles.restrictedNotice}>
                  Restricted by policy. The orchestrator always rejects this skill and records why.
                </div>
              )}

              <div>
                <span className={styles.drawerSectionTitle}>TOOLS EXPOSED</span>
                <div className={styles.chips}>
                  {selectedSkill.tools.map((tool) => (
                    <span key={tool} className={styles.chip}>
                      {tool}
                    </span>
                  ))}
                </div>
              </div>

              <div>
                <span className={styles.drawerSectionTitle}>CAPABILITIES</span>
                <div className={styles.chips}>
                  {selectedSkill.capabilities.map((cap) => (
                    <span key={cap} className={styles.chip}>
                      {cap}
                    </span>
                  ))}
                </div>
              </div>

              <div>
                <span className={styles.drawerSectionTitle}>TECHNOLOGIES</span>
                <div className={styles.chips}>
                  {selectedSkill.technologies.map((tech) => (
                    <span key={tech} className={styles.chip}>
                      {tech}
                    </span>
                  ))}
                </div>
              </div>

              <div>
                <span className={styles.drawerSectionTitle}>REQUIRES</span>
                <span className={styles.requires}>
                  {selectedSkill.requires.length > 0 ? selectedSkill.requires.join(', ') : 'None'}
                </span>
              </div>

              <div>
                <span className={styles.drawerSectionTitle}>TRACK RECORD</span>
                <div className={styles.scoreContainer}>
                  <div className={styles.scoreRow}>
                    <div className={styles.scoreBar}>
                      <div
                        className={styles.scoreFill}
                        style={{ flex: selectedSkill.score }}
                      />
                      <div
                        className={styles.scoreEmpty}
                        style={{ flex: 1 - selectedSkill.score }}
                      />
                    </div>
                    <span className={styles.scoreNum}>{selectedSkill.score.toFixed(2)}</span>
                  </div>
                  <span className={styles.runsText}>{selectedSkill.runs} runs completed</span>
                </div>
              </div>

              <div>
                <span className={styles.drawerSectionTitle}>PROMPT FRAGMENT</span>
                <button
                  type="button"
                  className={styles.togglePromptBtn}
                  onClick={() => setPromptOpen(!promptOpen)}
                >
                  {promptOpen ? 'Hide prompt fragment' : 'Show prompt fragment'}
                </button>
                {promptOpen && (
                  <div className={styles.promptFragmentContainer}>
                    <pre className={styles.promptFragment}>
                      {selectedSkill.prompt_fragment}
                    </pre>
                  </div>
                )}
              </div>
            </div>
          )}
        </Drawer>
      </div>
    </PageShell>
  );
};
