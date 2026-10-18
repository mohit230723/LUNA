import React from 'react';
import { Check, X } from 'lucide-react';
import { StatusDot } from '../ui/StatusDot';
import { AgentRow } from './AgentRow';
import type { StageState } from '../../state/stages';
import type { AgentInfo } from '../../api/contract';
import styles from './StageList.module.css';

export interface StageListProps {
  stages: Record<string, StageState> | StageState[];
  agents?: AgentInfo[];
}

const STAGE_ORDER = [
  'ROUTED',
  'PLANNED',
  'SKILLS ASSIGNED',
  'AGENTS WORKING',
  'VERIFIED',
  'ANSWER',
];

export const StageList: React.FC<StageListProps> = ({ stages, agents = [] }) => {
  const stageMap: Record<string, StageState> = Array.isArray(stages)
    ? Object.fromEntries(stages.map((s) => [s.name, s]))
    : stages;

  return (
    <div className={styles.list}>
      {STAGE_ORDER.map((stageKey) => {
        const stage = stageMap[stageKey] || { status: 'pending' };

        return (
          <div key={stageKey} className={styles.stageRow}>
            <div className={styles.stageHeader}>
              <div className={styles.stageLeft}>
                {stage.status === 'pending' && <StatusDot status="pending" showText={false} />}
                {stage.status === 'running' && <StatusDot status="running" showText={false} />}
                {stage.status === 'done' && (
                  <Check size={14} strokeWidth={1.5} color="var(--color-chalk)" />
                )}
                {stage.status === 'failed' && (
                  <X size={14} strokeWidth={1.5} color="var(--color-chalk)" />
                )}
                {stage.status === 'cancelled' && (
                  <StatusDot status="superseded" showText={false} />
                )}

                <span className={styles.stageName}>{stageKey}</span>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                {'durationMs' in stage && stage.durationMs !== undefined && stage.status === 'done' && (
                  <span className={styles.duration}>{stage.durationMs}ms</span>
                )}

                <span className={`${styles.stageStatus} ${
                  stage.status === 'pending'
                    ? styles.stageStatusPending
                    : stage.status === 'running'
                    ? styles.stageStatusRunning
                    : stage.status === 'done'
                    ? styles.stageStatusDone
                    : styles.stageStatusFailed
                }`}>
                  {stage.status.toUpperCase()}
                </span>
              </div>
            </div>

            {/* If AGENTS WORKING and agents exist, show agent rows */}
            {stageKey === 'AGENTS WORKING' && agents.length > 0 && (
              <div className={styles.agentsContainer}>
                {agents.map((agent) => (
                  <AgentRow key={agent.id} agent={agent} />
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};
