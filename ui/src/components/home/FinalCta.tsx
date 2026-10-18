import React from 'react';
import { NavLink } from 'react-router-dom';
import { Button } from '../ui/Button';
import styles from './FinalCta.module.css';

export const FinalCta: React.FC = () => {
  return (
    <section className={styles.section} aria-label="Final Call to Action">
      <h2 className={styles.heading}>Try it on a real prompt.</h2>
      <NavLink to="/platform" tabIndex={-1}>
        <Button showArrow>TRY THE PLATFORM</Button>
      </NavLink>
    </section>
  );
};
