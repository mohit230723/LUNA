import React from 'react';
import { AlertTriangle } from 'lucide-react';
import type { GraphStats } from '../../../api/contract';
import styles from './GraphSummaryBlock.module.css';

interface GraphSummaryBlockProps {
  data: GraphStats;
  onSelectEntity?: (name: string) => void;
}

export const GraphSummaryBlock: React.FC<GraphSummaryBlockProps> = ({ data, onSelectEntity }) => {
  const modelName = data.extraction?.model || 'LLM';
  const byLabelEntries = Object.entries(data.by_label || {}).sort((a, b) => b[1] - a[1]);

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <span className={styles.readyBadge}>CONTEXT GRAPH READY</span>
      </div>

      {/* 4-cell hairline grid */}
      <div className={styles.statsGrid}>
        <div className={styles.statCell}>
          <div className={styles.statLabel}>NODES</div>
          <div className={styles.statValue}>{(data.nodes || 0).toLocaleString()}</div>
        </div>
        <div className={styles.statCell}>
          <div className={styles.statLabel}>EDGES</div>
          <div className={styles.statValue}>{(data.edges || 0).toLocaleString()}</div>
        </div>
        <div className={styles.statCell}>
          <div className={styles.statLabel}>SOURCES</div>
          <div className={styles.statValue}>{(data.sources || 0).toLocaleString()}</div>
        </div>
        <div className={styles.statCell}>
          <div className={styles.statLabel}>MODEL</div>
          <div className={styles.statValue} style={{ fontSize: '14px' }}>
            {modelName}
          </div>
        </div>
      </div>

      {/* Top Entities */}
      {data.top_entities && data.top_entities.length > 0 && (
        <div className={styles.section}>
          <div className={styles.sectionLabel}>TOP ENTITIES</div>
          <div className={styles.chipsWrap}>
            {data.top_entities.map((ent) => (
              <button
                key={ent.cid}
                type="button"
                className={styles.entityChip}
                onClick={() => onSelectEntity && onSelectEntity(ent.name || ent.cid)}
                title={`Degree: ${ent.degree}`}
              >
                <span className={styles.entityName}>{ent.name || ent.cid}</span>
                <span className={styles.entityType}>{(ent.type || 'Entity').toUpperCase()}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* By Type */}
      {byLabelEntries.length > 0 && (
        <div className={styles.section}>
          <div className={styles.sectionLabel}>BY TYPE</div>
          <div className={styles.byTypeList}>
            {byLabelEntries.map(([label, count]) => (
              <div key={label} className={styles.byTypeItem}>
                <span className={styles.typeLabel}>{label}</span>
                <span className={styles.typeCount}>{count.toLocaleString()}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Warnings */}
      {data.warnings && data.warnings.length > 0 && (
        <div className={styles.warningsList}>
          {data.warnings.map((w, idx) => (
            <div key={idx} className={styles.warningItem}>
              <AlertTriangle size={15} strokeWidth={1.5} color="var(--color-compass-gold)" />
              <span>{w}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
