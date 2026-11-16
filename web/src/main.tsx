import '@fontsource/instrument-serif/400.css';
import '@fontsource/inter-tight/400.css';
import '@fontsource/inter-tight/500.css';
import '@fontsource/inter-tight/600.css';
import '@fontsource/jetbrains-mono/300.css';
import '@fontsource/jetbrains-mono/400.css';
import '@fontsource/jetbrains-mono/500.css';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import './styles.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

// LIVE · CONTEXT panel (display only), mounted only with ?live=1 so the default app is unchanged.
if (new URLSearchParams(location.search).get('live') === '1') {
  import('./live/NowPanel').then(({ LiveMount }) => {
    const el = document.createElement('div');
    el.id = 'polaris-live';
    document.body.appendChild(el);
    createRoot(el).render(<LiveMount />);
  });
}
