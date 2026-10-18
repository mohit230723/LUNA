import React, { useRef, useEffect, useState } from 'react';
import { ArrowDown } from 'lucide-react';
import { Badge } from '../ui/Badge';
import { GhostButton } from '../ui/GhostButton';
import { UserMessage } from './UserMessage';
import { AssistantMessage } from './AssistantMessage';
import { Composer } from './Composer';
import type { Message, SendOptions, ActionResult, AgentInfo } from '../../api/contract';
import type { StageState } from '../../state/stages';
import type { ElementsDefinition } from 'cytoscape';
import styles from './Thread.module.css';

export interface ThreadProps {
  messages: Message[];
  activeStages?: Record<string, StageState> | StageState[];
  activeAgents?: AgentInfo[];
  previewElements?: ElementsDefinition;
  isStreaming?: boolean;
  connectionState?: 'open' | 'reconnecting' | 'closed';
  composerInitialPrompt?: string;
  onSend: (content: string, options: SendOptions) => void;
  onCancel?: () => void;
  onViewTrace?: (runId?: string) => void;
  onOpenWhy?: (target?: string) => void;
  onCidClick?: (cid: string) => void;
  onAnswer?: (choice: string) => void;
  onApproveAction?: (actionId: string, approver: string) => Promise<ActionResult>;
  onRejectAction?: (actionId: string, approver: string, reason: string) => Promise<void>;
  onSelectFile?: (path: string) => void;
  filePreview?: { path: string; content: string; truncated: boolean };
  onSimulateDisconnect?: () => void;
  onToggleFailAll?: () => void;
  onToggleFailPartial?: () => void;
}

const EXAMPLE_PROMPTS = [
  {
    text: 'Who is connected to the fraud involving customer cust-000?',
    pack: 'INVESTIGATE',
  },
  {
    text: 'Is customer cust-010 part of a fraud ring?',
    pack: 'INVESTIGATE',
  },
  {
    text: 'Build a todo app: React + Vite frontend, Express backend, Postgres database.',
    pack: 'BUILD',
  },
  {
    text: 'Build a notes API with Fastify and SQLite.',
    pack: 'BUILD',
  },
];

export const Thread: React.FC<ThreadProps> = ({
  messages,
  activeStages,
  activeAgents,
  previewElements,
  isStreaming = false,
  connectionState = 'open',
  composerInitialPrompt = '',
  onSend,
  onCancel,
  onViewTrace,
  onOpenWhy,
  onCidClick,
  onAnswer,
  onApproveAction,
  onRejectAction,
  onSelectFile,
  filePreview,
  onSimulateDisconnect,
  onToggleFailAll,
  onToggleFailPartial,
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

  // Scroll to bottom on messages/events change unless user scrolled up
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

  const handleChipClick = (prompt: string) => {
    setComposerText(prompt);
  };

  // Check if current run is in needs_input state
  const lastMsg = messages[messages.length - 1];
  const isNeedsInput = lastMsg?.status === 'needs_input';

  return (
    <div className={styles.threadContainer}>
      {/* Offline / Reconnecting banner */}
      {connectionState === 'reconnecting' && (
        <div className={styles.offlineBanner}>
          Connection lost. Reconnecting...
        </div>
      )}

      {/* Main scrollable message area */}
      <div
        ref={scrollAreaRef}
        className={styles.scrollArea}
        onScroll={handleScroll}
      >
        <div className={styles.innerColumn}>
          {messages.length === 0 ? (
            <div className={styles.emptyStateContainer}>
              <h2 className={styles.emptyHeading}>What should the agents work on?</h2>
              <p className={styles.emptySubline}>
                Ask a question about connected data, or describe something to build.
              </p>

              <div className={styles.chipsGrid}>
                {EXAMPLE_PROMPTS.map((item) => (
                  <div
                    key={item.text}
                    className={styles.promptChip}
                    onClick={() => handleChipClick(item.text)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && handleChipClick(item.text)}
                  >
                    <Badge size="compact">{item.pack}</Badge>
                    <p className={styles.chipText}>{item.text}</p>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            messages.map((msg, index) => {
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
                  onCancel={onCancel}
                  onViewTrace={onViewTrace}
                  onOpenWhy={onOpenWhy}
                  onCidClick={onCidClick}
                  onAnswer={onAnswer}
                  onApproveAction={onApproveAction}
                  onRejectAction={onRejectAction}
                  onSelectFile={onSelectFile}
                  filePreview={filePreview}
                />
              );
            })
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
            onSimulateDisconnect={onSimulateDisconnect}
            onToggleFailAll={onToggleFailAll}
            onToggleFailPartial={onToggleFailPartial}
          />
        </div>
      </div>
    </div>
  );
};
