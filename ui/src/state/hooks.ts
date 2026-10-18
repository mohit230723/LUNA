import { useEffect, useReducer, useRef, useState } from 'react';
import { getApi, Health, RunEvent, TraceResponse } from '../api';
import { createInitialRunState, runReducer, RunState } from './runReducer';

export function useRun(runId: string | undefined): {
  runState: RunState;
  connectionState: 'open' | 'reconnecting' | 'closed';
} {
  const [runState, dispatch] = useReducer(runReducer, createInitialRunState(runId));
  const [connectionState, setConnectionState] = useState<'open' | 'reconnecting' | 'closed'>('closed');
  const api = getApi();

  useEffect(() => {
    if (!runId) return;

    dispatch({ type: 'RESET_RUN', runId });

    const unsubscribe = api.subscribeRun(runId, {
      lastEventId: runState.lastEventId,
      onEvent: (event: RunEvent) => {
        dispatch({ type: 'ADD_EVENT', event });
      },
      onState: (state: 'open' | 'reconnecting' | 'closed') => {
        setConnectionState(state);
      },
    });

    return () => {
      unsubscribe();
    };
  }, [runId]);

  return { runState, connectionState };
}

export function useTrace(runId: string | undefined): {
  trace: TraceResponse | null;
  isLoading: boolean;
  error: string | null;
  reload: () => Promise<void>;
} {
  const [trace, setTrace] = useState<TraceResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const api = getApi();

  const load = async () => {
    if (!runId) return;
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.getTrace(runId);
      setTrace(data);
    } catch (err: any) {
      setError(err?.message || 'Failed to load trace');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [runId]);

  return { trace, isLoading, error, reload: load };
}

export function useHealth(): {
  health: Health | null;
  isOnline: boolean;
} {
  const [health, setHealth] = useState<Health | null>(null);
  const api = getApi();
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const check = async () => {
    if (typeof document !== 'undefined' && document.hidden) return;
    try {
      const res = await api.health();
      setHealth(res);
    } catch {
      setHealth(null);
    }
  };

  useEffect(() => {
    check();
    timerRef.current = setInterval(check, 30000);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  const isOnline = health?.status === 'ok';
  return { health, isOnline };
}
