import React from 'react';
import { NavLink } from 'react-router-dom';
import { Button } from '../ui/Button';
import { GhostButton } from '../ui/GhostButton';
import { Badge } from '../ui/Badge';
import { ConstellationCanvas } from './ConstellationCanvas';
import { TwoWays } from './TwoWays';
import { useHealth } from '../../state/hooks';
import styles from './Hero.module.css';

export const Hero: React.FC = () => {
  const { isOnline } = useHealth();

  return (
    <section className={styles.hero} aria-label="Hero">
      <h1 className={styles.headline}>Agents that act on connected data.</h1>
      <p className={styles.subheadline}>
        Give LUNA a case or a build. It plans the work as a graph, equips sub-agents with skills by query,
        and hands back a result you can trace to the data.
      </p>

      <div className={styles.ctaRow}>
        <NavLink to="/platform" tabIndex={-1}>
          <Button showArrow>OPEN THE PLATFORM</Button>
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

      <TwoWays />
    </section>
  );
};
