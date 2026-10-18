import React from 'react';
import { GhostButton } from '../../ui/GhostButton';
import type { Subtask, ComponentInfo, ContractInfo } from '../../../api/contract';
import styles from './blocks.module.css';

export interface PlanBlockProps {
  subtasks?: Subtask[];
  components?: ComponentInfo[];
  contracts?: ContractInfo[];
  onViewBlueprint?: () => void;
}

export const PlanBlock: React.FC<PlanBlockProps> = ({
  subtasks,
  components,
  contracts,
  onViewBlueprint,
}) => {
  return (
    <div className={styles.blockCard}>
      <div className={styles.blockHeader}>
        <h4 className={styles.blockTitle}>EXECUTION PLAN</h4>
        {onViewBlueprint && (
          <GhostButton onClick={onViewBlueprint}>VIEW BLUEPRINT</GhostButton>
        )}
      </div>

      {/* Investigate Plan: Numbered subtasks with capability tags */}
      {subtasks && subtasks.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {subtasks.map((st, idx) => (
            <div
              key={st.id}
              style={{
                display: 'flex',
                alignItems: 'baseline',
                justifyContent: 'space-between',
                padding: '6px 0',
                borderBottom: '1px solid var(--color-graphite)',
              }}
            >
              <div style={{ display: 'flex', gap: 12, alignItems: 'baseline' }}>
                <span className={styles.monoMeta}>{String(idx + 1).padStart(2, '0')}</span>
                <span style={{ fontSize: '14px', color: 'var(--color-chalk)' }}>
                  {st.description}
                </span>
              </div>
              <span className={styles.chip}>{st.capability}</span>
            </div>
          ))}
        </div>
      )}

      {/* Build Plan: Mini table of components + contracts list in mono */}
      {components && components.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div>
            <span className={styles.monoMeta} style={{ display: 'block', marginBottom: 8 }}>
              COMPONENTS
            </span>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th className={styles.th}>NAME</th>
                  <th className={styles.th}>KIND</th>
                  <th className={styles.th}>TECH</th>
                </tr>
              </thead>
              <tbody>
                {components.map((comp) => (
                  <tr key={comp.id}>
                    <td className={styles.td} style={{ fontFamily: 'var(--font-mono)' }}>
                      {comp.name}
                    </td>
                    <td className={styles.td}>{comp.kind}</td>
                    <td className={styles.td} style={{ color: 'var(--color-smoke)' }}>
                      {comp.tech}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {contracts && contracts.length > 0 && (
            <div>
              <span className={styles.monoMeta} style={{ display: 'block', marginBottom: 8 }}>
                CONTRACTS DECLARED
              </span>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {contracts.map((c) => (
                  <span key={c.id} className={styles.chip}>
                    {c.kind}: {c.key}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
