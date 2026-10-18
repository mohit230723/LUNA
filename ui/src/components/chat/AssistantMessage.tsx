import React from 'react';
import { Badge } from '../ui/Badge';
import { RunCard } from './RunCard';
import { PlanBlock } from './blocks/PlanBlock';
import { SkillsBlock } from './blocks/SkillsBlock';
import { FindingsBlock } from './blocks/FindingsBlock';
import { NeedsInputBlock } from './blocks/NeedsInputBlock';
import { WarningBlock } from './blocks/WarningBlock';
import { AnswerBlock } from './blocks/AnswerBlock';
import { GraphSummaryBlock } from './blocks/GraphSummaryBlock';
import type { Message, AgentInfo, GraphStats } from '../../api/contract';
import type { StageState } from '../../state/stages';
import type { ElementsDefinition } from 'cytoscape';
import styles from './AssistantMessage.module.css';

export interface AssistantMessageProps {
  message: Message;
  stages?: Record<string, StageState> | StageState[];
  agents?: AgentInfo[];
  previewElements?: ElementsDefinition;
  entityNames?: Record<string, string>;
  onCancel?: () => void;
  onViewTrace?: (runId?: string) => void;
  onOpenWhy?: (target?: string) => void;
  onCidClick?: (cid: string) => void;
  onAnswer?: (choice: string) => void;
  onSelectEntity?: (name: string) => void;
}

export const AssistantMessage: React.FC<AssistantMessageProps> = ({
  message,
  stages,
  agents = [],
  previewElements,
  entityNames = {},
  onCancel,
  onViewTrace,
  onOpenWhy,
  onCidClick,
  onAnswer,
  onSelectEntity,
}) => {
  // Check if message is purely a graph summary
  const hasGraphSummary = message.blocks.some((b) => b.type === 'graph_summary');

  return (
    <div className={styles.wrapper}>
      {/* Header line with LUNA label */}
      {!hasGraphSummary && (
        <div className={styles.headerLine}>
          <span className={styles.brandLabel}>LUNA</span>
          <Badge size="compact">LLM</Badge>
        </div>
      )}

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
            case 'graph_summary':
              return (
                <GraphSummaryBlock
                  key={idx}
                  data={block.data as GraphStats}
                  onSelectEntity={onSelectEntity}
                />
              );

            case 'text':
              return (
                <div key={idx} style={{ marginBottom: 16 }}>
                  {block.data.markdown}
                </div>
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
                  model={block.data.model}
                  entityNames={entityNames}
                  onViewTrace={() => onViewTrace && onViewTrace(message.run_id)}
                  onOpenWhy={() => onOpenWhy && onOpenWhy()}
                  onCidClick={onCidClick}
                  previewElements={previewElements}
                />
              );

            default:
              return null;
          }
        })}
      </div>
    </div>
  );
};
