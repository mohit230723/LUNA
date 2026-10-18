import React from 'react';
import { Database, Wrench, Code2, Lock, FileCheck, ShieldAlert } from 'lucide-react';
import styles from './UnderTheHood.module.css';

const items = [
  {
    icon: Database,
    title: 'FALKORDB',
    line: 'Atlas, data, run memory, and per-agent graphs live in one graph database.',
  },
  {
    icon: Wrench,
    title: 'MCP TOOL SCOPING',
    line: "Each sub-agent gets a tool server with only its skill's tools.",
  },
  {
    icon: Code2,
    title: 'PARAMETERIZED CYPHER',
    line: 'Queries the system builds never interpolate values.',
  },
  {
    icon: Lock,
    title: 'READ-ONLY NATURAL LANGUAGE QUERIES',
    line: 'Model-written Cypher is validated and run through a read-only path.',
  },
  {
    icon: FileCheck,
    title: 'PROVENANCE CHECKS',
    line: 'Cited evidence must exist in the slice and appear in tool output.',
  },
  {
    icon: ShieldAlert,
    title: 'APPROVAL GATE',
    line: 'Actions outside the run graph execute only after approval.',
  },
];

export const UnderTheHood: React.FC = () => {
  return (
    <section className={styles.section} aria-label="Under the hood">
      <span className={styles.label}>UNDER THE HOOD</span>
      <h2 className={styles.heading}>Six constraints that keep the system honest.</h2>

      <div className={styles.grid}>
        {items.map((item) => {
          const Icon = item.icon;
          return (
            <div key={item.title} className={styles.cell}>
              <Icon size={28} strokeWidth={1.5} className={styles.icon} aria-hidden="true" />
              <h3 className={styles.cellTitle}>{item.title}</h3>
              <p className={styles.cellLine}>{item.line}</p>
            </div>
          );
        })}
      </div>

      <p className={styles.limitsNote}>
        Limits: build quality depends on the model you connect. The contract checker verifies
        consistency between pieces, not that the app runs, unless you approve the build check.
      </p>
    </section>
  );
};
