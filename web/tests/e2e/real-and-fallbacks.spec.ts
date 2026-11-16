import { expect, test } from '@playwright/test';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
const __dirname = dirname(fileURLToPath(import.meta.url));
import { openDemo, shots } from './helpers';

const realFile = 'polaris-source-site01-2026-11-14-v2.json';
const realPath = resolve(__dirname, '../../public/bundles', realFile);

test('real Codex source bundle: honest status, JPL angles, no invented margins', async ({ page }) => {
  test.skip(!existsSync(realPath), 'real bundle not synced');
  const real = JSON.parse(readFileSync(realPath, 'utf8'));
  await page.goto(`/?bundle=${realFile}`);
  await expect(page.getByTestId('status-badge')).toHaveAttribute('data-status', 'SOURCE-BASED UNVALIDATED');
  await expect(page.getByTestId('demo-banner')).toHaveCount(0);
  await expect(page.getByTestId('bundle-warning')).toContainText('does not compute');
  const s0 = real.datasets[0].ephemeris.samples[0];
  // Explore: no skyline in this bundle → honest empty states, nothing invented
  await expect(page.getByTestId('no-skyline')).toBeVisible();
  await expect(page.getByTestId('sky-sun')).toContainText('not in bundle');
  // the exact JPL angles (2 decimals) live in the Decision workspace's Metrics panel since the three-workspace layout
  await page.getByTestId('tab-decision').click();
  await expect(page.getByTestId('sun-az')).toHaveText(`${s0.sun.az.toFixed(2)}°`);
  await expect(page.getByTestId('sun-margin')).toHaveText('not in bundle');
  await page.getByTestId('tab-sky').click();
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${shots}/03-real-site01-source-bundle.png`, fullPage: true });
});

test('Cesium failure is graceful and token is never persisted', async ({ page }) => {
  await page.route(/cesium\.com/, (r) => r.abort());
  await openDemo(page);
  await page.getByTestId('cesium-token').fill('not-a-real-token');
  await page.getByTestId('cesium-load').click();
  await expect(page.getByTestId('cesium-error')).toContainText('unaffected');
  await expect(page.getByTestId('sky-sun')).toContainText('margin');
  const stored = await page.evaluate(() => JSON.stringify({ ...localStorage }) + JSON.stringify({ ...sessionStorage }));
  expect(stored).not.toContain('not-a-real-token');
});

test('invalid bundle file is rejected with a specific message', async ({ page }) => {
  await openDemo(page);
  await page.getByTestId('bundle-file').setInputFiles({ name: 'bad.json', mimeType: 'application/json', buffer: Buffer.from('{"format":"POLARIS-X5D-v1"}') });
  await expect(page.getByTestId('load-error')).toContainText('unsupported format');
});

test('screenshot set', async ({ page }) => {
  await openDemo(page);
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${shots}/01-demo-overview.png`, fullPage: true });
  await page.getByTestId('scenario-select').selectOption('mast10');
  await page.waitForTimeout(800);
  await page.screenshot({ path: `${shots}/04-demo-scenario-mast10.png`, fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForTimeout(800);
  await page.screenshot({ path: `${shots}/05-demo-phone-390.png`, fullPage: true });
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
  expect(overflow).toBe(false);
});
