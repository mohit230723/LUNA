import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import '@fontsource-variable/inter';
import '@fontsource/ibm-plex-mono';
import './styles/tokens.css';
import './styles/base.css';
import './styles/typography.css';
import './styles/utilities.css';
import { App } from './App';
import { registerDevMockApi } from './api';

// `?mock=1` loads the dev mock before first render. The branch is constant-false in
// production builds, so the mock chunk is dropped from the bundle.
const ready: Promise<void> =
  import.meta.env.DEV && window.location.search.includes('mock=1')
    ? import('./dev/mockApi').then((m) => registerDevMockApi(m.mockApi))
    : Promise.resolve();

ready.then(() => {
  ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </React.StrictMode>
  );
});
