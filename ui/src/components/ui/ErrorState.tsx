import React from 'react';
import { AlertTriangle } from 'lucide-react';
import { GhostButton } from './GhostButton';
import styles from './ErrorState.module.css';

export interface ErrorStateProps {
  title?: string;
  message?: string;
  detail?: string;
  onRetry?: () => void;
  className?: string;
}

export const ErrorState: React.FC<ErrorStateProps> = ({
  title = 'An error occurred',
  message,
  detail,
  onRetry,
  className = '',
}) => {
  return (
    <div className={`${styles.container} ${className}`} role="alert">
      <div className={styles.iconContainer}>
        <AlertTriangle size={32} strokeWidth={1.5} className={styles.goldIcon} />
      </div>
      <h3 className={styles.title}>{title}</h3>
      {message && <p className={styles.message}>{message}</p>}
      {detail && <pre className={styles.detail}>{detail}</pre>}
      {onRetry && (
        <div className={styles.action}>
          <GhostButton onClick={onRetry}>RETRY</GhostButton>
        </div>
      )}
    </div>
  );
};
