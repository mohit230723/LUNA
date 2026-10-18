import React from 'react';
import styles from './FlowSteps.module.css';

const steps = [
  {
    num: '01',
    title: 'ROUTE',
    desc: 'Decides which pack handles the prompt, and asks you when it is not sure.',
  },
  {
    num: '02',
    title: 'PLAN',
    desc: 'Writes the plan into a run graph: subtasks for investigations, components and contracts for builds.',
  },
  {
    num: '03',
    title: 'ASSIGN',
    desc: 'Queries the Skill Atlas, stores the chosen skill and each rejected one with its reason, and checks the fit.',
  },
  {
    num: '04',
    title: 'WORK',
    desc: 'Sub-agents run in parallel on isolated slices through tools scoped to their skill.',
  },
  {
    num: '05',
    title: 'VERIFY AND ANSWER',
    desc: 'Checks evidence or contracts, resolves conflicts without deleting anything, and composes the answer. Actions wait for approval.',
  },
];

export const FlowSteps: React.FC = () => {
  return (
    <section className={styles.section} aria-label="How a request flows">
      <span className={styles.label}>HOW A REQUEST FLOWS</span>
      <h2 className={styles.heading}>From prompt to traceable answer.</h2>

      <div className={styles.list}>
        {steps.map((s) => (
          <div key={s.num} className={styles.row}>
            <span className={styles.numeral}>{s.num}</span>
            <span className={styles.stepTitle}>{s.title}</span>
            <span className={styles.stepDesc}>{s.desc}</span>
          </div>
        ))}
      </div>
    </section>
  );
};
