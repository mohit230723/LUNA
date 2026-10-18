import React from 'react';
import { Plus, Minus } from 'lucide-react';
import { GhostButton } from '../ui/GhostButton';
import type { SendOptions } from '../../api/contract';
import styles from './OptionsPopover.module.css';

export interface OptionsPopoverProps {
  options: SendOptions;
  onChange: (newOpts: SendOptions) => void;
  onSimulateDisconnect?: () => void;
  onToggleFailAll?: () => void;
  onToggleFailPartial?: () => void;
  onClose: () => void;
}

export const OptionsPopover: React.FC<OptionsPopoverProps> = ({
  options,
  onChange,
  onSimulateDisconnect,
  onToggleFailAll,
  onToggleFailPartial,
}) => {
  const isDev = import.meta.env.DEV || window.location.search.includes('dev=1');

  const update = (partial: Partial<SendOptions>) => {
    const next = { ...options, ...partial };
    onChange(next);
    localStorage.setItem('luna.prefs', JSON.stringify(next));
  };

  return (
    <div className={styles.popover} role="dialog" aria-label="Run Options">
      {/* Pack Selection */}
      <div className={styles.row}>
        <span className={styles.label}>PACK</span>
        <div className={styles.segmented}>
          {(['auto', 'investigate', 'build'] as const).map((p) => (
            <button
              key={p}
              type="button"
              className={`${styles.segmentBtn} ${options.pack === p ? styles.segmentBtnActive : ''}`}
              onClick={() => update({ pack: p })}
            >
              {p.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      {/* Execution Mode */}
      <div className={styles.row}>
        <span className={styles.label}>MODE</span>
        <div className={styles.segmented}>
          {(['scripted', 'live'] as const).map((m) => (
            <button
              key={m}
              type="button"
              className={`${styles.segmentBtn} ${options.mode === m ? styles.segmentBtnActive : ''}`}
              onClick={() => update({ mode: m })}
            >
              {m.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      {/* Strict LLM Switch */}
      <div className={styles.row}>
        <div className={styles.switchRow}>
          <span className={styles.label}>STRICT LLM</span>
          <button
            type="button"
            className={`${styles.segmentBtn} ${options.strict_llm ? styles.segmentBtnActive : ''}`}
            style={{ borderRadius: 4, padding: '4px 8px', border: '1px solid var(--color-graphite)' }}
            onClick={() => update({ strict_llm: !options.strict_llm })}
          >
            {options.strict_llm ? 'ON' : 'OFF'}
          </button>
        </div>
        <p className={styles.subtext}>
          When on, the run fails instead of falling back to rules.
        </p>
      </div>

      {/* Parallel Agents */}
      <div className={styles.row}>
        <span className={styles.label}>PARALLEL AGENTS</span>
        <div className={styles.stepper}>
          <button
            type="button"
            className={styles.stepperBtn}
            onClick={() => update({ parallel: Math.max(1, options.parallel - 1) })}
            aria-label="Decrease parallel agents"
          >
            <Minus size={14} />
          </button>
          <span className={styles.stepperValue}>{options.parallel}</span>
          <button
            type="button"
            className={styles.stepperBtn}
            onClick={() => update({ parallel: Math.min(5, options.parallel + 1) })}
            aria-label="Increase parallel agents"
          >
            <Plus size={14} />
          </button>
        </div>
      </div>

      {/* Dev-only controls */}
      {isDev && (
        <>
          <hr className={styles.devDivider} />
          <span className={styles.label} style={{ color: 'var(--color-ash)' }}>
            DEV DIAGNOSTICS
          </span>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {onSimulateDisconnect && (
              <GhostButton onClick={onSimulateDisconnect}>
                SIMULATE DISCONNECT
              </GhostButton>
            )}
            {onToggleFailPartial && (
              <GhostButton onClick={onToggleFailPartial}>
                TOGGLE PARTIAL FAIL
              </GhostButton>
            )}
            {onToggleFailAll && (
              <GhostButton onClick={onToggleFailAll}>
                TOGGLE ALL FAIL
              </GhostButton>
            )}
          </div>
        </>
      )}
    </div>
  );
};
