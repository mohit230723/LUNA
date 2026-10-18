import React from 'react';
import styles from './IconButton.module.css';

export interface IconButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  children: React.ReactNode;
  'aria-label': string;
  variant?: 'ghost' | 'pill' | 'circle';
}

export const IconButton: React.FC<IconButtonProps> = ({
  children,
  'aria-label': ariaLabel,
  variant = 'ghost',
  className = '',
  disabled,
  ...props
}) => {
  const variantClass = variant === 'pill' ? styles.pill : variant === 'circle' ? styles.circle : styles.ghost;
  return (
    <button
      className={`${styles.iconButton} ${variantClass} ${className}`}
      aria-label={ariaLabel}
      disabled={disabled}
      {...props}
    >
      {children}
    </button>
  );
};
