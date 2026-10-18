import React, { useState, useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { PageShell } from '../components/layout/PageShell';
import { Tabs } from '../components/ui/Tabs';
import { GhostButton } from '../components/ui/GhostButton';
import { Button } from '../components/ui/Button';
import { MiniGraph } from '../components/graph/MiniGraph';
import { toElements } from '../components/graph/toElements';
import { F1_TRACE, F1_BLOCKS } from '../api/mock/fixtures/f1_investigate';
import { F2_TRACE, F2_BLOCKS } from '../api/mock/fixtures/f2_build';
import type { TraceNode, TraceEdge } from '../api/contract';
import styles from './HowItWorks.module.css';

interface StageWalkthrough {
  title: string;
  description: string;
  whatGetsStored: string[];
  realValues: string[];
  nodeIds: string[];
}

export const HowItWorks: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'investigate' | 'build'>('investigate');
  const [currentStageIdx, setCurrentStageIdx] = useState(0);

  useEffect(() => {
    document.title = 'How it works · LUNA OS';
  }, []);

  // Keyboard arrow listeners for stepper
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
        setCurrentStageIdx((prev) => Math.min(5, prev + 1));
      } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
        setCurrentStageIdx((prev) => Math.max(0, prev - 1));
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Data from F1 Investigate fixture
  const investigateStages: StageWalkthrough[] = useMemo(() => {
    const routingBlock = F1_BLOCKS.find((b) => b.type === 'routing');
    const skillsBlock = F1_BLOCKS.find((b) => b.type === 'skills');
    const findingsBlock = F1_BLOCKS.find((b) => b.type === 'findings');

    const routingData = routingBlock?.type === 'routing' ? routingBlock.data : null;
    const assignments = skillsBlock?.type === 'skills' ? skillsBlock.data.assignments : [];
    const findings = findingsBlock?.type === 'findings' ? findingsBlock.data.items : [];

    return [
      {
        title: 'Route',
        description:
          'Decides which pack handles the prompt and assesses confidence. If intent is ambiguous, it stops to ask for clarification before creating run resources.',
        whatGetsStored: [
          'Run(id="run_f1", pack="investigate") -[:ROUTED_WITH]-> Intent(kind="fraud_investigation")',
        ],
        realValues: [
          `Pack: ${routingData?.pack.toUpperCase() || 'INVESTIGATE'}`,
          `Intent: ${routingData?.intent || 'fraud_investigation'}`,
          `Confidence: ${(routingData?.confidence || 0.96) * 100}% (${routingData?.backend || 'scripted'})`,
        ],
        nodeIds: ['cust-000'],
      },
      {
        title: 'Plan',
        description:
          'Writes the plan directly into the graph as connected subtasks. Subtasks define the graph traversal capabilities and boundaries.',
        whatGetsStored: [
          'Run -[:HAS_SUBTASK]-> Subtask(capability="connection_tracing")',
          'Run -[:HAS_SUBTASK]-> Subtask(capability="community_detection")',
        ],
        realValues: [
          'Subtask 1: Trace phone and bank account links from seed cust-000',
          'Subtask 2: Identify dense shared-attribute community clusters',
        ],
        nodeIds: ['cust-000', 'ph-ring-01'],
      },
      {
        title: 'Assign skills',
        description:
          'Queries the Skill Atlas graph for candidate skills. Evaluates capability fit and track record, permanently storing chosen and rejected candidates.',
        whatGetsStored: [
          'Decision(kind="skill_assignment") -[:CHOSE]-> SkillRef(id="connection-tracer")',
          'Decision -[:REJECTED {reason: "policy_restricted"}]-> SkillRef(id="bulk-linker")',
        ],
        realValues: assignments.map(
          (a) =>
            `${a.subject}: chose ${a.chosen} (fit: ${a.fit || 0.95}) · rejected ${a.rejected.map((r) => `${r.skill} [${r.reason}]`).join(', ')}`
        ),
        nodeIds: ['cust-000', 'ph-ring-01', 'cust-003'],
      },
      {
        title: 'Work',
        description:
          'Sub-agents run in parallel on isolated slices of the data graph. Each sub-agent calls only the scoped tools exposed by its assigned skill.',
        whatGetsStored: [
          'Agent -[:EXECUTED_STEP]-> TraversalStep(tool="trace_connections")',
          'Agent -[:TRAVERSED]-> Entity(Phone, BankAccount, Provider)',
        ],
        realValues: [
          'agent_tracer: walked 4 hops, 6 tool calls',
          'agent_linker: walked 2 hops, 3 tool calls',
        ],
        nodeIds: ['cust-000', 'ph-ring-01', 'cust-003', 'ba-ring-01', 'cust-005'],
      },
      {
        title: 'Verify',
        description:
          'Verifies that every cited piece of evidence exists in the agent slice and appeared in tool output. Resolves conflicting findings deterministically.',
        whatGetsStored: [
          'Finding(subject="cust-010", verdict="suspicious") -[:SUPERSEDED_BY]-> Finding(verdict="benign")',
          'Finding -[:CITED_EVIDENCE]-> Entity',
        ],
        realValues: [
          `Active findings: ${findings.filter((f) => f.status === 'active').length}`,
          `Superseded findings: ${findings.filter((f) => f.status === 'superseded').length} (cust-010 marked benign by community-analyzer)`,
        ],
        nodeIds: ['cust-000', 'ph-ring-01', 'cust-003', 'ba-ring-01', 'cust-005', 'claim-017', 'prov-ring'],
      },
      {
        title: 'Answer',
        description:
          'Composes the human-readable response with clickable citations. Any destructive or external actions are parked as approval-gated requests.',
        whatGetsStored: [
          'Answer -[:CITES]-> Entity',
          'ActionRequest(kind="flag_for_review", status="PENDING") -[:TARGETS]-> Customer',
        ],
        realValues: [
          'Action: Flag 3 customers (cust-000, cust-003, cust-005)',
          'Requires: Human approval before executing external flag update',
        ],
        nodeIds: ['cust-000', 'ph-ring-01', 'cust-003', 'ba-ring-01', 'cust-005', 'claim-017', 'prov-ring'],
      },
    ];
  }, []);

  // Data from F2 Build fixture
  const buildStages: StageWalkthrough[] = useMemo(() => {
    const skillsBlock = F2_BLOCKS.find((b) => b.type === 'skills');
    const filesBlock = F2_BLOCKS.find((b) => b.type === 'files');
    const assignments = skillsBlock?.type === 'skills' ? skillsBlock.data.assignments : [];
    const filesData = filesBlock?.type === 'files' ? filesBlock.data : null;

    return [
      {
        title: 'Route',
        description:
          'Identifies the task as a build specification, parsing required stack constraints (React, Vite, Express, Postgres).',
        whatGetsStored: [
          'Run(id="run_f2", pack="build") -[:ROUTED_WITH]-> Requirement(frontend="react+vite")',
        ],
        realValues: [
          'Pack: BUILD',
          'Requirements: frontend=react+vite, backend=express, database=postgres',
        ],
        nodeIds: ['req-frontend'],
      },
      {
        title: 'Plan',
        description:
          'Generates the blueprint graph: components, dependency relationships, and contracts (endpoints, tables, ports, env vars) that pieces must satisfy.',
        whatGetsStored: [
          'Component(name="api") -[:DEPENDS_ON]-> Component(name="database")',
          'Component(name="api") -[:DECLARES]-> Contract(kind="endpoint", key="GET /api/todos")',
        ],
        realValues: [
          'Components: database (postgres), api (express), web (react+vite), docs',
          'Contracts declared: 9 (endpoints, schema, port 3001, DATABASE_URL)',
        ],
        nodeIds: ['req-frontend', 'cmp-web', 'cmp-api', 'cmp-db'],
      },
      {
        title: 'Assign skills',
        description:
          'Matches blueprint components to specialized skills in the atlas. Rejects incompatible technologies and records policy constraints.',
        whatGetsStored: [
          'Decision -[:CHOSE]-> SkillRef(id="backend-express")',
          'Decision -[:REJECTED {reason: "tech_mismatch"}]-> SkillRef(id="backend-fastify")',
          'Decision -[:REJECTED {reason: "policy_restricted"}]-> SkillRef(id="shell-runner")',
        ],
        realValues: assignments.map(
          (a) =>
            `${a.subject}: chose ${a.chosen} (fit: ${a.fit || 0.9}) · rejected ${a.rejected.map((r) => `${r.skill} [${r.reason}]`).join(', ')}`
        ),
        nodeIds: ['req-frontend', 'cmp-web', 'cmp-api', 'cmp-db', 'skill-web', 'skill-api', 'skill-db'],
      },
      {
        title: 'Work',
        description:
          'Sub-agents work in dependency waves (database -> api -> web -> docs) generating workspace code files.',
        whatGetsStored: [
          'Agent -[:WROTE]-> Artifact(path="api/src/routes/todos.js")',
          'Agent -[:WROTE]-> Artifact(path="database/schema.sql")',
        ],
        realValues: [
          'Files written: 13 artifacts across database/, api/, web/, and README.md',
          'Database wave completed -> API wave completed -> Web wave completed',
        ],
        nodeIds: ['req-frontend', 'cmp-web', 'cmp-api', 'cmp-db', 'skill-web', 'skill-api', 'skill-db', 'art-schema', 'art-routes'],
      },
      {
        title: 'Verify',
        description:
          'Static contract checker inspects generated artifacts against declared contracts. Flags discrepancies and applies remediation waves.',
        whatGetsStored: [
          'ContractViolation(kind="undeclared_endpoint", detail="GET /api/todo") -[:REMEDIATED_BY]-> Agent',
          'Contract -[:STATUS]-> Implemented',
        ],
        realValues: [
          `${filesData?.contracts_implemented || 9} of ${filesData?.contracts_total || 9} contracts implemented`,
          'Resolved violation: Web requested /api/todo; remediation synchronized to /api/todos',
        ],
        nodeIds: ['cmp-web', 'cmp-api', 'contr-get', 'contr-post', 'viol-01'],
      },
      {
        title: 'Answer',
        description:
          'Packages the codebase into a downloadable zip archive with run instructions. Parks test command execution behind an approval gate.',
        whatGetsStored: [
          'ArtifactZip(url="/api/runs/run_f2/artifacts.zip")',
          'ActionRequest(kind="run_build_check", status="PENDING")',
        ],
        realValues: [
          'Ready: ZIP package generated with README and seed scripts',
          'Action: run_build_check (npm install, npm run build) waiting for user approval',
        ],
        nodeIds: ['cmp-web', 'cmp-api', 'contr-get', 'contr-post'],
      },
    ];
  }, []);

  const activeStages = activeTab === 'investigate' ? investigateStages : buildStages;
  const currentStage = activeStages[currentStageIdx] || activeStages[0]!;
  const fullTrace = activeTab === 'investigate' ? F1_TRACE : F2_TRACE;

  // Progressive graph elements for current stage
  const stageElements = useMemo(() => {
    const revealedNodeIds = new Set(currentStage.nodeIds);
    const visibleNodes: TraceNode[] = fullTrace.nodes.filter((n) => revealedNodeIds.has(n.id));
    const visibleNodeIdSet = new Set(visibleNodes.map((n) => n.id));

    const visibleEdges: TraceEdge[] = fullTrace.edges.filter(
      (e) => visibleNodeIdSet.has(e.src) && visibleNodeIdSet.has(e.dst)
    );

    return toElements({
      nodes: visibleNodes,
      edges: visibleEdges,
      pathNodeIds: Array.from(revealedNodeIds),
    }).elements;
  }, [currentStage, fullTrace]);

  return (
    <PageShell>
      <div className="page-column">
        {/* Header */}
        <header className={styles.header}>
          <div className={styles.label}>HOW IT WORKS</div>
          <h1 className={styles.heading}>One request, followed end to end.</h1>
          <p className={styles.subline}>
            Pick a run below and step through what the system actually records.
          </p>

          <div className={styles.tabsContainer}>
            <Tabs
              activeId={activeTab}
              onChange={(tab) => {
                setActiveTab(tab as 'investigate' | 'build');
                setCurrentStageIdx(0);
              }}
              tabs={[
                { id: 'investigate', label: 'INVESTIGATE RUN' },
                { id: 'build', label: 'BUILD RUN' },
              ]}
            />
          </div>
        </header>

        {/* Walkthrough Two-Column */}
        <div className={styles.walkthroughGrid}>
          {/* Left Column: Vertical Stepper */}
          <div className={styles.stepperCol} role="region" aria-label="Walkthrough stages">
            {activeStages.map((stg, idx) => {
              const isCurrent = idx === currentStageIdx;
              const numFormatted = String(idx + 1).padStart(2, '0');

              return (
                <div key={stg.title}>
                  <div
                    className={`${styles.stepHeader} ${isCurrent ? styles.activeStepHeader : ''}`}
                    onClick={() => setCurrentStageIdx(idx)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && setCurrentStageIdx(idx)}
                    aria-expanded={isCurrent}
                  >
                    <div>
                      <span className={styles.stepNumber}>{numFormatted}</span>
                      <span className={styles.stepTitle}>{stg.title}</span>
                    </div>
                  </div>

                  {isCurrent && (
                    <div className={styles.stepContent}>
                      <p className={styles.stepDescription}>{stg.description}</p>

                      <div className={styles.storedSection}>
                        <span className={styles.storedTitle}>WHAT GETS STORED</span>
                        {stg.whatGetsStored.map((item, i) => (
                          <div key={i} className={styles.storedItem}>
                            {item}
                          </div>
                        ))}
                      </div>

                      <div className={styles.storedSection}>
                        <span className={styles.storedTitle}>FIXTURE VALUES</span>
                        <div className={styles.valuesList}>
                          {stg.realValues.map((val, i) => (
                            <div key={i}>• {val}</div>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}

            {/* Stepper Prev/Next Controls */}
            <div className={styles.stepperNav}>
              <GhostButton
                disabled={currentStageIdx <= 0}
                onClick={() => setCurrentStageIdx((prev) => Math.max(0, prev - 1))}
              >
                PREVIOUS
              </GhostButton>

              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--color-smoke)' }}>
                STAGE {currentStageIdx + 1} OF 6
              </span>

              <GhostButton
                disabled={currentStageIdx >= 5}
                onClick={() => setCurrentStageIdx((prev) => Math.min(5, prev + 1))}
              >
                NEXT
              </GhostButton>
            </div>
          </div>

          {/* Right Column: Progressive Graph Canvas */}
          <div className={styles.canvasCol}>
            <MiniGraph
              elements={stageElements}
              height="100%"
              direction={activeTab === 'build' ? 'TB' : 'LR'}
            />
          </div>
        </div>

        <hr className="divider" />

        {/* Section: GLOSSARY */}
        <section className={styles.sectionHeader} aria-labelledby="glossary-heading">
          <div className={styles.label}>DEFINITIONS</div>
          <h2 id="glossary-heading" className={styles.sectionTitleLg}>Glossary.</h2>
        </section>

        <dl className={styles.glossaryGrid}>
          <div className={styles.glossaryItem}>
            <dt className={styles.glossaryTerm}>Atlas</dt>
            <dd className={styles.glossaryDef}>
              Catalog of skills, capabilities, technologies, and historical track records stored in the graph.
            </dd>
          </div>
          <div className={styles.glossaryItem}>
            <dt className={styles.glossaryTerm}>Pack</dt>
            <dd className={styles.glossaryDef}>
              A bundle of skills, tools, and policy rules configured for one kind of domain work (Investigate or Build).
            </dd>
          </div>
          <div className={styles.glossaryItem}>
            <dt className={styles.glossaryTerm}>Skill</dt>
            <dd className={styles.glossaryDef}>
              A specialized prompt fragment paired strictly with the MCP tools it exposes to the sub-agent.
            </dd>
          </div>
          <div className={styles.glossaryItem}>
            <dt className={styles.glossaryTerm}>Slice</dt>
            <dd className={styles.glossaryDef}>
              The isolated sub-graph of data that one sub-agent can inspect and query during its execution.
            </dd>
          </div>
          <div className={styles.glossaryItem}>
            <dt className={styles.glossaryTerm}>Finding</dt>
            <dd className={styles.glossaryDef}>
              A structured claim with confidence and cited evidence produced by a sub-agent.
            </dd>
          </div>
          <div className={styles.glossaryItem}>
            <dt className={styles.glossaryTerm}>Contract</dt>
            <dd className={styles.glossaryDef}>
              An endpoint, database table schema, environment variable, or port that pieces of a build must satisfy.
            </dd>
          </div>
          <div className={styles.glossaryItem}>
            <dt className={styles.glossaryTerm}>Decision</dt>
            <dd className={styles.glossaryDef}>
              A stored choice record linking chosen skills, rejected candidates, and explicit rejection rationales.
            </dd>
          </div>
          <div className={styles.glossaryItem}>
            <dt className={styles.glossaryTerm}>Action</dt>
            <dd className={styles.glossaryDef}>
              A change or command execution that halts outside the run graph until approved by a human approver.
            </dd>
          </div>
        </dl>

        <hr className="divider" />

        {/* Section: SAFETY MODEL */}
        <section className={styles.sectionHeader} aria-labelledby="safety-heading">
          <div className={styles.label}>ARCHITECTURE & SAFETY</div>
          <h2 id="safety-heading" className={styles.sectionTitleLg}>Safety model.</h2>
        </section>

        <div className={styles.safetyGrid}>
          <div className={styles.safetyCard}>
            <h3 className={styles.safetyTitle}>Files stay in a sandbox</h3>
            <p className={styles.safetyBody}>
              Agents write only inside a per-run isolated workspace. Every file path is validated before writing, preventing directory traversal.
            </p>
          </div>

          <div className={styles.safetyCard}>
            <h3 className={styles.safetyTitle}>Nothing runs without approval</h3>
            <p className={styles.safetyBody}>
              Flagging customers, modifying databases, or executing npm test commands are approval-gated actions that wait for human review.
            </p>
          </div>

          <div className={styles.safetyCard}>
            <h3 className={styles.safetyTitle}>Queries are constrained</h3>
            <p className={styles.safetyBody}>
              Model-written Cypher queries are strictly read-only, row-capped, parameterized, and pinned to the agent's own slice of the graph.
            </p>
          </div>
        </div>

        <hr className="divider" />

        {/* CTA Section */}
        <div className={styles.ctaSection}>
          <h2 className={styles.heading} style={{ fontSize: '34px' }}>
            Ready to trace a real request?
          </h2>
          <Link to="/platform">
            <Button showArrow={true}>
              TRY THE PLATFORM
            </Button>
          </Link>
        </div>
      </div>
    </PageShell>
  );
};
