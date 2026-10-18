import React from 'react';
import styles from './Divider.module.css';

export interface DividerProps {
  className?: string;
}

export const Divider: React.FC<DividerProps> = ({ className = '' }) => {
  return <hr className={`${styles.divider} ${className}`} aria-hidden="true" />;
};
