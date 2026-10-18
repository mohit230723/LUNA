import React, { useRef, useState, useEffect } from 'react';
import type { TraceStep } from '../../api/contract';
import styles from './StepList.module.css';

export interface StepListProps {
  steps: TraceStep[];
  activeStepSeq?: number;
  onSelectStep: (seq: number) => void;
  onHoverStep?: (seq: number | null) => void;
  mode?: 'traversal' | 'blueprint';
}

const ROW_HEIGHT = 68;

export const StepList: React.FC<StepListProps> = ({
  steps,
  activeStepSeq,
  onSelectStep,
  onHoverStep,
  mode = 'traversal',
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [scrollTop, setScrollTop] = useState(0);

  // Auto-scroll to active step
  useEffect(() => {
    if (activeStepSeq === undefined || !containerRef.current) return;
    const activeIndex = steps.findIndex((s) => s.seq === activeStepSeq);
    if (activeIndex >= 0) {
      const topPos = activeIndex * ROW_HEIGHT;
      if (
        topPos < containerRef.current.scrollTop ||
        topPos > containerRef.current.scrollTop + containerRef.current.clientHeight - ROW_HEIGHT
      ) {
        containerRef.current.scrollTo({ top: topPos, behavior: 'smooth' });
      }
    }
  }, [activeStepSeq, steps]);

  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    setScrollTop(e.currentTarget.scrollTop);
  };

  const totalCount = steps.length;
  const isVirtual = totalCount > 100;

  // Virtual windowing calculations if > 100 rows
  const visibleCount = Math.ceil(700 / ROW_HEIGHT) + 4;
  const startIndex = isVirtual ? Math.max(0, Math.floor(scrollTop / ROW_HEIGHT) - 2) : 0;
  const endIndex = isVirtual ? Math.min(totalCount, startIndex + visibleCount) : totalCount;
  const renderedSteps = steps.slice(startIndex, endIndex);

  return (
    <aside
      className={styles.container}
      ref={containerRef}
      onScroll={handleScroll}
      aria-label="Trace step list"
    >
      <div className={styles.header}>
        {mode === 'blueprint' ? 'BLUEPRINT EVENTS' : 'TRAVERSAL STEPS'} ({steps.length})
      </div>

      {steps.length === 0 ? (
        <div className={styles.emptyState}>No steps recorded.</div>
      ) : (
        <div
          className={styles.list}
          style={isVirtual ? { height: totalCount * ROW_HEIGHT, position: 'relative' } : undefined}
        >
          {renderedSteps.map((step, idx) => {
            const actualIndex = startIndex + idx;
            const seqFormatted = String(step.seq).padStart(2, '0');
            const isActive = step.seq === activeStepSeq;

            const style: React.CSSProperties | undefined = isVirtual
              ? {
                  position: 'absolute',
                  top: actualIndex * ROW_HEIGHT,
                  left: 0,
                  right: 0,
                  height: ROW_HEIGHT,
                }
              : undefined;

            return (
              <div
                key={step.seq}
                className={`${styles.stepItem} ${isActive ? styles.activeStep : ''}`}
                style={style}
                onClick={() => onSelectStep(step.seq)}
                onMouseEnter={() => onHoverStep?.(step.seq)}
                onMouseLeave={() => onHoverStep?.(null)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    onSelectStep(step.seq);
                  }
                }}
              >
                <div className={styles.primaryLine}>
                  <span className={styles.seq}>{seqFormatted}</span>
                  <span>{step.from}</span>
                  <span className={styles.relTag}> -[{step.rel}]-&gt; </span>
                  <span>{step.to}</span>
                </div>
                <div className={styles.secondaryLine}>
                  {step.tool ? `${step.tool} · ` : ''}
                  {step.agent_id ? `${step.agent_id} · ` : ''}
                  {step.note}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </aside>
  );
};
