import React, { useState, useEffect } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { GhostButton } from '../ui/GhostButton';
import { StageList } from './StageList';
import type { StageState } from '../../state/stages';
import type { AgentInfo, RunStatus } from '../../api/contract';
import styles from './RunCard.module.css';

export interface RunCardProps {
  stages: Record<string, StageState> | StageState[];
  agents?: AgentInfo[];
  status?: RunStatus;
  onCancel?: () => void;
}

export const RunCard: React.FC<RunCardProps> = ({
  stages,
  agents = [],
  status = 'streaming',
  onCancel,
}) => {
  const [collapsed, setCollapsed] = useState(status === 'done');
  const [liveAnnouncement, setLiveAnnouncement] = useState('');

  // Update aria-live when stages change
  useEffect(() => {
    const stageEntries = Array.isArray(stages)
      ? stages.map((s) => [s.name, s] as const)
      : Object.entries(stages);

    for (const [name, s] of stageEntries) {
      if (s.status === 'running') {
        setLiveAnnouncement(`Stage ${name}: running`);
        break;
      }
    }
  }, [stages]);

  const isFailed = status === 'failed';
  const isRunning = status === 'streaming' || status === 'queued';

  return (
    <div className={`${styles.card} ${isFailed ? styles.failedCard : ''}`}>
      {/* Screen reader live region */}
      <div aria-live="polite" className={styles.srOnly}>
        {liveAnnouncement}
      </div>

      <div
        className={styles.cardHeader}
        onClick={() => setCollapsed(!collapsed)}
        role="button"
        tabIndex={0}
        aria-expanded={!collapsed}
        onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && setCollapsed(!collapsed)}
      >
        <div className={styles.headerLeft}>
          {collapsed ? <ChevronRight size={16} /> : <ChevronDown size={16} />}
          <span className={styles.headerTitle}>
            {isRunning ? 'PIPELINE EXECUTION IN PROGRESS' : isFailed ? 'PIPELINE EXECUTION FAILED' : 'PIPELINE EXECUTION COMPLETE'}
          </span>
        </div>

        {isRunning && onCancel && (
          <GhostButton
            onClick={(e) => {
              e.stopPropagation();
              onCancel();
            }}
          >
            CANCEL
          </GhostButton>
        )}
      </div>

      {!collapsed && (
        <StageList stages={stages} agents={agents} />
      )}
    </div>
  );
};
