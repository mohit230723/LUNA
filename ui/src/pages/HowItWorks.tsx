import React, { useEffect } from 'react';
import { PageShell } from '../components/layout/PageShell';

export const HowItWorks: React.FC = () => {
  useEffect(() => {
    document.title = 'How it works · LUNA OS';
  }, []);

  return (
    <PageShell>
      <div style={{ padding: '40px 24px', textAlign: 'center' }}>
        <h1>One request, followed end to end.</h1>
      </div>
    </PageShell>
  );
};
