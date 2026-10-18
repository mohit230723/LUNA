import React from 'react';
import { Badge } from '../ui/Badge';
import { RunCard } from './RunCard';
import { RoutingBlock } from './blocks/RoutingBlock';
import { PlanBlock } from './blocks/PlanBlock';
import { SkillsBlock } from './blocks/SkillsBlock';
import { FindingsBlock } from './blocks/FindingsBlock';
import { FilesBlock } from './blocks/FilesBlock';
import { ActionRequestBlock } from './blocks/ActionRequestBlock';
import { NeedsInputBlock } from './blocks/NeedsInputBlock';
import { WarningBlock } from './blocks/WarningBlock';
import { AnswerBlock } from './blocks/AnswerBlock';
import { UnsupportedBlock } from './blocks/UnsupportedBlock';
import type { Message, Backend, ActionResult, AgentInfo } from '../../api/contract';
import type { StageState } from '../../state/stages';
import type { ElementsDefinition } from 'cytoscape';
import styles from './AssistantMessage.module.css';

export interface AssistantMessageProps {
  message: Message;
  stages?: Record<string, StageState> | StageState[];
  agents?: AgentInfo[];
  previewElements?: ElementsDefinition;
  onCancel?: () => void;
  onViewTrace?: (runId?: string) => void;
  onOpenWhy?: (target?: string) => void;
  onCidClick?: (cid: string) => void;
  onAnswer?: (choice: string) => void;
  onApproveAction?: (actionId: string, approver: string) => Promise<ActionResult>;
  onRejectAction?: (actionId: string, approver: string, reason: string) => Promise<void>;
  onSelectFile?: (path: string) => void;
  filePreview?: { path: string; content: string; truncated: boolean };
}

export const AssistantMessage: React.FC<AssistantMessageProps> = ({
  message,
  stages,
  agents = [],
  previewElements,
  onCancel,
  onViewTrace,
  onOpenWhy,
  onCidClick,
  onAnswer,
  onApproveAction,
  onRejectAction,
  onSelectFile,
  filePreview,
}) => {
  // Collect unique backends present in message blocks
  const backends = Array.from(
    new Set(
      message.blocks
        .map((b) => {
          if ('backend' in b.data && typeof b.data.backend === 'string') {
            return b.data.backend as Backend;
          }
          return null;
        })
        .filter((b): b is Backend => b !== null)
    )
  );

  return (
    <div className={styles.wrapper}>
      {/* Header line with LUNA label + backend badges */}
      <div className={styles.headerLine}>
        <span className={styles.brandLabel}>LUNA</span>
        {backends.map((backend) => (
          <Badge key={backend} size="compact">
            {backend.toUpperCase()}
          </Badge>
        ))}
      </div>

      <div className={styles.blocksStack}>
        {/* RunCard if stages provided */}
        {stages && (
          <RunCard
            stages={stages}
            agents={agents}
            status={message.status}
            onCancel={onCancel}
          />
        )}

        {/* Render stack of blocks */}
        {message.blocks.map((block, idx) => {
          switch (block.type) {
            case 'text':
              return (
                <div key={idx} style={{ marginBottom: 16 }}>
                  {block.data.markdown}
                </div>
              );

            case 'routing':
              return (
                <RoutingBlock
                  key={idx}
                  pack={block.data.pack}
                  intent={block.data.intent}
                  confidence={block.data.confidence}
                  backend={block.data.backend}
                />
              );

            case 'plan':
              return (
                <PlanBlock
                  key={idx}
                  subtasks={block.data.subtasks}
                  components={block.data.components}
                  contracts={block.data.contracts}
                  onViewBlueprint={() => onViewTrace && onViewTrace(message.run_id)}
                />
              );

            case 'skills':
              return <SkillsBlock key={idx} assignments={block.data.assignments} />;

            case 'findings':
              return (
                <FindingsBlock
                  key={idx}
                  items={block.data.items}
                  onOpenWhy={onOpenWhy}
                />
              );

            case 'files':
              return (
                <FilesBlock
                  key={idx}
                  tree={block.data.tree}
                  zipUrl={block.data.zip_url}
                  contractsImplemented={block.data.contracts_implemented}
                  contractsTotal={block.data.contracts_total}
                  openViolations={block.data.open_violations}
                  previewContent={filePreview}
                  onSelectFile={onSelectFile}
                />
              );

            case 'action_request':
              return (
                <ActionRequestBlock
                  key={idx}
                  action={block.data}
                  onApprove={(approver) =>
                    onApproveAction
                      ? onApproveAction(block.data.action_id, approver)
                      : Promise.resolve({ ok: true })
                  }
                  onReject={(approver, reason) =>
                    onRejectAction
                      ? onRejectAction(block.data.action_id, approver, reason)
                      : Promise.resolve()
                  }
                  onFocusNode={onCidClick}
                />
              );

            case 'needs_input':
              return (
                <NeedsInputBlock
                  key={idx}
                  question={block.data.question}
                  options={block.data.options}
                  allowFreeText={block.data.allow_free_text}
                  onAnswer={(choice) => onAnswer && onAnswer(choice)}
                />
              );

            case 'warning':
              return <WarningBlock key={idx} text={block.data.text} />;

            case 'answer':
              return (
                <AnswerBlock
                  key={idx}
                  text={block.data.text}
                  citedCids={block.data.cited_cids}
                  backend={block.data.backend}
                  onViewTrace={() => onViewTrace && onViewTrace(message.run_id)}
                  onOpenWhy={() => onOpenWhy && onOpenWhy()}
                  onCidClick={onCidClick}
                  previewElements={previewElements}
                />
              );

            default:
              return <UnsupportedBlock key={idx} type={(block as any).type || 'unknown'} />;
          }
        })}
      </div>
    </div>
  );
};
