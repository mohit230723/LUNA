import React from 'react';
import { Check, X, HelpCircle, AlertTriangle } from 'lucide-react';
import styles from './StatusDot.module.css';

export type StatusType =
  | 'pending'
  | 'running'
  | 'active'
  | 'done'
  | 'failed'
  | 'needs_input'
  | 'superseded'
  | 'skipped'
  | 'warning';

export interface StatusDotProps {
  status: StatusType;
  label?: string;
  showText?: boolean;
  className?: string;
}

export const StatusDot: React.FC<StatusDotProps> = ({
  status,
  label,
  showText = true,
  className = '',
}) => {
  const renderIndicator = () => {
    switch (status) {
      case 'pending':
        return <span className={styles.pendingDot} aria-hidden="true" />;
      case 'running':
      case 'active':
        return <span className={styles.pulseDot} aria-hidden="true" />;
      case 'done':
        return <Check size={12} strokeWidth={1.5} className={styles.chalkIcon} aria-hidden="true" />;
      case 'failed':
        return <X size={12} strokeWidth={1.5} className={styles.chalkIcon} aria-hidden="true" />;
      case 'needs_input':
        return <HelpCircle size={12} strokeWidth={1.5} className={styles.goldIcon} aria-hidden="true" />;
      case 'warning':
        return <AlertTriangle size={12} strokeWidth={1.5} className={styles.goldIcon} aria-hidden="true" />;
      case 'superseded':
      case 'skipped':
        return <span className={styles.supersededDash} aria-hidden="true">—</span>;
      default:
        return null;
    }
  };

  const getDefaultText = () => {
    switch (status) {
      case 'pending': return 'PENDING';
      case 'running': case 'active': return 'RUNNING';
      case 'done': return 'DONE';
      case 'failed': return 'FAILED';
      case 'needs_input': return 'NEEDS INPUT';
      case 'superseded': return 'SUPERSEDED';
      case 'skipped': return 'SKIPPED';
      case 'warning': return 'WARNING';
      default: return String(status).toUpperCase();
    }
  };

  const displayText = label || getDefaultText();

  return (
    <span className={`${styles.statusContainer} ${styles[status] || ''} ${className}`}>
      {renderIndicator()}
      {showText && <span className={styles.statusText}>{displayText}</span>}
    </span>
  );
};
