import React, { useState, useRef, useEffect } from 'react';
import { ArrowUp, Square, SlidersHorizontal } from 'lucide-react';
import { Button } from '../ui/Button';
import { GhostButton } from '../ui/GhostButton';
import { IconButton } from '../ui/IconButton';
import { OptionsPopover } from './OptionsPopover';
import type { SendOptions } from '../../api/contract';
import styles from './Composer.module.css';

export interface ComposerProps {
  onSend: (content: string, options: SendOptions) => void;
  onCancel?: () => void;
  isStreaming?: boolean;
  needsInput?: boolean;
  initialValue?: string;
}

const DEFAULT_OPTIONS: SendOptions = {
  max_hops: 3,
  investigators: 3,
};

export const Composer: React.FC<ComposerProps> = ({
  onSend,
  onCancel,
  isStreaming = false,
  needsInput = false,
  initialValue = '',
}) => {
  const [text, setText] = useState(initialValue);
  const [optionsOpen, setOptionsOpen] = useState(false);
  const [options, setOptions] = useState<SendOptions>(() => {
    try {
      const saved = localStorage.getItem('luna.prefs');
      return saved ? { ...DEFAULT_OPTIONS, ...JSON.parse(saved) } : DEFAULT_OPTIONS;
    } catch {
      return DEFAULT_OPTIONS;
    }
  });

  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Sync initialValue (e.g. from prompt chips)
  useEffect(() => {
    if (initialValue) {
      setText(initialValue);
      if (textareaRef.current) {
        textareaRef.current.focus();
      }
    }
  }, [initialValue]);

  // Auto-grow textarea up to 8 rows (~200px)
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [text]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleSend = () => {
    if (!text.trim() || isStreaming || needsInput || text.length > 8000) return;
    onSend(text.trim(), options);
    setText('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const isOverLimit = text.length > 8000;
  const showCounter = text.length >= 6000;

  return (
    <div className={styles.wrapper}>
      {optionsOpen && (
        <OptionsPopover
          options={options}
          onChange={setOptions}
          onClose={() => setOptionsOpen(false)}
        />
      )}

      <div className={styles.composerCard}>
        <textarea
          ref={textareaRef}
          className={styles.textarea}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about people, links, timelines, or anything in the graph"
          disabled={needsInput || isStreaming}
          rows={1}
          aria-label="Composer question input"
        />

        <div className={styles.bottomRow}>
          <div className={styles.leftControls}>
            <IconButton
              aria-label="Investigation Options"
              onClick={() => setOptionsOpen(!optionsOpen)}
              disabled={needsInput || isStreaming}
            >
              <SlidersHorizontal size={16} strokeWidth={1.5} />
            </IconButton>

            {needsInput && (
              <span className={styles.disabledNotice}>
                Answer the question above to continue.
              </span>
            )}
          </div>

          <div className={styles.rightControls}>
            {showCounter && (
              <span
                className={`${styles.charCounter} ${isOverLimit ? styles.charLimitExceeded : ''}`}
              >
                {isOverLimit
                  ? `Character limit exceeded (${text.length}/8,000)`
                  : `${text.length}/8,000`}
              </span>
            )}

            {isStreaming ? (
              <GhostButton onClick={onCancel} aria-label="Stop run">
                <Square size={12} fill="currentColor" style={{ marginRight: 6 }} />
                STOP
              </GhostButton>
            ) : (
              <Button
                disabled={!text.trim() || isOverLimit || needsInput}
                onClick={handleSend}
                aria-label="Send"
              >
                <ArrowUp size={16} strokeWidth={2} />
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
