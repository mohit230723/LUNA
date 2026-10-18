import React, { createContext, useContext } from 'react';
import { SkipLink } from './SkipLink';
import { TopNav } from './TopNav';
import { Footer } from './Footer';
import styles from './PageShell.module.css';

export interface PageShellProps {
  children: React.ReactNode;
  showFooter?: boolean;
  compactNav?: boolean;
}

// A PageShell rendered inside another PageShell (e.g. the Cases tab inside the
// Platform tab shell) renders only its children so the nav is not duplicated.
const InsidePageShell = createContext(false);

export const PageShell: React.FC<PageShellProps> = ({
  children,
  showFooter = true,
  compactNav = false,
}) => {
  const nested = useContext(InsidePageShell);
  if (nested) return <>{children}</>;
  return (
    <InsidePageShell.Provider value={true}>
    <div className={styles.shell}>
      <SkipLink />
      <TopNav compact={compactNav} />
      <main id="main-content" className={styles.main}>
        {children}
      </main>
      {showFooter && <Footer />}
    </div>
    </InsidePageShell.Provider>
  );
};
