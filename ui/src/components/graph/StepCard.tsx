import React from 'react';
import type { TraceStep, TraceNode } from '../../api/contract';
import styles from './StepCard.module.css';

interface StepCardProps {
  stepIndex: number; // 0 for START, 1..N for steps 1..N
  totalSteps: number;
  currentStep?: TraceStep;
  startNode?: TraceNode;
  nodeNameMap?: Record<string, string>;
  exploredSteps?: number;
}

export const StepCard: React.FC<StepCardProps> = ({
  stepIndex,
  totalSteps,
  currentStep,
  startNode,
  nodeNameMap = {},
  exploredSteps = 0,
}) => {
  const isStart = stepIndex === 0;
  const isEnd = stepIndex === totalSteps && totalSteps > 0;

  // Format step count: "STEP 00 / 06"
  const formattedCur = String(stepIndex).padStart(2, '0');
  const formattedTot = String(totalSteps).padStart(2, '0');

  // Title & Subtitle
  let title = '';
  let subtitle = '';
  let properties: { k: string; v: string }[] = [];
  let transitionLine = '';
  let note = '';
  let source: { name: string; locator: string; quote?: string } | undefined = undefined;

  if (isStart) {
    title = (startNode?.props?.name as string) || startNode?.id || 'Start Entity';
    subtitle = (startNode?.props?.type as string) || startNode?.label || 'ENTITY';
    note = 'Start of the traced path.';

    // Extract up to 4 properties from startNode
    if (startNode?.props) {
      const p = startNode.props;
      for (const [k, v] of Object.entries(p)) {
        if (properties.length >= 4) break;
        if (!['name', 'type', 'id', 'cid', 'status', 'context'].includes(k) && typeof v === 'string') {
          properties.push({ k, v: v.slice(0, 60) });
        }
      }
    }
  } else if (currentStep) {
    title = currentStep.value.title;
    subtitle = currentStep.value.subtitle;
    properties = currentStep.value.properties || [];
    note = currentStep.note;
    source = currentStep.source;

    const fromName = nodeNameMap[currentStep.from] || currentStep.from;
    const toName = nodeNameMap[currentStep.to] || currentStep.to;
    transitionLine = `${fromName} —[${currentStep.rel}]→ ${toName}`;
  }

  return (
    <div
      className={styles.stepCard}
      role="region"
      aria-live="polite"
      aria-label={`Step ${stepIndex} of ${totalSteps}: ${title}`}
    >
      {/* Header row */}
      <div className={styles.cardHeader}>
        <span className={styles.stepCounter}>
          STEP {formattedCur} / {formattedTot}
        </span>
        {!isStart && currentStep && (
          <div className={styles.tagsRow}>
            {currentStep.tool && <span className={styles.tag}>{currentStep.tool}</span>}
            {currentStep.agent_id && <span className={styles.tag}>{currentStep.agent_id}</span>}
          </div>
        )}
      </div>

      {/* Title & Type badge */}
      <div className={styles.titleRow}>
        <h2 className={styles.title}>{title}</h2>
        {subtitle && <span className={styles.typeBadge}>{subtitle.toUpperCase()}</span>}
      </div>

      {/* Transition Line */}
      {transitionLine && <div className={styles.transitionLine}>{transitionLine}</div>}

      {/* Note */}
      {note && <p className={styles.note}>{note}</p>}

      {/* Properties grid */}
      {properties.length > 0 && (
        <div className={styles.propsGrid}>
          {properties.map((prop, idx) => (
            <div key={idx} className={styles.propItem}>
              <span className={styles.propKey}>{prop.k}</span>
              <span className={styles.propVal}>{prop.v}</span>
            </div>
          ))}
        </div>
      )}

      {/* Source & Provenance */}
      {source && (
        <div className={styles.sourceSection}>
          <div className={styles.sourceLocator}>
            {source.name} · {source.locator}
          </div>
          {source.quote && (
            <div className={styles.sourceQuote}>
              "{source.quote.length > 160 ? source.quote.slice(0, 159) + '…' : source.quote}"
            </div>
          )}
        </div>
      )}

      {/* End of path notice */}
      {isEnd && (
        <div className={styles.endNotice}>
          END OF TRACED PATH · {exploredSteps} more steps were explored
        </div>
      )}
    </div>
  );
};
