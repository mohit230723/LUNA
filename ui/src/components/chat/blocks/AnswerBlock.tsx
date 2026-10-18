import React from 'react';
import { Markdown } from '../../ui/Markdown';
import { GhostButton } from '../../ui/GhostButton';
import { MiniGraph } from '../../graph/MiniGraph';
import type { Backend } from '../../../api/contract';
import type { ElementsDefinition } from 'cytoscape';
import styles from './blocks.module.css';

export interface AnswerBlockProps {
  text: string;
  citedCids: string[];
  backend: Backend;
  model?: string;
  entityNames?: Record<string, string>;
  onViewTrace?: () => void;
  onOpenWhy?: () => void;
  onCidClick?: (cid: string) => void;
  previewElements?: ElementsDefinition;
}

export const AnswerBlock: React.FC<AnswerBlockProps> = ({
  text,
  citedCids,
  model,
  entityNames = {},
  onViewTrace,
  onOpenWhy,
  onCidClick,
  previewElements,
}) => {
  return (
    <div className={styles.answerCard}>
      {/* Model badge */}
      {model && (
        <div style={{ marginBottom: 12 }}>
          <span className={styles.monoMeta}>ANSWER · {model}</span>
        </div>
      )}

      {/* Sanitized Markdown content with [[cid]] replacement */}
      <Markdown content={text} onCidClick={onCidClick} entityNames={entityNames} />

      {/* Cited CIDs chips */}
      {citedCids.length > 0 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginTop: 12 }}>
          <span className={styles.monoMeta}>CITATIONS:</span>
          {citedCids.map((cid) => (
            <span
              key={cid}
              className={styles.cidChip}
              onClick={() => onCidClick && onCidClick(cid)}
              role="button"
              tabIndex={0}
              aria-label={`Citation node ${cid}`}
            >
              {entityNames[cid] || cid}
            </span>
          ))}
        </div>
      )}

      {/* Action Buttons: VIEW TRACE and WHY */}
      <div className={styles.answerActions}>
        {onViewTrace && (
          <GhostButton onClick={onViewTrace}>VIEW TRACE</GhostButton>
        )}
        {onOpenWhy && (
          <GhostButton onClick={onOpenWhy}>WHY</GhostButton>
        )}
      </div>

      {/* TracePreview: MiniGraph */}
      {previewElements && (
        <div className={styles.tracePreviewContainer} onClick={onViewTrace} style={{ cursor: 'pointer' }}>
          <MiniGraph
            elements={previewElements}
            height={200}
            onClick={onViewTrace}
            direction="LR"
          />
        </div>
      )}
    </div>
  );
};
