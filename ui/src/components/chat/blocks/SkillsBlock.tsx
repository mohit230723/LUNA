import React from 'react';
import { Badge } from '../../ui/Badge';
import type { SkillAssignment } from '../../../api/contract';
import styles from './blocks.module.css';

export interface SkillsBlockProps {
  assignments: SkillAssignment[];
}

const reasonLabels: Record<string, string> = {
  policy_restricted: 'POLICY RESTRICTED',
  lower_track_record: 'LOWER TRACK RECORD',
  tech_mismatch: 'TECH MISMATCH',
};

export const SkillsBlock: React.FC<SkillsBlockProps> = ({ assignments }) => {
  return (
    <div className={styles.blockCard}>
      <h4 className={styles.blockTitle}>SKILLS ASSIGNED</h4>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
        {assignments.map((asgn) => (
          <div
            key={asgn.subject}
            style={{
              padding: '12px 16px',
              border: '1px solid var(--color-graphite)',
              borderRadius: 'var(--radius-card)',
              backgroundColor: 'var(--color-obsidian)',
            }}
          >
            {/* Subject and chosen skill header */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: 8,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
                <span className={styles.monoMeta}>{asgn.subject.toUpperCase()}</span>
                <span style={{ fontSize: '14px', color: 'var(--color-chalk)' }}>
                  CHOSE: <strong>{asgn.chosen}</strong>
                </span>
                {asgn.fit !== undefined && (
                  <span className={styles.monoMeta}>FIT {asgn.fit.toFixed(2)}</span>
                )}
              </div>
              <Badge size="compact">{asgn.backend.toUpperCase()}</Badge>
            </div>

            {asgn.reassigned_from && (
              <p
                style={{
                  margin: '4px 0 8px 0',
                  fontSize: '12px',
                  fontFamily: 'var(--font-mono)',
                  color: 'var(--color-ash)',
                }}
              >
                Reassigned from: {asgn.reassigned_from} (fit check triggered reassignment)
              </p>
            )}

            {/* Rejected candidates */}
            {asgn.rejected && asgn.rejected.length > 0 && (
              <div style={{ marginTop: 8, paddingTop: 8, borderTop: '1px solid var(--color-graphite)' }}>
                <span className={styles.monoMeta} style={{ display: 'block', marginBottom: 6 }}>
                  REJECTED CANDIDATES
                </span>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {asgn.rejected.map((rej) => (
                    <div
                      key={rej.skill}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                      }}
                    >
                      <span style={{ fontSize: '13px', color: 'var(--color-smoke)' }}>
                        {rej.skill}
                      </span>
                      <span className={styles.chip}>
                        {reasonLabels[rej.reason] || rej.reason.toUpperCase()}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};
