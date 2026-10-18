import React, { useState, useRef, useEffect } from 'react';
import {
  FileText,
  FileSpreadsheet,
  Database,
  FileCode,
  Trash2,
  AlertTriangle,
  UploadCloud,
  CheckCircle2,
  Clock,
  XCircle,
} from 'lucide-react';
import { GhostButton } from '../ui/GhostButton';
import { PrimaryButton } from '../ui/Button';
import { Badge } from '../ui/Badge';
import type { CaseDetail, LlmInfo } from '../../api/contract';
import styles from './IngestScreen.module.css';

interface IngestScreenProps {
  caseDetail?: CaseDetail | null;
  llmInfo?: LlmInfo;
  onAddText: (name: string, text: string) => Promise<void>;
  onUploadFiles: (files: File[]) => Promise<void>;
  onRemoveSource: (sourceId: string) => Promise<void>;
  onStartBuild: (acknowledgeRemote: boolean) => Promise<void>;
}

const ALLOWED_EXTS = ['.csv', '.json', '.jsonl', '.xlsx', '.sqlite', '.db', '.txt', '.md'];
const MAX_FILE_SIZE = 20 * 1024 * 1024; // 20 MB

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
}

function getFileIcon(kind: string) {
  switch (kind) {
    case 'csv':
    case 'xlsx':
      return <FileSpreadsheet size={16} strokeWidth={1.5} color="var(--color-chalk)" />;
    case 'sqlite':
      return <Database size={16} strokeWidth={1.5} color="var(--color-chalk)" />;
    case 'json':
    case 'jsonl':
      return <FileCode size={16} strokeWidth={1.5} color="var(--color-chalk)" />;
    case 'text':
    case 'txt':
    case 'md':
    default:
      return <FileText size={16} strokeWidth={1.5} color="var(--color-chalk)" />;
  }
}

