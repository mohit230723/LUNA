import React from 'react';
import { SkipLink } from './SkipLink';
import { TopNav } from './TopNav';
import { Footer } from './Footer';
import styles from './PageShell.module.css';

export interface PageShellProps {
  children: React.ReactNode;
  showFooter?: boolean;
  compactNav?: boolean;
}

export const PageShell: React.FC<PageShellProps> = ({
  children,
  showFooter = true,
  compactNav = false,
}) => {
  return (
    <div className={styles.shell}>
      <SkipLink />
      <TopNav compact={compactNav} />
      <main id="main-content" className={styles.main}>
        {children}
      </main>
      {showFooter && <Footer />}
    </div>
  );
};
