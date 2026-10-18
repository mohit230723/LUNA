import React, { useRef, useEffect, useState } from 'react';
import { ArrowDown, Plus } from 'lucide-react';
import { GhostButton } from '../ui/GhostButton';
import { UserMessage } from './UserMessage';
import { AssistantMessage } from './AssistantMessage';
import { Composer } from './Composer';
import type { Message, SendOptions, AgentInfo, GraphStats } from '../../api/contract';
import type { StageState } from '../../state/stages';
import type { ElementsDefinition } from 'cytoscape';
import styles from './Thread.module.css';

export interface ThreadProps {
  messages: Message[];
  graphStats?: GraphStats | null;
  suggestions?: string[];
  entityNames?: Record<string, string>;
  activeStages?: Record<string, StageState> | StageState[];
  activeAgents?: AgentInfo[];
  previewElements?: ElementsDefinition;
  isStreaming?: boolean;
  connectionState?: 'open' | 'reconnecting' | 'closed';
  composerInitialPrompt?: string;
  onSend: (content: string, options: SendOptions) => void;
  onCancel?: () => void;
  onAddSource?: () => void;
  onViewTrace?: (runId?: string) => void;
  onOpenWhy?: (target?: string) => void;
  onCidClick?: (cid: string) => void;
  onAnswer?: (choice: string) => void;
}

export const Thread: React.FC<ThreadProps> = ({
  messages,
  graphStats,
  suggestions = [],
  entityNames = {},
  activeStages,
  activeAgents,
  previewElements,
  isStreaming = false,
  connectionState = 'open',
  composerInitialPrompt = '',
  onSend,
  onCancel,
  onAddSource,
  onViewTrace,
  onOpenWhy,
  onCidClick,
  onAnswer,
}) => {
  const [composerText, setComposerText] = useState(composerInitialPrompt);
  const [showJumpToBottom, setShowJumpToBottom] = useState(false);
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const userScrolledUpRef = useRef(false);

  useEffect(() => {
    if (composerInitialPrompt) {
      setComposerText(composerInitialPrompt);
    }
  }, [composerInitialPrompt]);

  const scrollToBottom = (behavior: ScrollBehavior = 'smooth') => {
    if (scrollAreaRef.current) {
      if (typeof scrollAreaRef.current.scrollTo === 'function') {
        scrollAreaRef.current.scrollTo({
          top: scrollAreaRef.current.scrollHeight,
          behavior,
        });
      } else {
        scrollAreaRef.current.scrollTop = scrollAreaRef.current.scrollHeight;
      }
      userScrolledUpRef.current = false;
      setShowJumpToBottom(false);
    }
  };

  useEffect(() => {
    if (!userScrolledUpRef.current) {
      scrollToBottom('smooth');
    }
  }, [messages, activeStages]);

  const handleScroll = () => {
    if (!scrollAreaRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollAreaRef.current;
    const distanceToBottom = scrollHeight - (scrollTop + clientHeight);

    if (distanceToBottom > 150) {
      userScrolledUpRef.current = true;
      setShowJumpToBottom(true);
    } else {
      userScrolledUpRef.current = false;
      setShowJumpToBottom(false);
    }
  };

  const handleSuggestionClick = (prompt: string) => {
    setComposerText(prompt);
  };

  const handleSelectEntity = (name: string) => {
    setComposerText(`Tell me about ${name}`);
  };

  const lastMsg = messages[messages.length - 1];
  const isNeedsInput = lastMsg?.status === 'needs_input';

  // Check if thread has user questions yet (ignoring graph summary message)
  const userQuestions = messages.filter((m) => m.role === 'user');
  const hasUserAsked = userQuestions.length > 0;

  return (
    <div className={styles.threadContainer}>
      {/* Top Strip */}
      <div className={styles.topStrip}>
        <div className={styles.topStripText}>
          CONTEXT GRAPH · {(graphStats?.nodes || 0).toLocaleString()} nodes ·{' '}
          {(graphStats?.edges || 0).toLocaleString()} edges ·{' '}
          {(graphStats?.sources || 0).toLocaleString()} sources
        </div>
        {onAddSource && (
          <GhostButton onClick={onAddSource} className={styles.addSourceBtn}>
            <Plus size={14} strokeWidth={1.5} />
            ADD SOURCE
          </GhostButton>
        )}
      </div>

      {/* Offline / Reconnecting banner */}
      {connectionState === 'reconnecting' && (
        <div className={styles.offlineBanner}>
          Connection lost. Reconnecting...
        </div>
      )}

      {/* Main scrollable message area */}
      <div ref={scrollAreaRef} className={styles.scrollArea} onScroll={handleScroll}>
        <div className={styles.innerColumn}>
          {messages.map((msg, index) => {
            const isLast = index === messages.length - 1;
            if (msg.role === 'user') {
              const textContent =
                msg.blocks.find((b) => b.type === 'text')?.data.markdown || '';
              return (
                <UserMessage
                  key={msg.id}
                  content={textContent}
                  createdAt={msg.created_at}
                />
              );
            }

            return (
              <AssistantMessage
                key={msg.id}
                message={msg}
                stages={isLast ? activeStages : undefined}
                agents={isLast ? activeAgents : undefined}
                previewElements={previewElements}
                entityNames={entityNames}
                onCancel={onCancel}
                onViewTrace={onViewTrace}
                onOpenWhy={onOpenWhy}
                onCidClick={onCidClick}
                onAnswer={onAnswer}
                onSelectEntity={handleSelectEntity}
              />
            );
          })}

          {/* Dynamic Suggestion Chips when no questions have been asked yet */}
          {!hasUserAsked && suggestions.length > 0 && (
            <div className={styles.suggestionsSection}>
              <div className={styles.suggestionsHeader}>SUGGESTED QUESTIONS</div>
              <div className={styles.suggestionsGrid}>
                {suggestions.map((item, idx) => (
                  <button
                    key={idx}
                    type="button"
                    className={styles.suggestionChip}
                    onClick={() => handleSuggestionClick(item)}
                  >
                    {item}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Jump to latest button */}
      {showJumpToBottom && (
        <div className={styles.jumpButton}>
          <GhostButton onClick={() => scrollToBottom('smooth')}>
            <ArrowDown size={14} style={{ marginRight: 6 }} />
            JUMP TO LATEST
          </GhostButton>
        </div>
      )}

      {/* Composer footer */}
      <div className={styles.composerFooter}>
        <div className={styles.composerInner}>
          <Composer
            initialValue={composerText}
            onSend={(content, opts) => {
              setComposerText('');
              onSend(content, opts);
            }}
            onCancel={onCancel}
            isStreaming={isStreaming}
            needsInput={isNeedsInput}
          />
        </div>
      </div>
    </div>
  );
};
