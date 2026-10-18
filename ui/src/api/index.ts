import type { Api } from './contract';
import { liveApi } from './live';
import { mockApi } from '../dev/mockApi';

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
    // Static import: `require` does not exist in the browser ESM bundle.
    return mockApi;
  }
  return liveApi;
}
