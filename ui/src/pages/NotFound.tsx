import React, { useEffect } from 'react';
import { NavLink } from 'react-router-dom';
import { PageShell } from '../components/layout/PageShell';
import { GhostButton } from '../components/ui/GhostButton';
import styles from './NotFound.module.css';

export const NotFound: React.FC = () => {
  useEffect(() => {
    document.title = 'Not found · LUNA OS';
  }, []);

  return (
    <PageShell>
      <div className={styles.container}>
        <h1 className={styles.code}>404</h1>
        <p className={styles.subline}>That page is not in the graph.</p>
        <NavLink to="/">
          <GhostButton>GO HOME</GhostButton>
        </NavLink>
      </div>
    </PageShell>
  );
};
