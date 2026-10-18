import React, { useState } from 'react';
import { NavLink } from 'react-router-dom';
import { Plus, Trash2 } from 'lucide-react';
import { GhostButton } from '../ui/GhostButton';
import { Badge } from '../ui/Badge';
import type { CaseSummary, LlmInfo } from '../../api/contract';
import styles from './Sidebar.module.css';

export interface SidebarProps {
  conversations?: CaseSummary[];
  cases?: CaseSummary[];
  activeId?: string;
  onNewChat?: () => void;
  onNewCase?: () => void;
  onDeleteCase?: (caseId: string) => void;
  llmInfo?: LlmInfo;
  className?: string;
}

function formatRelativeTime(iso: string): string {
  try {
    const diffMs = Date.now() - new Date(iso).getTime();
    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHours = Math.floor(diffMin / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffDays > 0) return `${diffDays}d ago`;
    if (diffHours > 0) return `${diffHours}h ago`;
    if (diffMin > 0) return `${diffMin}m ago`;
    return 'just now';
  } catch {
    return 'recently';
  }
}

export const Sidebar: React.FC<SidebarProps> = ({
  conversations,
  cases,
  activeId,
  onNewChat,
  onNewCase,
  onDeleteCase,
  llmInfo,
  className = '',
}) => {
  const caseList = cases || conversations || [];
  const handleNew = onNewCase || onNewChat || (() => {});
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  const handleDelete = (e: React.MouseEvent, id: string) => {
    e.preventDefault();
    e.stopPropagation();
    setConfirmDeleteId(id);
  };

  const confirmDelete = (e: React.MouseEvent, id: string) => {
    e.preventDefault();
    e.stopPropagation();
    if (onDeleteCase) {
      onDeleteCase(id);
    }
    setConfirmDeleteId(null);
  };

  const cancelDelete = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setConfirmDeleteId(null);
  };

  return (
    <aside className={`${styles.sidebar} ${className}`} aria-label="Case Workspace Sidebar">
      <div className={styles.topSection}>
        <GhostButton onClick={handleNew} className={styles.newChatButton}>
          <Plus size={16} strokeWidth={1.5} />
          NEW CASE
        </GhostButton>
      </div>

      <div className={styles.listSection}>
        <span className={styles.recentLabel}>CASES</span>

        {caseList.length === 0 ? (
          <div style={{ padding: '0 16px', fontSize: '13px', color: 'var(--color-smoke)' }}>
            No cases yet
          </div>
        ) : (
          caseList.map((c) => {
            const isActive = c.id === activeId;
            const statusUpper = (c.status || 'draft').toUpperCase();
            return (
              <div key={c.id} className={`${styles.itemWrapper} ${isActive ? styles.itemActive : ''}`}>
                <NavLink
                  to={`/platform/${c.id}`}
                  className={styles.convItem}
                  aria-current={isActive ? 'page' : undefined}
                >
                  <div className={styles.convHeader}>
                    <span className={styles.convTitle}>{c.title || 'Untitled Case'}</span>
                    <span className={styles.statusWord}>{statusUpper}</span>
                  </div>
                  <div className={styles.convFooter}>
                    <span className={styles.convTime}>{formatRelativeTime(c.updated_at)}</span>
                  </div>
                </NavLink>

                {onDeleteCase && (
                  <button
                    type="button"
                    className={styles.deleteBtn}
                    onClick={(e) => handleDelete(e, c.id)}
                    title="Delete case"
                    aria-label={`Delete case ${c.title}`}
                  >
                    <Trash2 size={13} strokeWidth={1.5} />
                  </button>
                )}

                {confirmDeleteId === c.id && (
                  <div className={styles.confirmModal} onClick={(e) => e.stopPropagation()}>
                    <div className={styles.confirmText}>Delete this case?</div>
                    <div className={styles.confirmActions}>
                      <button type="button" className={styles.confirmYes} onClick={(e) => confirmDelete(e, c.id)}>
                        Delete
                      </button>
                      <button type="button" className={styles.confirmNo} onClick={cancelDelete}>
                        Cancel
                      </button>
                    </div>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      <div className={styles.bottomSection}>
        <div className={styles.modelStatusBadge}>
          <Badge hasPulseDot={Boolean(llmInfo?.reachable)} size="compact">
            {llmInfo?.provider || 'ollama'} · {llmInfo?.model || 'model'}
          </Badge>
          <span className={styles.localityMono}>{llmInfo?.remote ? 'REMOTE' : 'LOCAL'}</span>
        </div>
      </div>
    </aside>
  );
};
