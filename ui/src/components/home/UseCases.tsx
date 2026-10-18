import React from 'react';
import { NavLink } from 'react-router-dom';
import { MiniGraph } from '../graph/MiniGraph';
import type { ElementsDefinition } from 'cytoscape';
import styles from './UseCases.module.css';

const investigatePrompt = 'Who is connected to the fraud involving customer cust-000?';
const buildPrompt = 'Build a todo app: React + Vite frontend, Express backend, Postgres database.';

const investigateElements: ElementsDefinition = {
  nodes: [
    { data: { id: 'c0', label: 'cust-000', type: 'Customer', on_path: true } },
    { data: { id: 'p1', label: 'ph-ring-01', type: 'Phone', on_path: true } },
    { data: { id: 'c3', label: 'cust-003', type: 'Customer', on_path: true } },
    { data: { id: 'b1', label: 'ba-ring-01', type: 'BankAccount', on_path: true } },
    { data: { id: 'c5', label: 'cust-005', type: 'Customer', on_path: true } },
  ],
  edges: [
    { data: { id: 'e1', source: 'c0', target: 'p1', rel: 'USES_PHONE', on_path: true } },
    { data: { id: 'e2', source: 'c3', target: 'p1', rel: 'USES_PHONE', on_path: true } },
    { data: { id: 'e3', source: 'c3', target: 'b1', rel: 'PAYS_FROM', on_path: true } },
    { data: { id: 'e4', source: 'c5', target: 'b1', rel: 'PAYS_FROM', on_path: true } },
  ],
};

const buildElements: ElementsDefinition = {
  nodes: [
    { data: { id: 'comp_web', label: 'web', type: 'Component', on_path: true } },
    { data: { id: 'contract_api', label: 'GET /todos', type: 'Contract', on_path: true } },
    { data: { id: 'comp_api', label: 'api', type: 'Component', on_path: true } },
    { data: { id: 'art_file', label: 'todos.js', type: 'Artifact', on_path: true } },
  ],
  edges: [
    { data: { id: 'be1', source: 'comp_web', target: 'contract_api', rel: 'CONSUMES', on_path: true } },
    { data: { id: 'be2', source: 'comp_api', target: 'contract_api', rel: 'PROVIDES', on_path: true } },
    { data: { id: 'be3', source: 'comp_api', target: 'art_file', rel: 'WROTE', on_path: true } },
  ],
};

export const UseCases: React.FC = () => {
  return (
    <section className={styles.section} aria-label="Two ways to use it">
      <span className={styles.label}>TWO WAYS TO USE IT</span>
      <h2 className={styles.heading}>Investigate or build.</h2>

      <div className={styles.grid}>
        {/* INVESTIGATE PANEL */}
        <div className={styles.panel}>
          <h3 className={styles.panelTitle}>INVESTIGATE</h3>
          <p className={styles.panelBody}>
            Ask a question over a connected-data graph. LUNA returns an answer with citations and the
            exact path it travelled.
          </p>
          <div className={styles.promptBox}>{investigatePrompt}</div>
          <NavLink
            to={`/platform?prompt=${encodeURIComponent(investigatePrompt)}`}
            className={styles.link}
          >
            TRY THIS PROMPT ↗
          </NavLink>
          <div className={styles.graphWrapper}>
            <MiniGraph elements={investigateElements} height={140} direction="LR" />
          </div>
        </div>

        {/* BUILD PANEL */}
        <div className={styles.panel}>
          <h3 className={styles.panelTitle}>BUILD</h3>
          <p className={styles.panelBody}>
            Describe a project and the stack you want. LUNA assigns frontend, backend, and database skills
            to sub-agents, checks that the pieces fit together, and returns the files.
          </p>
          <div className={styles.promptBox}>{buildPrompt}</div>
          <NavLink
            to={`/platform?prompt=${encodeURIComponent(buildPrompt)}`}
            className={styles.link}
          >
            TRY THIS PROMPT ↗
          </NavLink>
          <div className={styles.graphWrapper}>
            <MiniGraph elements={buildElements} height={140} direction="LR" />
          </div>
        </div>
      </div>
    </section>
  );
};
