import React, { useState } from 'react';
import { GhostButton } from '../../ui/GhostButton';
import { Button } from '../../ui/Button';
import styles from './blocks.module.css';

export interface NeedsInputBlockProps {
  question: string;
  options: string[];
  allowFreeText?: boolean;
  onAnswer: (choice: string) => void;
  disabled?: boolean;
}

export const NeedsInputBlock: React.FC<NeedsInputBlockProps> = ({
  question,
  options,
  allowFreeText = false,
  onAnswer,
  disabled = false,
}) => {
  const [freeText, setFreeText] = useState('');

  const handleFreeTextSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (freeText.trim()) {
      onAnswer(freeText.trim());
    }
  };

  return (
    <div className={styles.needsInputCard}>
      <div className={styles.blockHeader}>
        <h4 className={styles.blockTitle}>NEEDS INPUT</h4>
      </div>

      <p style={{ margin: 0, fontSize: '15px', color: 'var(--color-chalk)', lineHeight: 1.5 }}>
        {question}
      </p>

      <div className={styles.optionsRow}>
        {options.map((opt) => (
          <GhostButton
            key={opt}
            disabled={disabled}
            onClick={() => onAnswer(opt)}
          >
            {opt}
          </GhostButton>
        ))}
      </div>

      {allowFreeText && (
        <form onSubmit={handleFreeTextSubmit} style={{ display: 'flex', gap: 8, marginTop: 8 }}>
          <input
            type="text"
            value={freeText}
            onChange={(e) => setFreeText(e.target.value)}
            placeholder="Or type custom answer..."
            disabled={disabled}
            style={{
              backgroundColor: 'var(--color-obsidian)',
              border: '1px solid var(--color-graphite)',
              borderRadius: 'var(--radius-card)',
              padding: '8px 12px',
              color: 'var(--color-chalk)',
              fontFamily: 'var(--font-primary)',
              fontSize: '13px',
              flex: 1,
              outline: 'none',
            }}
          />
          <Button type="submit" disabled={disabled || !freeText.trim()}>
            SUBMIT
          </Button>
        </form>
      )}
    </div>
  );
};
