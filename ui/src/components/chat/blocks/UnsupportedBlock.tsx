import React from 'react';
import styles from './blocks.module.css';

export interface UnsupportedBlockProps {
  type: string;
}

export const UnsupportedBlock: React.FC<UnsupportedBlockProps> = ({ type }) => {
  return (
    <div className={styles.blockCard}>
      <span className={styles.monoMeta}>UNSUPPORTED BLOCK: {type}</span>
    </div>
  );
};
