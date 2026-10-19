import { useEffect, useReducer, useState } from 'react';
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
    // Always clear previous run state (also when the case changes and there is no live run).
    dispatch({ type: 'RESET_RUN', runId });
    if (!runId) return;

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

// One shared health request for every component that shows backend status.
let sharedHealth: Health | null = null;
let sharedHealthAt = 0;
let sharedHealthInflight: Promise<Health | null> | null = null;
const healthListeners = new Set<(h: Health | null) => void>();

async function fetchSharedHealth(force = false): Promise<Health | null> {
  if (!force && sharedHealthInflight) return sharedHealthInflight;
  if (!force && sharedHealth && Date.now() - sharedHealthAt < 5000) return sharedHealth;
  sharedHealthInflight = getApi()
    .health()
    .then((h) => h as Health | null)
    .catch(() => null)
    .then((h) => {
      sharedHealth = h;
      sharedHealthAt = Date.now();
      sharedHealthInflight = null;
      healthListeners.forEach((fn) => fn(h));
      return h;
    });
  return sharedHealthInflight;
}

export function useHealth(): {
  health: Health | null;
  isOnline: boolean;
} {
  const [health, setHealth] = useState<Health | null>(sharedHealth);

  useEffect(() => {
    healthListeners.add(setHealth);
    if (!(typeof document !== 'undefined' && document.hidden)) {
      void fetchSharedHealth();
    }
    const timer = setInterval(() => {
      if (typeof document !== 'undefined' && document.hidden) return;
      void fetchSharedHealth(true);
    }, 30000);
    return () => {
      healthListeners.delete(setHealth);
      clearInterval(timer);
    };
  }, []);

  const isOnline = health?.status === 'ok';
  return { health, isOnline };
}
