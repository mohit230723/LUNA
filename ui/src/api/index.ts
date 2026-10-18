import { Api } from './contract';
import { mockApi } from './mock/mockApi';
import { liveApi } from './live';

export * from './contract';
export * from './guards';
export { mockApi } from './mock/mockApi';
export { liveApi, LiveApi, ApiError } from './live';

export function getApiMode(): 'mock' | 'live' {
  try {
    const prefs = localStorage.getItem('luna.prefs');
    if (prefs) {
      const parsed = JSON.parse(prefs);
      if (parsed.apiMode === 'live' || parsed.apiMode === 'mock') {
        return parsed.apiMode;
      }
    }
  } catch {
    // ignore json parse error
  }
  return (import.meta.env.VITE_API_MODE as 'mock' | 'live') === 'live' ? 'live' : 'mock';
}

export function setApiMode(mode: 'mock' | 'live'): void {
  try {
    let prefs: Record<string, unknown> = {};
    const existing = localStorage.getItem('luna.prefs');
    if (existing) {
      prefs = JSON.parse(existing);
    }
    prefs.apiMode = mode;
    localStorage.setItem('luna.prefs', JSON.stringify(prefs));
  } catch {
    // ignore
  }
}

export function getApi(): Api {
  const mode = getApiMode();
  return mode === 'live' ? liveApi : mockApi;
}
