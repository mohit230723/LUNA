import React from 'react';
import styles from './Card.module.css';

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  variant?: 'normal' | 'carbon' | 'failed' | 'warning';
}

export const Card: React.FC<CardProps> = ({
  children,
  variant = 'normal',
  className = '',
  ...props
}) => {
  const variantClass = styles[variant] || '';
  return (
    <div className={`${styles.card} ${variantClass} ${className}`} {...props}>
      {children}
    </div>
  );
};
