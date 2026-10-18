import React from 'react';
import styles from './Badge.module.css';

export interface BadgeProps {
  children: React.ReactNode;
  hasPulseDot?: boolean;
  size?: 'normal' | 'compact';
  className?: string;
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  hasPulseDot = false,
  size = 'normal',
  className = '',
}) => {
  return (
    <span
      className={`${styles.badge} ${size === 'compact' ? styles.compact : ''} ${className}`}
    >
      {hasPulseDot && (
        <span className={styles.pulseDot} aria-hidden="true" />
      )}
      <span>{children}</span>
    </span>
  );
};
