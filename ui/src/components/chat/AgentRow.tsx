import React from 'react';
import { Check, X } from 'lucide-react';
import { Badge } from '../ui/Badge';
import { StatusDot } from '../ui/StatusDot';
import type { AgentInfo } from '../../api/contract';
import styles from './AgentRow.module.css';

export interface AgentRowProps {
  agent: AgentInfo;
}

export const AgentRow: React.FC<AgentRowProps> = ({ agent }) => {
  return (
    <div className={styles.row}>
      <div className={styles.leftCol}>
        {agent.status === 'running' && <StatusDot status="running" showText={false} />}
        {agent.status === 'done' && <Check size={14} strokeWidth={1.5} color="var(--color-chalk)" />}
        {agent.status === 'failed' && <X size={14} strokeWidth={1.5} color="var(--color-chalk)" />}
        {agent.status === 'pending' && <StatusDot status="pending" showText={false} />}

        <span className={styles.skillName}>{agent.skill}</span>

        <span className={styles.counts}>
          {agent.tool_calls} tool calls
          {agent.hops_walked !== undefined && ` · ${agent.hops_walked} hops`}
          {agent.files_written !== undefined && ` · ${agent.files_written} files`}
        </span>
      </div>

      <div className={styles.rightCol}>
        {agent.reason && (
          <span className={styles.failedReason}>{agent.reason}</span>
        )}
        <Badge size="compact">{agent.backend.toUpperCase()}</Badge>
      </div>
    </div>
  );
};
