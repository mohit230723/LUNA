import React from 'react';
import { Badge } from '../../ui/Badge';
import { GhostButton } from '../../ui/GhostButton';
import type { FindingInfo } from '../../../api/contract';
import styles from './blocks.module.css';

export interface FindingsBlockProps {
  items: FindingInfo[];
  onOpenWhy?: (target: string) => void;
}

export const FindingsBlock: React.FC<FindingsBlockProps> = ({ items, onOpenWhy }) => {
  return (
    <div className={styles.blockCard}>
      <h4 className={styles.blockTitle}>EVIDENCE FINDINGS</h4>

      <table className={styles.table}>
        <thead>
          <tr>
            <th className={styles.th}>SUBJECT</th>
            <th className={styles.th}>VERDICT</th>
            <th className={styles.th}>CONF</th>
            <th className={styles.th}>SKILL</th>
            <th className={styles.th}>BACKEND</th>
            <th className={styles.th}>ACTION</th>
          </tr>
        </thead>
        <tbody>
          {items.map((f) => {
            const isSuperseded = f.status === 'superseded';
            return (
              <tr
                key={f.id}
                className={isSuperseded ? styles.supersededRow : ''}
              >
                <td className={styles.td} style={{ fontFamily: 'var(--font-mono)' }}>
                  {f.subject}
                </td>
                <td className={styles.td}>
                  {f.verdict === 'suspicious' ? (
                    <span>
                      <span aria-hidden="true" style={{ marginRight: 4 }}>◆</span>
                      SUSPICIOUS
                    </span>
                  ) : (
                    <span>
                      <span aria-hidden="true" style={{ marginRight: 4 }}>◇</span>
                      BENIGN
                    </span>
                  )}
                </td>
                <td className={styles.td} style={{ fontFamily: 'var(--font-mono)' }}>
                  {f.confidence.toFixed(2)}
                </td>
                <td className={styles.td} style={{ color: 'var(--color-smoke)' }}>
                  {f.skill_id}
                </td>
                <td className={styles.td}>
                  <Badge size="compact">{f.backend.toUpperCase()}</Badge>
                </td>
                <td className={styles.td}>
                  {onOpenWhy && (
                    <GhostButton onClick={() => onOpenWhy(f.subject)}>
                      WHY
                    </GhostButton>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};
