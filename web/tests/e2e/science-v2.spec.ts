import { expect, test } from '@playwright/test';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
const __dirname = dirname(fileURLToPath(import.meta.url));
const file = 'site01_2026-11-14_14d.json';
const path = resolve(__dirname, '../../public/bundles', file);
const shots = resolve(__dirname, '../../docs/screenshots');

test.describe('Person A science-bundle-v2 (Site01, 14 d)', () => {
  test.skip(!existsSync(path), 'a-science bundle not synced into public/bundles (merge a-science, run npm run sync-bundles)');
  const raw = existsSync(path) ? JSON.parse(readFileSync(path, 'utf8')) : null;

  test('displayed margins equal the bundle at 3 timestamps; contract labels shown', async ({ page }) => {
    await page.goto(`/?bundle=${file}`);
    await expect(page.getByTestId('status-badge')).toHaveAttribute('data-status', 'SOURCE-BASED UNVALIDATED');
    await expect(page.getByTestId('demo-banner')).toHaveCount(0);
    for (const k of [17, 168, 300]) {
      const s = raw.samples[k];
      await page.getByTestId('utc-input').fill(s.utc.replace('.000Z', 'Z'));
      await page.getByTestId('utc-input').press('Enter');
      await expect(page.getByTestId('sample-pos')).toHaveText(`sample ${k + 1} / ${raw.samples.length}`);
      for (const t of ['sun', 'earth'] as const) {
        await expect(page.getByTestId(`${t}-margin`)).toHaveAttribute('data-value', String(s[t].margin_deg));
        await expect(page.getByTestId(`${t}-state`)).toContainText(s[t].center_visible ? 'VISIBLE' : 'BLOCKED');
        await expect(page.getByTestId(`${t}-disk`)).toHaveAttribute('data-value', String(s[t].disk_fraction));
        await expect(page.getByTestId(`${t}-az`)).toHaveText(`${s[t].az_deg.toFixed(2)}°`);
      }
    }
    await expect(page.getByTestId('metric-sun_center_visible_pct').locator('td').first()).toHaveAttribute('data-value', String(raw.metrics.sun_center_visible_pct));
  });

  test('between-sample times snap to a sample (contract rule)', async ({ page }) => {
    await page.goto(`/?bundle=${file}`);
    await page.getByTestId('utc-input').fill('2026-11-14T05:20:00Z');
    await page.getByTestId('utc-input').press('Enter');
    await expect(page.getByTestId('utc')).toHaveText('2026-11-14T05:00:00Z');
    await expect(page.getByTestId('time-note')).toContainText('snapped');
  });

  test('5D table: repair row shows bundle deltas and keeps baseline series labelled', async ({ page }) => {
    await page.goto(`/?bundle=${file}`);
    const rep = raw.scenarios.find((s: { family: string }) => s.family === 'repair');
    const row = page.getByTestId(`scen-${rep.id}`);
    await row.scrollIntoViewIfNeeded();
    await expect(row.locator('td').nth(2)).toHaveAttribute('data-value', String(rep.metrics.sun_and_earth_center_visible_pct));
    await expect(page.getByTestId('og-100_-100')).toContainText('100%');
    await row.getByRole('button').click();
    await expect(page.getByTestId('series-note')).toContainText('metrics only');
    await expect(page.getByTestId('metric-sun_and_earth_center_visible_pct').locator('td').nth(1)).toHaveAttribute('data-value', String(rep.delta_vs_baseline.sun_and_earth_center_visible_pct));
    await page.waitForTimeout(500);
    await page.getByTestId('scenario-table').screenshot({ path: `${shots}/09-science-v2-5d-scenarios.png` });
  });

  test('events jump the clock; 3D horizon dome renders; screenshot', async ({ page }) => {
    await page.goto(`/?bundle=${file}`);
    const ev = raw.events.find((e: { body: string; event: string }) => e.body === 'sun' && e.event === 'center_set');
    await page.getByTestId(`event-sun-center_set`).click();
    const t = Date.parse(ev.utc);
    const near = raw.samples.reduce((a: { t_unix: number }, b: { t_unix: number }) => (Math.abs(b.t_unix * 1000 - t) < Math.abs(a.t_unix * 1000 - t) ? b : a));
    await expect(page.getByTestId('utc')).toHaveText(near.utc.replace('.000Z', 'Z'));
    await expect(page.getByTestId('horizon-dome')).toBeVisible();
    await page.waitForTimeout(1500);
    await page.screenshot({ path: `${shots}/08-science-v2-site01.png`, fullPage: true });
  });
});
