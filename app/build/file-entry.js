// Self-contained runtime: embed the two-site source case, including the Site01
// 5 m terrain/error realizations. This also avoids file:// module/fetch limits.
import offlineBundle from '../data/polaris-runtime-source-case.json';

window.__POLARIS_OFFLINE_BUNDLE__ = offlineBundle;
import('../src/main.js');
