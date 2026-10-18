import React from 'react';
import { NavLink } from 'react-router-dom';
import { Badge } from '../ui/Badge';
import { useHealth } from '../../state/hooks';
import styles from './Footer.module.css';

export const Footer: React.FC = () => {
  const { isOnline } = useHealth();

  return (
    <footer className={styles.footer} role="contentinfo">
      <div className={styles.inner}>
        {/* Top Row */}
        <div className={styles.topRow}>
          {/* Brand & Subtitle */}
          <div className={styles.brandCol}>
            <span className={styles.wordmark}>LUNA OS</span>
            <p className={styles.tagline}>Agents that act on connected data.</p>
          </div>

          {/* Nav Links */}
          <div className={styles.links}>
            <NavLink to="/" className={styles.link}>HOME</NavLink>
            <NavLink to="/how-it-works" className={styles.link}>HOW IT WORKS</NavLink>
            <NavLink to="/skills" className={styles.link}>SKILL ATLAS</NavLink>
            <NavLink to="/platform" className={styles.link}>PLATFORM</NavLink>
          </div>

          {/* Status Badge */}
          <div className={styles.statusCol}>
            <Badge hasPulseDot={isOnline} size="compact">
              {isOnline ? 'BACKEND ONLINE' : 'BACKEND OFFLINE'}
            </Badge>
          </div>
        </div>

        {/* Bottom Line */}
        <div className={styles.bottomRow}>
          <span className={styles.builtWith}>
            Built on FalkorDB, MCP, and open tooling.
          </span>
        </div>
      </div>
    </footer>
  );
};
