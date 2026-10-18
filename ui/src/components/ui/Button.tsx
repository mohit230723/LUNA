import React from 'react';
import styles from './Button.module.css';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  children: React.ReactNode;
  showArrow?: boolean;
}

export const Button: React.FC<ButtonProps> = ({
  children,
  showArrow = false,
  className = '',
  disabled,
  ...props
}) => {
  return (
    <button
      className={`${styles.pillButton} ${className}`}
      disabled={disabled}
      {...props}
    >
      <span>{children}</span>
      {showArrow && <span className={styles.arrow} aria-hidden="true">↗</span>}
    </button>
  );
};
