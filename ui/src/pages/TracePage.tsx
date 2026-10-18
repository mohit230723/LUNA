import React, { useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { TraceView } from '../components/graph/TraceView';

export const TracePage: React.FC = () => {
  const { conversationId, runId } = useParams<{ conversationId: string; runId: string }>();
  const navigate = useNavigate();

  useEffect(() => {
    document.title = 'Trace · LUNA OS';
  }, []);

  const handleBack = () => {
    if (conversationId) {
      navigate(`/platform/${conversationId}`);
    } else {
      navigate('/platform');
    }
  };

  return (
    <>
      <h1 className="visually-hidden">Trace</h1>
      <TraceView
        runId={runId || 'run_f1'}
        onBack={handleBack}
      />
    </>
  );
};
