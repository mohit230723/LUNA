import React from 'react';
import { GhostButton } from '../ui/GhostButton';
import type { LlmInfo } from '../../api/contract';
import styles from './LlmBlockerCard.module.css';

interface LlmBlockerCardProps {
  llmInfo?: LlmInfo;
  onCheckAgain: () => void;
}

export const LlmBlockerCard: React.FC<LlmBlockerCardProps> = ({ llmInfo, onCheckAgain }) => {
  return (
    <div className={styles.container}>
      <div className={styles.card}>
        <h1 className={styles.heading}>No language model is connected.</h1>
        <p className={styles.text}>
          LUNA needs a language model to build and question a context graph. Set these in your .env file and restart the API:
        </p>

        <div className={styles.codeBox}>
          <code>
            <span className={styles.comment}># LLM provider: ollama | openai_compatible | anthropic | gemini</span>
            {'\n'}
            <span className={styles.key}>LUNA_LLM_PROVIDER</span>=ollama
            {'\n\n'}
            <span className={styles.comment}># Model identifier for extraction and investigation</span>
            {'\n'}
            <span className={styles.key}>LUNA_LLM_MODEL</span>=qwen2.5:7b
            {'\n\n'}
            <span className={styles.comment}># Base URL (default: http://localhost:11434 for Ollama)</span>
            {'\n'}
            <span className={styles.key}>LUNA_LLM_BASE_URL</span>=http://localhost:11434
            {'\n\n'}
            <span className={styles.comment}># API key for remote providers (not needed for local Ollama)</span>
            {'\n'}
            <span className={styles.key}>LUNA_LLM_API_KEY</span>=your_api_key_here
          </code>
        </div>

        {llmInfo && !llmInfo.reachable && (
          <div className={styles.detailText}>
            Configured provider: <span className={styles.mono}>{llmInfo.provider || 'unknown'}</span> · Model: <span className={styles.mono}>{llmInfo.model || 'unknown'}</span> (unreachable)
          </div>
        )}

        <div className={styles.actions}>
          <GhostButton onClick={onCheckAgain}>CHECK AGAIN</GhostButton>
        </div>
      </div>
    </div>
  );
};
