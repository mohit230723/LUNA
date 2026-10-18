import React, { useEffect } from 'react';
import { PageShell } from '../components/layout/PageShell';

export const Platform: React.FC = () => {
  useEffect(() => {
    document.title = 'Platform · LUNA OS';
  }, []);

  return (
    <PageShell showFooter={false} compactNav={true}>
      <div style={{ padding: '24px', textAlign: 'center' }}>
        <h1>Platform</h1>
      </div>
    </PageShell>
  );
};