export const IngestScreen: React.FC<IngestScreenProps> = ({
  caseDetail,
  llmInfo,
  onAddText,
  onUploadFiles,
  onRemoveSource,
  onStartBuild,
}) => {
  const [activeTab, setActiveTab] = useState<'text' | 'files'>('text');
  const [pastedText, setPastedText] = useState('');
  const [textName, setTextName] = useState('');
  const [isSubmittingText, setIsSubmittingText] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const caseId = caseDetail?.id || 'new';
  const sessionAckKey = `luna.remoteAck.${caseId}`;
  const [remoteAcknowledged, setRemoteAcknowledged] = useState(() => {
    return sessionStorage.getItem(sessionAckKey) === 'true';
  });

  useEffect(() => {
    sessionStorage.setItem(sessionAckKey, remoteAcknowledged ? 'true' : 'false');
  }, [remoteAcknowledged, sessionAckKey]);

  const sources = caseDetail?.sources || [];
  const status = caseDetail?.status || 'draft';
  const isStale = status === 'stale';
  const isFailed = status === 'failed';
  const buildError = caseDetail?.build_error;

  const handleAddText = async () => {
    if (!pastedText.trim() || pastedText.length > 200_000) return;
    setIsSubmittingText(true);
    setUploadError(null);
    try {
      await onAddText(textName.trim() || 'Pasted Scenario', pastedText);
      setPastedText('');
      setTextName('');
    } catch (err: any) {
      setUploadError(err?.message || 'Failed to add text');
    } finally {
      setIsSubmittingText(false);
    }
  };

  const [isUploadingFiles, setIsUploadingFiles] = useState(false);

  const processFiles = async (fileList: FileList | null) => {
    if (!fileList || fileList.length === 0) return;
    setUploadError(null);

    const validFiles: File[] = [];
    for (let i = 0; i < fileList.length; i++) {
      const file = fileList.item(i);
      if (!file) continue;
      const ext = '.' + file.name.split('.').pop()?.toLowerCase();
      if (!ALLOWED_EXTS.includes(ext)) {
        setUploadError(`File '${file.name}' has an unsupported extension. Allowed: ${ALLOWED_EXTS.join(', ')}`);
        return;
      }
      if (file.size > MAX_FILE_SIZE) {
        setUploadError(`File '${file.name}' exceeds the 20 MB size limit.`);
        return;
      }
      validFiles.push(file);
    }

    setIsUploadingFiles(true);
    try {
      await onUploadFiles(validFiles);
    } catch (err: any) {
      setUploadError(err?.message || 'Failed to upload files');
    } finally {
      setIsUploadingFiles(false);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    await processFiles(e.dataTransfer.files);
  };

  const isRemote = llmInfo?.remote ?? false;
  const canBuild =
    sources.length > 0 &&
    !isSubmittingText &&
    !isUploadingFiles &&
    (!isRemote || remoteAcknowledged);

  return (
    <div className={styles.ingestContainer}>
      <div className={styles.mainColumn}>
        <div className={styles.headerSection}>
          <span className={styles.caseLabel}>NEW CASE</span>
          <h1 className={styles.heading}>What should LUNA investigate?</h1>
          <p className={styles.subheading}>
            Paste a situation, upload records, or add a database file. LUNA turns it into a graph you can question.
          </p>
        </div>

        {/* Tab switcher */}
        <div className={styles.segmentedTabs}>
          <button
            type="button"
            className={`${styles.tabButton} ${activeTab === 'text' ? styles.tabButtonActive : ''}`}
            onClick={() => setActiveTab('text')}
          >
            PASTE TEXT
          </button>
          <button
            type="button"
            className={`${styles.tabButton} ${activeTab === 'files' ? styles.tabButtonActive : ''}`}
            onClick={() => setActiveTab('files')}
          >
            UPLOAD FILES
          </button>
        </div>

        {/* Tab 1: Paste Text */}
        {activeTab === 'text' && (
          <div className={styles.tabContent}>
            <div className={styles.inputGroup}>
              <input
                type="text"
                placeholder="Name this input (optional)"
                className={styles.nameInput}
                value={textName}
                onChange={(e) => setTextName(e.target.value)}
              />
              <textarea
                className={styles.textArea}
                rows={8}
                placeholder="Describe the situation, paste emails, notes, transcripts, or a long brief..."
                value={pastedText}
                onChange={(e) => setPastedText(e.target.value)}
                maxLength={200_000}
              />
              <div className={styles.textFooter}>
                <span className={styles.counter}>{pastedText.length.toLocaleString()} / 200,000</span>
                <GhostButton
                  onClick={handleAddText}
                  disabled={!pastedText.trim() || pastedText.length > 200_000 || isSubmittingText}
                >
                  {isSubmittingText ? 'ADDING...' : 'ADD TO CASE'}
                </GhostButton>
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: Upload Files */}
        {activeTab === 'files' && (
          <div className={styles.tabContent}>
            <div
              className={`${styles.dropzone} ${isDragging ? styles.dropzoneActive : ''}`}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
            >
              <input
                type="file"
                ref={fileInputRef}
                style={{ display: 'none' }}
                multiple
                accept=".csv,.json,.jsonl,.xlsx,.sqlite,.db,.txt,.md"
                onChange={(e) => processFiles(e.target.files)}
              />
              <UploadCloud size={32} strokeWidth={1.5} color="var(--color-smoke)" />
              <div className={styles.dropText}>Drop files here or choose files</div>
              <div className={styles.dropSub}>CSV, JSON, JSONL, XLSX, SQLite, TXT, MD · up to 20 MB each</div>
              <div style={{ marginTop: '16px' }}>
                <GhostButton
                  onClick={(e) => {
                    e.stopPropagation();
                    fileInputRef.current?.click();
                  }}
                >
                  CHOOSE FILES
                </GhostButton>
              </div>
            </div>
          </div>
        )}

        {uploadError && <div className={styles.errorNotice}>{uploadError}</div>}

        {/* Sources List */}
        <div className={styles.sourcesSection}>
          <div className={styles.sourcesHeader}>SOURCES ({sources.length})</div>

          {sources.length === 0 ? (
            <div className={styles.emptySources}>No inputs yet.</div>
          ) : (
            <div className={styles.sourcesList}>
              {sources.map((src) => (
                <div key={src.id} className={styles.sourceRow}>
                  <div className={styles.sourceIcon}>{getFileIcon(src.kind)}</div>
                  <div className={styles.sourceInfo}>
                    <span className={styles.sourceName}>{src.name}</span>
                    <span className={styles.kindTag}>{src.kind.toUpperCase()}</span>
                  </div>
                  <div className={styles.sourceBytes}>{formatBytes(src.bytes)}</div>
                  <div className={styles.sourceStatus}>
                    {src.status === 'pending' && (
                      <span className={styles.statusPending}>
                        <Clock size={12} strokeWidth={1.5} /> PENDING
                      </span>
                    )}
                    {src.status === 'parsed' && (
                      <span className={styles.statusParsed}>
                        <CheckCircle2 size={12} strokeWidth={1.5} /> PARSED
                      </span>
                    )}
                    {src.status === 'failed' && (
                      <span className={styles.statusFailed} title={src.error || 'Parse failed'}>
                        <XCircle size={12} strokeWidth={1.5} /> FAILED
                      </span>
                    )}
                  </div>
                  <button
                    type="button"
                    className={styles.removeBtn}
                    onClick={() => onRemoveSource(src.id)}
                    title="Remove source"
                    aria-label={`Remove source ${src.name}`}
                  >
                    <Trash2 size={14} strokeWidth={1.5} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Stale Banner */}
        {isStale && (
          <div className={styles.staleBanner}>
            <AlertTriangle size={16} strokeWidth={1.5} color="var(--color-compass-gold)" />
            <span>Sources changed since the last build. Rebuild to include them.</span>
          </div>
        )}

        {/* Failed Banner */}
        {isFailed && (
          <div className={styles.failedBanner}>
            <div className={styles.failedText}>
              <strong>Build Failed:</strong> {buildError || 'An error occurred during build.'}
            </div>
          </div>
        )}

        {/* Model Notice */}
        <div className={styles.modelNoticeContainer}>
          {isRemote ? (
            <div className={styles.remoteNoticeCard}>
              <div className={styles.remoteNoticeText}>
                Your inputs will be sent to <strong>{llmInfo?.provider}</strong> ({llmInfo?.model}) to extract the graph.
              </div>
              <label className={styles.checkboxLabel}>
                <input
                  type="checkbox"
                  checked={remoteAcknowledged}
                  onChange={(e) => setRemoteAcknowledged(e.target.checked)}
                />
                <span>I understand</span>
              </label>
            </div>
          ) : (
            <div className={styles.localBadge}>
              <Badge hasPulseDot size="compact">
                RUNS LOCALLY · {llmInfo?.model || 'Ollama'}
              </Badge>
            </div>
          )}
        </div>

        {/* Primary Action Button */}
        <div className={styles.primaryAction}>
          <PrimaryButton onClick={() => onStartBuild(remoteAcknowledged)} disabled={!canBuild}>
            BUILD CONTEXT GRAPH ↗
          </PrimaryButton>
        </div>
      </div>

      {/* Right Column: Explanatory Panel */}
      <aside className={styles.rightPanel}>
        <div className={styles.panelCard}>
          <div className={styles.panelLabel}>WHAT HAPPENS NEXT</div>
          <ol className={styles.nextStepsList}>
            <li>
              <div className={styles.stepNum}>01</div>
              <div className={styles.stepBody}>
                <strong>PARSE</strong>
                <p>Reads your text and files.</p>
              </div>
            </li>
            <li>
              <div className={styles.stepNum}>02</div>
              <div className={styles.stepBody}>
                <strong>EXTRACT</strong>
                <p>
                  A model finds people, organizations, accounts, places, events, and the links between them, and checks each one against the source text.
                </p>
              </div>
            </li>
            <li>
              <div className={styles.stepNum}>03</div>
              <div className={styles.stepBody}>
                <strong>RESOLVE</strong>
                <p>Merges duplicate names and flags possible matches instead of guessing.</p>
              </div>
            </li>
            <li>
              <div className={styles.stepNum}>04</div>
              <div className={styles.stepBody}>
                <strong>LOAD</strong>
                <p>Writes the graph to FalkorDB. Then you can ask questions.</p>
              </div>
            </li>
          </ol>
        </div>
      </aside>
    </div>
  );
};
