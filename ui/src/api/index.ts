import { Api } from './contract';
import { mockApi } from './mock/mockApi';

export * from './contract';
export { mockApi } from './mock/mockApi';

export function getApi(): Api {
  const mode = import.meta.env.VITE_API_MODE;
  if (mode === 'live') {
    // LiveApi will be instantiated here; fallback to mockApi if not connected
    return mockApi;
  }
  return mockApi;
}
