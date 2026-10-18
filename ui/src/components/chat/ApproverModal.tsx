import React, { useState, useEffect } from 'react';
import { Modal } from '../ui/Modal';
import { Button } from '../ui/Button';
import { GhostButton } from '../ui/GhostButton';
import styles from './ApproverModal.module.css';

export interface ApproverModalProps {
  isOpen: boolean;
  mode: 'approve' | 'reject';
  onClose: () => void;
  onSubmit: (val: string) => void;
}

export const ApproverModal: React.FC<ApproverModalProps> = ({
  isOpen,
  mode,
  onClose,
  onSubmit,
}) => {
  const [value, setValue] = useState('');

  useEffect(() => {
    if (isOpen) {
      if (mode === 'approve') {
        const saved = localStorage.getItem('luna.approver') || '';
        setValue(saved);
      } else {
        setValue('');
      }
    }
  }, [isOpen, mode]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!value.trim()) return;

    if (mode === 'approve') {
      localStorage.setItem('luna.approver', value.trim());
    }
    onSubmit(value.trim());
    onClose();
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={mode === 'approve' ? 'APPROVE ACTION' : 'REJECT ACTION'}
    >
      <form onSubmit={handleSubmit} className={styles.form}>
        <label className={styles.label} htmlFor="approver-input">
          {mode === 'approve' ? 'Your Name' : 'Rejection Reason'}
        </label>
        <input
          id="approver-input"
          className={styles.input}
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder={mode === 'approve' ? 'e.g. Alice Thorne' : 'e.g. Requires further validation'}
          autoFocus
          required
        />
        <div className={styles.actions}>
          <GhostButton type="button" onClick={onClose}>
            CANCEL
          </GhostButton>
          <Button type="submit">
            {mode === 'approve' ? 'CONFIRM APPROVAL' : 'CONFIRM REJECTION'}
          </Button>
        </div>
      </form>
    </Modal>
  );
};
