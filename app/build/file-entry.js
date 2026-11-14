// Direct-file runtime: embed the compact source case, then start the same app.
// This avoids Chrome's file:// module and fetch restrictions when index.html is double-clicked.
import offlineBundle from '../data/polaris-offline-source-case.json';

window.__POLARIS_OFFLINE_BUNDLE__ = offlineBundle;
import('../src/main.js');
