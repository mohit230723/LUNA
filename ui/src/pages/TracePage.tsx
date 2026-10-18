import React, { useEffect } from 'react';
import { PageShell } from '../components/layout/PageShell';

export const TracePage: React.FC = () => {
  useEffect(() => {
    document.title = 'Trace · LUNA OS';
  }, []);

  return (
    <PageShell showFooter={false} compactNav={true}>
      <div style={{ padding: '24px', textAlign: 'center' }}>
        <h1>Trace</h1>
      </div>
    </PageShell>
  );
};
