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

// The dev mock is loaded by main.tsx (dev builds only) and registered here, so the
// mock and its fixtures never enter the production bundle.
let devMockApi: Api | null = null;
export function registerDevMockApi(api: Api): void {
  devMockApi = api;
}

export function getApi(): Api {
  if (
    typeof window !== 'undefined' &&
    import.meta.env.DEV &&
    window.location.search.includes('mock=1')
  ) {
    if (devMockApi) return devMockApi;
  }
  return liveApi;
}
