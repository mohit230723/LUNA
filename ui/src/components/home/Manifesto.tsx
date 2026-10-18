import React from 'react';
import { NavLink } from 'react-router-dom';
import { GhostButton } from '../ui/GhostButton';
import styles from './Manifesto.module.css';

export const Manifesto: React.FC = () => {
  return (
    <section className={styles.section} aria-label="Manifesto">
      <div className={styles.container}>
        <h2 className={styles.title}>Why graphs?</h2>
        <p className={styles.body}>
          Most agent systems pass text between agents and hope it stays consistent. LUNA keeps the plan,
          the evidence, and every decision as nodes and edges in one database. That makes the shared
          memory inspectable: you can follow a result back through the findings, the tools, and the
          skills that produced it.
        </p>
        <p className={styles.body}>
          It does not make the agents smarter. It makes their work checkable.
        </p>
        <NavLink to="/how-it-works" tabIndex={-1}>
          <GhostButton>READ HOW IT WORKS</GhostButton>
        </NavLink>
      </div>
    </section>
  );
};
