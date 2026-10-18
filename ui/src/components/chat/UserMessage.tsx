import React from 'react';
import styles from './UserMessage.module.css';

export interface UserMessageProps {
  content: string;
  createdAt: string;
}

export const UserMessage: React.FC<UserMessageProps> = ({ content, createdAt }) => {
  const formattedTime = new Date(createdAt).toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
  });

  return (
    <div className={styles.wrapper}>
      <div className={styles.card}>{content}</div>
      <span className={styles.timestamp}>{formattedTime}</span>
    </div>
  );
};
