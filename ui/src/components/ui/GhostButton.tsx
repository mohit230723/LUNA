import React from 'react';
import styles from './GhostButton.module.css';

export interface GhostButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  children: React.ReactNode;
}

export const GhostButton: React.FC<GhostButtonProps> = ({
  children,
  className = '',
  disabled,
  ...props
}) => {
  return (
    <button
      className={`${styles.ghostButton} ${className}`}
      disabled={disabled}
      {...props}
    >
      {children}
    </button>
  );
};
