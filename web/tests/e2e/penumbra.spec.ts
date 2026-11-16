import { expect, test, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

/**
 * Penumbra V3 implementation checks (14 Nov 2026): the story, the immersive stage and the decision instruments show values
 * copied from their sources (certainty sidecar, coverage sidecar, bundle), and the stage layout does not overlap at 1440 × 900.
 */
const here = dirname(fileURLToPath(import.meta.url));
const pub = resolve(here, '../../public');
const sidecar = JSON.parse(readFileSync(`${pub}/certainty/sidecar.json`, 'utf8'));
const coverage = JSON.parse(readFileSync(`${pub}/certainty/coverage.json`, 'utf8'));
const roi3 = sidecar.sites.site04_roi3;
const row = (m: number, metric: string) => roi3.certainty_curve.find((r: { mast_m: number; metric: string }) => r.mast_m === m && r.metric === metric);
const range = (r: { min: number; max: number }) => (r.min === r.max ? `${r.min.toFixed(1)} %` : `${r.min.toFixed(1)}–${r.max.toFixed(1)} %`);
const RESULTS = 'site04_roi3_2026-11-14_14d_mast1m.json';

async function box(page: Page, testId: string) {
  const b = await page.getByTestId(testId).boundingBox();
  if (!b) throw new Error(`no box for ${testId}`);
  return b;
}
const overlap = (a: { x: number; y: number; width: number; height: number }, b: { x: number; y: number; width: number; height: number }) =>
  a.x < b.x + b.width && b.x < a.x + a.width && a.y < b.y + b.height && b.y < a.y + a.height;

test('story opens first and its numbers equal the certainty and coverage sidecars', async ({ page }) => {
  await page.goto('/');
  const strip = page.getByTestId('story-strip');
  await expect(strip).toContainText(range(row(1, 'sun_centre_pct')));
  await expect(strip).toContainText(`${roi3.all_maps_100pct_sun_mast_m} m`);
  await expect(strip).toContainText(range(row(1, 'both_centre_pct')));
  await expect(strip).toContainText(`${coverage.sites.site04_roi3.sun_pct.toFixed(1)} %`);
  await expect(page.getByText('Sun angle chosen for the picture', { exact: false })).toBeVisible();
  await page.getByTestId('story-enter').click();
  await expect(page.getByTestId('instrument')).toBeVisible();
  await expect(page).toHaveURL(/#sky$/);
});

test('explore opens on real terrain (ROI export, Site01 ROI6, full NASA GSFC SfS relief) and labels its geometry mode', async ({ page }) => {
  // Sid, 15 Nov 18:15 EST: Explore opens on Site01 ROI6; the story, Decision and the guided demo stay on Site04 ROI3
  await page.goto('/#sky');
  await expect(page.getByTestId('geometry-mode')).toContainText('REAL SURFACE');
  await expect(page.getByTestId('site-select')).toHaveValue(/\d/);
  await expect(page.locator('.stage-title h1')).toContainText('Site01 ROI6');
  await page.getByTestId('tab-decision').click();
  await expect(page.getByTestId('site-select').locator('option:checked')).toContainText('Site04');
  await page.goto(`/?bundle=${RESULTS}#sky`);
  await expect(page.getByTestId('geometry-mode')).toContainText('HORIZON GEOMETRY');
  await expect(page.getByTestId('geometry-mode')).toContainText('not a terrain mesh');
});

test('stage layout at 1440 × 900: instrument, temporal bar, title and camera row do not overlap', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`/?bundle=${RESULTS}#sky`);
  await expect(page.getByTestId('instrument')).toBeVisible();
  const ins = await box(page, 'instrument');
  const cams = await box(page, 'camera-views');
  const rib = await box(page, 'margin-ribbon');
  const title = (await page.locator('.stage-title').boundingBox())!;
  const temporal = (await page.locator('.temporal').boundingBox())!;
  expect(overlap(ins, temporal)).toBe(false);
  expect(overlap(ins, title)).toBe(false);
  expect(overlap(cams, temporal)).toBe(false);
  expect(overlap(cams, ins)).toBe(false);
  expect(temporal.y + temporal.height).toBeLessThanOrEqual(900);
  expect(rib.width).toBeGreaterThan(1000);
  const scrollW = await page.evaluate(() => document.documentElement.scrollWidth);
  expect(scrollW).toBeLessThanOrEqual(1440);
});

test('camera views: one pressed at a time, also under reduced motion; no page errors', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto(`/?bundle=${RESULTS}#sky`);
  await page.getByTestId('cam-overhead').click();
  await expect(page.getByTestId('cam-overhead')).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByTestId('cam-approach')).toHaveAttribute('aria-pressed', 'false');
  await page.getByTestId('cam-mast').click();
  await expect(page.getByTestId('cam-mast')).toHaveAttribute('aria-pressed', 'true');
  expect(errors).toEqual([]);
});

test('decision: card pass counts and coverage rings equal their sidecars; the < 50 % caveat is shown', async ({ page }) => {
  await page.goto(`/?bundle=${RESULTS}#decision`);
  const card = page.getByTestId('decision-card');
  await expect(card).toContainText(range(row(1, 'sun_centre_pct')));
  await expect(card).toContainText(`requirement ≥ 70 %: ${row(1, 'sun_centre_pct').pass}`);
  await expect(card).toContainText(`requirement ≥ 40 %: ${row(1, 'both_centre_pct').pass}`);
  await expect(card).toContainText(`from a ${roi3.all_maps_100pct_sun_mast_m} m mast`);
  const cov = page.getByTestId('coverage-batch');
  await expect(cov).toContainText(`${coverage.sites.site04_roi3.sun_pct.toFixed(1)} %`);
  await expect(cov).toContainText(`${coverage.sites.site04_roi3.earth_pct.toFixed(1)} %`);
  await expect(cov).toContainText(coverage.source.sha256.slice(0, 12));
  await expect(page.getByTestId('coverage-warning')).toBeVisible();
});

test('typography: Penumbra fonts load; numbers use the mono face', async ({ page }) => {
  await page.goto(`/?bundle=${RESULTS}#sky`);
  await page.getByTestId('instrument').waitFor();
  const ok = await page.evaluate(async () => {
    await document.fonts.ready;
    return ['12px "JetBrains Mono"', '12px "Inter Tight"', '40px "Instrument Serif"'].map((f) => document.fonts.check(f));
  });
  expect(ok).toEqual([true, true, true]);
  const fam = await page.locator('.readout .big').first().evaluate((e) => getComputedStyle(e).fontFamily);
  expect(fam).toContain('JetBrains Mono');
});

test('margin ribbon: one concise accessible summary, per-sample values only in the on-demand table', async ({ page }) => {
  await page.goto(`/?bundle=${RESULTS}#sky`);
  const rib = page.getByTestId('margin-ribbon');
  await expect(rib).toHaveAttribute('aria-label', /Sun blocked in \d+ of 337 bundle samples; Earth blocked in \d+ of 337/);
  expect(await page.locator('[data-testid="margin-ribbon"] title').count()).toBe(0);
  expect(await page.locator('.strips title').count()).toBe(0);
  const table = page.getByTestId('ribbon-table');
  expect(await table.locator('tbody tr').count()).toBe(0);
  await table.locator('summary').click();
  await expect(table.locator('tbody tr')).toHaveCount(337);
  await table.locator('tbody tr').nth(5).locator('button').click();
  await expect(page.getByTestId('sample-pos')).toHaveText('sample 6 / 337');
});
