import type { Api } from './contract';
import { liveApi } from './live';

export * from './contract';
export * from './guards';
export { liveApi, LiveApi, ApiError } from './live';

export function getApiMode(): 'mock' | 'live' {
  if (
    typeof window !== 'undefined' &&
    import.meta.env.DEV &&
    window.location.search.includes('mock=1')
  ) {
    return 'mock';
  }
  return 'live';
}

export function getApi(): Api {
  if (
    typeof window !== 'undefined' &&
    import.meta.env.DEV &&
    window.location.search.includes('mock=1')
  ) {
    // Lazy require/import of dev mock
    try {
      const { mockApi } = require('../dev/mockApi');
      return mockApi;
    } catch {
      // fallback to liveApi
    }
  }
  return liveApi;
}
