import React from 'react';
import { NavLink } from 'react-router-dom';
import { Network, TerminalSquare } from 'lucide-react';
import styles from './TwoWays.module.css';

/** The two ways to use LUNA, shown right under the hero so both are visible before scrolling. */
export const TwoWays: React.FC = () => {
  return (
    <section className={styles.section} aria-label="Two ways to use LUNA">
      <div className={styles.grid}>
        <article className={styles.card}>
          <div className={styles.iconWrap} aria-hidden="true">
            <Network size={20} strokeWidth={1.5} />
          </div>
          <h2 className={styles.title}>Investigate connected data</h2>
          <p className={styles.body}>
            Paste a brief or upload records. LUNA turns them into a graph you can question, and every answer
            comes back with the evidence it was built from.
          </p>
          <ul className={styles.points}>
            <li>Entities and links are checked against your source text</li>
            <li>Sub-agents work on private slices of the graph</li>
            <li>Trace any answer step by step</li>
          </ul>
          <NavLink to="/platform?tab=cases" className={styles.link}>
            Open Cases
          </NavLink>
        </article>

        <article className={styles.card}>
          <div className={styles.iconWrap} aria-hidden="true">
            <TerminalSquare size={20} strokeWidth={1.5} />
          </div>
          <h2 className={styles.title}>Give your coding agent skills</h2>
          <p className={styles.body}>
            Connect Claude Code or Antigravity over MCP. LUNA plans the build, hands each task a skill from the
            graph, and assembles what the agents deliver.
          </p>
          <pre className={styles.code} aria-label="Connect command">
            <code>claude mcp add --transport http luna http://localhost:8000/mcp</code>
          </pre>
          <NavLink to="/platform" className={styles.link}>
            Open Agents
          </NavLink>
        </article>
      </div>
    </section>
  );
};
