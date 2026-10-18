import React, { useEffect } from 'react';
import { PageShell } from '../components/layout/PageShell';

export const SkillAtlas: React.FC = () => {
  useEffect(() => {
    document.title = 'Skill Atlas · LUNA OS';
  }, []);

  return (
    <PageShell>
      <div style={{ padding: '40px 24px', textAlign: 'center' }}>
        <h1>Every skill the orchestrator can choose.</h1>
      </div>
    </PageShell>
  );
};
