import React from 'react';
import { AlertTriangle } from 'lucide-react';
import styles from './blocks.module.css';

export interface WarningBlockProps {
  text: string;
}

export const WarningBlock: React.FC<WarningBlockProps> = ({ text }) => {
  return (
    <div className={styles.warningCard} role="alert">
      <AlertTriangle size={20} strokeWidth={1.5} className={styles.warningIcon} aria-hidden="true" />
      <p className={styles.warningText}>{text}</p>
    </div>
  );
};
