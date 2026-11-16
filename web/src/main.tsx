import '@fontsource/instrument-serif/400.css';
import '@fontsource/inter-tight/400.css';
import '@fontsource/inter-tight/500.css';
import '@fontsource/inter-tight/600.css';
import '@fontsource/jetbrains-mono/300.css';
import '@fontsource/jetbrains-mono/400.css';
import '@fontsource/jetbrains-mono/500.css';
import { lazy, StrictMode, Suspense } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import SimpleApp from './SimpleApp';
import { resolveMode } from './mode';
import './styles.css';

// Hidden design-system reference for Simple mode (S1): ?mode=simple&sheet=1. Nothing links to it; Expert never loads it.
const TokenSheet = lazy(() => import('./simple/TokenSheet'));
const mode = resolveMode(location.search, location.hash);
const sheet = mode === 'simple' && new URLSearchParams(location.search).get('sheet') === '1';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {sheet ? (
      <Suspense fallback={null}>
        <TokenSheet />
      </Suspense>
    ) : mode === 'simple' ? (
      <SimpleApp />
    ) : (
      <App />
    )}
  </StrictMode>,
);
