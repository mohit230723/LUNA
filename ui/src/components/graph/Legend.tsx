import React from 'react';
import { X } from 'lucide-react';
import { IconButton } from '../ui/IconButton';
import styles from './Legend.module.css';

export interface LegendProps {
  isOpen: boolean;
  onClose: () => void;
}

export const Legend: React.FC<LegendProps> = ({ isOpen, onClose }) => {
  if (!isOpen) return null;

  return (
    <div className={styles.card} role="dialog" aria-label="Graph legend">
      <div className={styles.header}>
        <span className={styles.title}>GRAPH LEGEND</span>
        <IconButton aria-label="Close legend" onClick={onClose}>
          <X size={14} strokeWidth={1.5} />
        </IconButton>
      </div>

      {/* Node Shapes */}
      <div className={styles.section}>
        <span className={styles.sectionTitle}>NODE SHAPES</span>

        <div className={styles.item}>
          <span className={styles.shapeBadge}><span className={styles.diamond} /></span>
          <span>Customer</span>
        </div>

        <div className={styles.item}>
          <span className={styles.shapeBadge}><span className={styles.ellipse} /></span>
          <span>Entity (Phone, Address, Bank)</span>
        </div>

        <div className={styles.item}>
          <span className={styles.shapeBadge}><span className={styles.roundRect} /></span>
          <span>Finding</span>
        </div>

        <div className={styles.item}>
          <span className={styles.shapeBadge}><span className={styles.hexagon} /></span>
          <span>Agent</span>
        </div>

        <div className={styles.item}>
          <span className={styles.shapeBadge}><span className={styles.barrel} /></span>
          <span>Contract</span>
        </div>

        <div className={styles.item}>
          <span className={styles.shapeBadge}><span className={styles.octagon} /></span>
          <span>Action</span>
        </div>

        <div className={styles.item}>
          <span className={styles.shapeBadge}><span className={styles.dashedRect} /></span>
          <span>Violation / Superseded</span>
        </div>
      </div>

      {/* Edge Styles */}
      <div className={styles.section}>
        <span className={styles.sectionTitle}>EDGE STYLES</span>

        <div className={styles.item}>
          <span className={styles.shapeBadge}><span className={styles.edgeLine} /></span>
          <span>Standard Edge</span>
        </div>

        <div className={styles.item}>
          <span className={styles.shapeBadge}><span className={styles.pathEdgeLine} /></span>
          <span>Traversal Path (2.5px)</span>
        </div>

        <div className={styles.item}>
          <span className={styles.shapeBadge}><span className={styles.rejectedEdgeLine} /></span>
          <span>Rejected Candidate (Dashed)</span>
        </div>
      </div>
    </div>
  );
};
