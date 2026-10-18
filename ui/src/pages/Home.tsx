import React, { useEffect } from 'react';
import { PageShell } from '../components/layout/PageShell';

export const Home: React.FC = () => {
  useEffect(() => {
    document.title = 'LUNA OS';
  }, []);

  return (
    <PageShell>
      <div style={{ padding: '40px 24px', textAlign: 'center' }}>
        <h1>Agents that act on connected data.</h1>
      </div>
    </PageShell>
  );
};
