import React from 'react';
import { Plus, Minus } from 'lucide-react';
import type { SendOptions } from '../../api/contract';
import styles from './OptionsPopover.module.css';

export interface OptionsPopoverProps {
  options: SendOptions;
  onChange: (newOpts: SendOptions) => void;
  onClose?: () => void;
}

export const OptionsPopover: React.FC<OptionsPopoverProps> = ({
  options,
  onChange,
}) => {
  const update = (partial: Partial<SendOptions>) => {
    const next = { ...options, ...partial };
    onChange(next);
    localStorage.setItem('luna.prefs', JSON.stringify(next));
  };

  const maxHops = options.max_hops ?? 3;
  const investigators = options.investigators ?? 3;

  return (
    <div className={styles.popover} role="dialog" aria-label="Investigation Options">
      {/* Max Hops */}
      <div className={styles.row}>
        <span className={styles.label}>MAX HOPS</span>
        <div className={styles.stepper}>
          <button
            type="button"
            className={styles.stepperBtn}
            onClick={() => update({ max_hops: Math.max(1, maxHops - 1) })}
            aria-label="Decrease max hops"
            disabled={maxHops <= 1}
          >
            <Minus size={14} />
          </button>
          <span className={styles.stepperValue}>{maxHops}</span>
          <button
            type="button"
            className={styles.stepperBtn}
            onClick={() => update({ max_hops: Math.min(5, maxHops + 1) })}
            aria-label="Increase max hops"
            disabled={maxHops >= 5}
          >
            <Plus size={14} />
          </button>
        </div>
      </div>

      {/* Investigators */}
      <div className={styles.row}>
        <span className={styles.label}>INVESTIGATORS</span>
        <div className={styles.stepper}>
          <button
            type="button"
            className={styles.stepperBtn}
            onClick={() => update({ investigators: Math.max(1, investigators - 1) })}
            aria-label="Decrease investigators"
            disabled={investigators <= 1}
          >
            <Minus size={14} />
          </button>
          <span className={styles.stepperValue}>{investigators}</span>
          <button
            type="button"
            className={styles.stepperBtn}
            onClick={() => update({ investigators: Math.min(4, investigators + 1) })}
            aria-label="Increase investigators"
            disabled={investigators >= 4}
          >
            <Plus size={14} />
          </button>
        </div>
      </div>
    </div>
  );
};
