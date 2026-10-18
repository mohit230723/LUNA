import React from 'react';
import { NavLink } from 'react-router-dom';
import { Plus } from 'lucide-react';
import { GhostButton } from '../ui/GhostButton';
import { Badge } from '../ui/Badge';
import { useHealth } from '../../state/hooks';
import type { ConversationSummary } from '../../api/contract';
import styles from './Sidebar.module.css';

export interface SidebarProps {
  conversations: ConversationSummary[];
  activeId?: string;
  onNewChat: () => void;
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
  activeId,
  onNewChat,
  className = '',
}) => {
  const { isOnline } = useHealth();
  const isMock = import.meta.env.VITE_API_MODE !== 'live';

  return (
    <aside className={`${styles.sidebar} ${className}`} aria-label="Conversation Sidebar">
      <div className={styles.topSection}>
        <GhostButton onClick={onNewChat} className={styles.newChatButton}>
          <Plus size={16} strokeWidth={1.5} />
          NEW CHAT
        </GhostButton>
      </div>

      <div className={styles.listSection}>
        <span className={styles.recentLabel}>RECENT</span>

        {conversations.length === 0 ? (
          <div style={{ padding: '0 16px', fontSize: '13px', color: 'var(--color-smoke)' }}>
            No recent conversations
          </div>
        ) : (
          conversations.map((c) => {
            const isActive = c.id === activeId;
            return (
              <NavLink
                key={c.id}
                to={`/platform/${c.id}`}
                className={`${styles.convItem} ${isActive ? styles.convItemActive : ''}`}
                aria-current={isActive ? 'page' : undefined}
              >
                <span className={styles.convTitle}>{c.title || 'New Conversation'}</span>
                <span className={styles.convTime}>{formatRelativeTime(c.updated_at)}</span>
              </NavLink>
            );
          })
        )}
      </div>

      <div className={styles.bottomSection}>
        <Badge hasPulseDot={isOnline} size="compact">
          {isOnline ? 'ONLINE' : 'OFFLINE'}
        </Badge>
        {isMock && <span className={styles.modeIndicator}>MOCK DATA</span>}
      </div>
    </aside>
  );
};
