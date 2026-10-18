import React from 'react';
import { Play, Square, SkipBack, SkipForward } from 'lucide-react';
import { Button } from '../ui/Button';
import { GhostButton } from '../ui/GhostButton';
import { IconButton } from '../ui/IconButton';
import styles from './Scrubber.module.css';

export interface ScrubberProps {
  totalSteps: number;
  mode: 'overview' | 'tour';
  stepIndex: number | null; // null in overview, 0 for START, 1..N
  onEnterTour: () => void;
  onExitTour: () => void;
  onStepBack: () => void;
  onStepForward: () => void;
  onSeek: (stepIndex: number) => void;
}

export const Scrubber: React.FC<ScrubberProps> = ({
  totalSteps,
  mode,
  stepIndex,
  onEnterTour,
  onExitTour,
  onStepBack,
  onStepForward,
  onSeek,
}) => {
  const isTour = mode === 'tour';
  const hasNoSteps = totalSteps === 0;
  const noStepsTitle = hasNoSteps ? 'No traversal path to replay' : undefined;

  const currentIdx = stepIndex ?? 0;
  const isAtStart = isTour && currentIdx <= 0;
  const isAtEnd = isTour && currentIdx >= totalSteps;

  const formattedCur = String(currentIdx).padStart(2, '0');
  const formattedTot = String(totalSteps).padStart(2, '0');

  return (
    <footer className={styles.container} aria-label="Playback scrubber">
      {/* Playback Controls Left */}
      <div className={styles.controlsLeft}>
        {isTour ? (
          <Button
            onClick={onExitTour}
            aria-label="Exit tour"
            title="Exit tour"
          >
            <Square size={13} fill="var(--color-obsidian)" strokeWidth={1} />
          </Button>
        ) : (
          <Button
            onClick={onEnterTour}
            disabled={hasNoSteps}
            aria-label="Start tour"
            title={noStepsTitle || 'Start tour'}
          >
            <Play size={14} strokeWidth={2} fill="var(--color-obsidian)" />
          </Button>
        )}

        <IconButton
          aria-label="Step back"
          onClick={onStepBack}
          disabled={!isTour || isAtStart}
          title={!isTour ? 'Previous (disabled in overview)' : 'Previous step'}
        >
          <SkipBack size={16} strokeWidth={1.5} />
        </IconButton>

        <IconButton
          aria-label={isTour ? 'Step forward' : 'Start tour'}
          onClick={isTour ? onStepForward : onEnterTour}
          disabled={hasNoSteps || (isTour && isAtEnd)}
          title={noStepsTitle || (isTour ? 'Next step' : 'Start tour')}
        >
          <SkipForward size={16} strokeWidth={1.5} />
        </IconButton>
      </div>

      {/* Timeline Slider Center */}
      <div className={styles.timelineCenter}>
        <div className={styles.sliderRow}>
          <input
            type="range"
            min={0}
            max={Math.max(1, totalSteps)}
            value={currentIdx}
            onChange={(e) => onSeek(Number(e.target.value))}
            className={styles.slider}
            aria-label="Seek trace timeline step"
            disabled={hasNoSteps}
          />
        </div>

        {totalSteps > 0 && totalSteps <= 30 && (
          <div className={styles.tickContainer}>
            {Array.from({ length: totalSteps + 1 }).map((_, i) => (
              <button
                key={i}
                type="button"
                className={`${styles.tick} ${isTour && currentIdx === i ? styles.tickActive : ''}`}
                onClick={() => onSeek(i)}
                title={i === 0 ? 'START' : `STEP ${i}`}
                aria-label={i === 0 ? 'Start' : `Step ${i}`}
              />
            ))}
          </div>
        )}
      </div>

      {/* Readout & Overview Exit Right */}
      <div className={styles.controlsRight}>
        {isTour && (
          <GhostButton onClick={onExitTour} aria-label="Exit tour and return to overview">
            OVERVIEW
          </GhostButton>
        )}

        <div className={styles.readout}>
          STEP <span className={styles.highlightChalk}>{formattedCur}</span> / {formattedTot}
        </div>
      </div>
    </footer>
  );
};
