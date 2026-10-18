import React from 'react';
import { Badge } from '../../ui/Badge';
import type { Backend, Pack } from '../../../api/contract';
import styles from './blocks.module.css';

export interface RoutingBlockProps {
  pack: Pack;
  intent: string;
  confidence: number;
  backend: Backend;
}

export const RoutingBlock: React.FC<RoutingBlockProps> = ({
  pack,
  intent,
  confidence,
  backend,
}) => {
  return (
    <div className={styles.blockCard}>
      <div className={styles.blockHeader}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <h4 className={styles.blockTitle}>ROUTED TO {pack.toUpperCase()}</h4>
          <span className={styles.monoMeta}>CONFIDENCE {confidence.toFixed(2)}</span>
        </div>
        <Badge size="compact">{backend.toUpperCase()}</Badge>
      </div>
      <p style={{ margin: 0, fontSize: '14px', color: 'var(--color-smoke)' }}>
        Intent: <span style={{ color: 'var(--color-chalk)' }}>{intent}</span>
      </p>
    </div>
  );
};
