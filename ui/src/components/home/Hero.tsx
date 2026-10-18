import React from 'react';
import { NavLink } from 'react-router-dom';
import { Button } from '../ui/Button';
import { GhostButton } from '../ui/GhostButton';
import { Badge } from '../ui/Badge';
import { ConstellationCanvas } from './ConstellationCanvas';
import { useHealth } from '../../state/hooks';
import styles from './Hero.module.css';

export const Hero: React.FC = () => {
  const { isOnline } = useHealth();

  return (
    <section className={styles.hero} aria-label="Hero">
      <h1 className={styles.headline}>Agents that act on connected data.</h1>
      <p className={styles.subheadline}>
        Give LUNA a task. A main agent plans it as a graph, assigns skills to sub-agents by query, and
        returns an answer you can trace back to the data.
      </p>

      <div className={styles.ctaRow}>
        <NavLink to="/platform" tabIndex={-1}>
          <Button showArrow>TRY THE PLATFORM</Button>
        </NavLink>
        <NavLink to="/how-it-works" tabIndex={-1}>
          <GhostButton>HOW IT WORKS</GhostButton>
        </NavLink>
      </div>

      <div className={styles.badgeRow}>
        <Badge hasPulseDot={isOnline}>
          {isOnline ? 'BACKEND ONLINE' : 'BACKEND OFFLINE'}
        </Badge>
      </div>

      <div className={styles.constellationBand}>
        <ConstellationCanvas />
      </div>
    </section>
  );
};
