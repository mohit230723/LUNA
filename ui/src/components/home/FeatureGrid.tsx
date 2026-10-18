import React from 'react';
import { GitBranch, Boxes, ShieldCheck, BadgeCheck } from 'lucide-react';
import styles from './FeatureGrid.module.css';

const features = [
  {
    icon: GitBranch,
    title: 'SKILLS ASSIGNED BY QUERY',
    body: 'Choosing a skill is a graph query over capabilities, technologies, policy, and track record. Rejected candidates and the reasons are stored.',
  },
  {
    icon: Boxes,
    title: 'ISOLATED AGENT GRAPHS',
    body: 'Each sub-agent works on its own slice of the data and can call only the tools its skill exposes.',
  },
  {
    icon: ShieldCheck,
    title: 'CHECKED EVIDENCE',
    body: "A finding is promoted only if its evidence exists in the agent's slice and appeared in the agent's own tool output.",
  },
  {
    icon: BadgeCheck,
    title: 'APPROVAL-GATED ACTIONS',
    body: 'Flagging customers or running a build happens only after a person approves it.',
  },
];

export const FeatureGrid: React.FC = () => {
  return (
    <section className={styles.section} aria-label="What it does">
      <span className={styles.label}>WHAT IT DOES</span>
      <h2 className={styles.heading}>Four ideas, built into the graph.</h2>

      <div className={styles.grid}>
        {features.map((feat) => {
          const Icon = feat.icon;
          return (
            <div key={feat.title} className={styles.card}>
              <Icon size={32} strokeWidth={1.5} className={styles.icon} aria-hidden="true" />
              <h3 className={styles.cardHeading}>{feat.title}</h3>
              <p className={styles.cardBody}>{feat.body}</p>
            </div>
          );
        })}
      </div>
    </section>
  );
};
