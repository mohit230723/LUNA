import React, { useEffect } from 'react';
import { Play, Pause, SkipBack, SkipForward } from 'lucide-react';
import { Button } from '../ui/Button';
import { GhostButton } from '../ui/GhostButton';
import { IconButton } from '../ui/IconButton';
import styles from './Scrubber.module.css';

export interface ScrubberProps {
  totalSteps: number;
  currentStepSeq?: number;
  isPlaying: boolean;
  speed: 1 | 2 | 5;
  showAll: boolean;
  onTogglePlay: () => void;
  onStepBack: () => void;
  onStepForward: () => void;
  onSeek: (seq: number) => void;
  onChangeSpeed: (speed: 1 | 2 | 5) => void;
  onToggleShowAll: () => void;
}

export const Scrubber: React.FC<ScrubberProps> = ({
  totalSteps,
  currentStepSeq = 1,
  isPlaying,
  speed,
  showAll,
  onTogglePlay,
  onStepBack,
  onStepForward,
  onSeek,
  onChangeSpeed,
  onToggleShowAll,
}) => {
  // Keyboard navigation shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't intercept if user is typing in an input
      const target = e.target as HTMLElement;
      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') return;

      if (e.code === 'Space') {
        e.preventDefault();
        onTogglePlay();
      } else if (e.key === 'ArrowLeft') {
        e.preventDefault();
        onStepBack();
      } else if (e.key === 'ArrowRight') {
        e.preventDefault();
        onStepForward();
      } else if (e.key === 'Home') {
        e.preventDefault();
        onSeek(1);
      } else if (e.key === 'End') {
        e.preventDefault();
        onSeek(totalSteps);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [totalSteps, onTogglePlay, onStepBack, onStepForward, onSeek]);

  const activeSeq = currentStepSeq ?? 1;

  return (
    <footer className={styles.container} aria-label="Playback scrubber">
      {/* Playback Controls Left */}
      <div className={styles.controlsLeft}>
        <Button
          onClick={onTogglePlay}
          aria-label={isPlaying ? 'Pause trace' : 'Play trace'}
        >
          {isPlaying ? (
            <Pause size={14} strokeWidth={2} fill="var(--color-obsidian)" />
          ) : (
            <Play size={14} strokeWidth={2} fill="var(--color-obsidian)" />
          )}
        </Button>

        <IconButton
          aria-label="Step back"
          onClick={onStepBack}
          disabled={activeSeq <= 1}
        >
          <SkipBack size={16} strokeWidth={1.5} />
        </IconButton>

        <IconButton
          aria-label="Step forward"
          onClick={onStepForward}
          disabled={activeSeq >= totalSteps}
        >
          <SkipForward size={16} strokeWidth={1.5} />
        </IconButton>
      </div>

      {/* Timeline Slider Center */}
      <div className={styles.timelineCenter}>
        <div className={styles.sliderRow}>
          <input
            type="range"
            min={1}
            max={Math.max(1, totalSteps)}
            value={activeSeq}
            onChange={(e) => onSeek(Number(e.target.value))}
            className={styles.slider}
            aria-label="Seek trace timeline step"
          />
        </div>
        {totalSteps > 1 && totalSteps <= 20 && (
          <div className={styles.tickContainer}>
            {Array.from({ length: totalSteps }).map((_, i) => (
              <span
                key={i}
                className={`${styles.tick} ${i + 1 <= activeSeq ? styles.tickActive : ''}`}
              />
            ))}
          </div>
        )}
      </div>

      {/* Speed, Show All, and Readout Right */}
      <div className={styles.controlsRight}>
        <div className={styles.speedGroup} role="group" aria-label="Playback speed">
          {([1, 2, 5] as const).map((s) => (
            <button
              key={s}
              className={`${styles.speedBtn} ${speed === s ? styles.speedActive : ''}`}
              onClick={() => onChangeSpeed(s)}
            >
              {s}X
            </button>
          ))}
        </div>

        <GhostButton
          onClick={onToggleShowAll}
          className={showAll ? styles.showAllActive : ''}
        >
          SHOW ALL
        </GhostButton>

        <div className={styles.readout}>
          STEP <span className={styles.highlightChalk}>{activeSeq}</span> / {totalSteps}
        </div>
      </div>
    </footer>
  );
};
