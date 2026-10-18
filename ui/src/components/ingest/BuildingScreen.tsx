import React from 'react';
import { Check, X } from 'lucide-react';
import { GhostButton } from '../ui/GhostButton';
import type { BuildEvent } from '../../api/contract';
import styles from './BuildingScreen.module.css';

interface BuildingScreenProps {
  events: BuildEvent[];
  buildError?: string;
  isFailed?: boolean;
  onCancel: () => void;
  onRetry: () => void;
  onBackToInputs: () => void;
}

type StageStatus = 'pending' | 'running' | 'done' | 'failed';

export const BuildingScreen: React.FC<BuildingScreenProps> = ({
  events,
  buildError,
  isFailed,
  onCancel,
  onRetry,
  onBackToInputs,
}) => {
  // Derive live counts and status from events
  let parseStatus: StageStatus = 'pending';
  let extractStatus: StageStatus = 'pending';
  let resolveStatus: StageStatus = 'pending';
  let loadStatus: StageStatus = 'pending';

  let parseCount = 'Pending...';
  let extractCount = 'Pending...';
  let resolveCount = 'Pending...';
  let loadCount = 'Pending...';

  let parsedSources = 0;
  let totalSources = 0;

  for (const ev of events) {
    const data = ev.data as Record<string, any>;
    switch (ev.type) {
      case 'source_parsed':
        parseStatus = 'running';
        parsedSources++;
        totalSources = data.total_sources || parsedSources;
        parseCount = `${parsedSources} of ${totalSources} sources`;
        break;
      case 'mapping_planned':
        parseStatus = 'done';
        if (extractStatus === 'pending') extractStatus = 'running';
        break;
      case 'extract_progress':
        parseStatus = 'done';
        extractStatus = 'running';
        extractCount = `${data.done || 0} / ${data.total || 0} chunks · ${data.entities || 0} entities · ${data.dropped || 0} dropped`;
        if (data.done && data.total && data.done >= data.total) {
          extractStatus = 'done';
          resolveStatus = 'running';
          resolveCount = 'Resolving duplicates...';
        }
        break;
      case 'resolve_done':
        parseStatus = 'done';
        extractStatus = 'done';
        resolveStatus = 'done';
        resolveCount = `${data.merged || 0} merged · ${data.possible_duplicates || 0} possible duplicates`;
        loadStatus = 'running';
        loadCount = 'Loading graph to FalkorDB...';
        break;
      case 'load_done':
        parseStatus = 'done';
        extractStatus = 'done';
        resolveStatus = 'done';
        loadStatus = 'done';
        loadCount = `${(data.nodes || 0).toLocaleString()} nodes · ${(data.edges || 0).toLocaleString()} edges`;
        break;
      case 'completed':
        parseStatus = 'done';
        extractStatus = 'done';
        resolveStatus = 'done';
        loadStatus = 'done';
        break;
      case 'failed':
        if (loadStatus === 'running') loadStatus = 'failed';
        else if (resolveStatus === 'running') resolveStatus = 'failed';
        else if (extractStatus === 'running') extractStatus = 'failed';
        else parseStatus = 'failed';
        break;
    }
  }

  // If first event arrived and parse is pending, start parse
  if (events.length > 0 && parseStatus === 'pending') {
    parseStatus = 'running';
    parseCount = 'Reading sources...';
  }

  const renderStatusIcon = (status: StageStatus) => {
    switch (status) {
      case 'done':
        return (
          <div className={`${styles.iconWrap} ${styles.iconDone}`}>
            <Check size={12} strokeWidth={2.5} color="var(--color-signal-white)" />
          </div>
        );
      case 'running':
        return (
          <div className={`${styles.iconWrap} ${styles.iconRunning}`}>
            <div className={styles.pulseDot} />
          </div>
        );
      case 'failed':
        return (
          <div className={`${styles.iconWrap} ${styles.iconFailed}`}>
            <X size={12} strokeWidth={2.5} color="#ff8888" />
          </div>
        );
      case 'pending':
      default:
        return (
          <div className={`${styles.iconWrap} ${styles.iconPending}`}>
            <div className={styles.hollowDot} />
          </div>
        );
    }
  };

  return (
    <div className={styles.container}>
      <div className={styles.content}>
        <div className={styles.header}>
          <h1 className={styles.heading}>Building the context graph</h1>
          <p className={styles.subheading}>This can take a few minutes for long inputs.</p>
        </div>

        {/* Vertical stage list */}
        <div className={styles.stageList}>
          <div className={styles.stageItem}>
            {renderStatusIcon(parseStatus)}
            <div className={styles.stageDetails}>
              <div className={styles.stageName}>PARSE</div>
              <div className={styles.stageCount}>{parseCount}</div>
            </div>
          </div>

          <div className={styles.stageItem}>
            {renderStatusIcon(extractStatus)}
            <div className={styles.stageDetails}>
              <div className={styles.stageName}>EXTRACT</div>
              <div className={styles.stageCount}>{extractCount}</div>
            </div>
          </div>

          <div className={styles.stageItem}>
            {renderStatusIcon(resolveStatus)}
            <div className={styles.stageDetails}>
              <div className={styles.stageName}>RESOLVE</div>
              <div className={styles.stageCount}>{resolveCount}</div>
            </div>
          </div>

          <div className={styles.stageItem}>
            {renderStatusIcon(loadStatus)}
            <div className={styles.stageDetails}>
              <div className={styles.stageName}>LOAD</div>
              <div className={styles.stageCount}>{loadCount}</div>
            </div>
          </div>
        </div>

        {/* Failed state card */}
        {isFailed && (
          <div className={styles.failedCard}>
            <div className={styles.failedTitle}>Build encountered a problem</div>
            <div className={styles.failedReason}>{buildError || 'The build failed.'}</div>
            <div className={styles.failedActions}>
              <GhostButton onClick={onBackToInputs}>BACK TO INPUTS</GhostButton>
              <GhostButton onClick={onRetry}>RETRY</GhostButton>
            </div>
          </div>
        )}

        {/* Cancel button if running */}
        {!isFailed && (
          <div className={styles.footerActions}>
            <GhostButton onClick={onCancel}>CANCEL</GhostButton>
          </div>
        )}
      </div>
    </div>
  );
};
