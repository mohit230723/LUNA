import React from 'react';
import styles from './Spinner.module.css';

export interface SpinnerProps {
  size?: number;
  className?: string;
  label?: string;
}

export const Spinner: React.FC<SpinnerProps> = ({
  size = 20,
  className = '',
  label = 'Loading...',
}) => {
  return (
    <div className={`${styles.wrapper} ${className}`} role="status">
      <div
        className={styles.spinner}
        style={{ width: size, height: size }}
        aria-hidden="true"
      />
      <span className="sr-only">{label}</span>
    </div>
  );
};
