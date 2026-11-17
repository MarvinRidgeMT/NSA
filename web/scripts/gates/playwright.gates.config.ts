// Gate specs (docs/v2/GATES.md): accessibility + 390 px mobile layout. Same server and browser as playwright.config.ts.
//   cd web && POLARIS_PLAYWRIGHT_PORT=4221 npx playwright test -c scripts/gates/playwright.gates.config.ts
//   optional: AXE_CORE_PATH=/path/to/axe.min.js (axe-core is not in web/node_modules; the gate then runs its lite scan)
import { defineConfig, devices } from '@playwright/test';
import { existsSync } from 'node:fs';

const macChrome = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const executablePath = process.env.PLAYWRIGHT_CHROME_EXECUTABLE ?? (existsSync(macChrome) ? macChrome : undefined);
const port = process.env.POLARIS_PLAYWRIGHT_PORT ?? '4221';
const baseURL = `http://localhost:${port}`;

export default defineConfig({
  testDir: '.',
  testMatch: /.*\.gate\.ts$/,
  timeout: 120_000,
  fullyParallel: false,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL,
    viewport: { width: 1440, height: 900 },
    launchOptions: { executablePath, args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] },
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } } }],
  webServer: {
    command: `npm run build && npm run preview -- --port ${port}`,
    cwd: '../..',
    url: baseURL,
    reuseExistingServer: true,
    timeout: 180_000,
  },
});
