import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

/**
 * Penumbra Apex regression checks (14 Nov 2026). Each test pins a defect fixed in this pass:
 * deep-link substitution, the Certainty Height selector, the Ridge of Record inspect/return flow, the lighting mode label and
 * the guided demo. Expected values are read from the sidecars and the bundle, never typed in.
 */
const here = dirname(fileURLToPath(import.meta.url));
const pub = resolve(here, '../../public');
const sidecar = JSON.parse(readFileSync(`${pub}/certainty/sidecar.json`, 'utf8'));
const coverage = JSON.parse(readFileSync(`${pub}/certainty/coverage.json`, 'utf8'));
const roi3 = sidecar.sites.site04_roi3;
type Row = { mast_m: number; metric: string; min: number; max: number; pass: string; n_clones: number };
const row = (m: number, metric: string): Row => roi3.certainty_curve.find((r: Row) => r.mast_m === m && r.metric === metric);

test('deep link to a bundle that does not exist shows an error and never substitutes another bundle', async ({ page }) => {
  await page.goto('/?bundle=does_not_exist_2026.json#sky');
  await expect(page.getByTestId('load-error')).toBeVisible();
  await expect(page.getByTestId('instrument')).toHaveCount(0);
  await page.goto('/?bundle=..%2Fsecret#sky');
  await expect(page.getByTestId('load-error')).toContainText('not a plain .json file name');
});

test('Certainty Height selector: only the sampled heights, values equal the sidecar, 10 m switches the bundle series', async ({ page }) => {
  // Time limit only (assertions unchanged): with the three-level terrain context, a software GPU (SwiftShader, cloud CI) draws
  // ~1.3 frames/s and each scenario switch takes 10–16 s; the Mac GPU runs the same scene at 120 Hz (docs/PERFORMANCE_REPORT.md).
  test.setTimeout(180_000);
  await page.goto('/?site=site04_roi3#sky'); // Site04-specific values (Explore opens on Site01 ROI6 since 15 Nov 18:15; see store/siteDefaults.ts)
  const mi = page.getByTestId('mast-instrument');
  await expect(mi).toBeVisible();
  const chips = await mi.getByRole('radio').allTextContents();
  expect(chips.map(Number)).toEqual(roi3.sampled_masts_m);
  const cert = roi3.all_maps_100pct_sun_mast_m;
  await page.getByTestId(`mast-${cert}`).click();
  await expect(page.getByTestId(`mast-${cert}`)).toHaveAttribute('aria-checked', 'true');
  await expect(page.getByTestId('mast-pass-sun')).toHaveText(row(cert, 'sun_centre_pct').pass);
  await expect(page.getByTestId('mast-pass-both')).toHaveText(row(cert, 'both_centre_pct').pass);
  await expect(page.getByTestId('mast-all100')).toContainText(`yes, ${row(cert, 'sun_centre_pct').n_clones} of`);
  await expect(page.getByTestId('mast-compare')).toContainText(`${row(1, 'sun_centre_pct').min.toFixed(1)} %`);
  await expect(page.getByTestId('mast-series-note')).toBeVisible();
  await expect(page.getByTestId('mast-series-note')).toContainText(`No bundle time series at ${cert} m`);
  await expect(mi).toContainText(`${coverage.sites.site04_roi3.sun_pct.toFixed(1)} %`);
  await expect(page.getByTestId('scenario-select')).toHaveValue('baseline');
  await page.getByTestId('mast-1.5').click();
  await expect(page.getByTestId('mast-all100')).toContainText(`no · lowest ${row(1.5, 'sun_centre_pct').min.toFixed(1)} %`);
  await page.getByTestId('mast-10').click();
  await expect(page.getByTestId('scenario-select')).toHaveValue('mast10');
  await expect(mi).toContainText('show the bundle series at 10 m');
  await expect(page.getByTestId('mast-series-note')).toHaveCount(0);
  await page.getByTestId('mast-1').click();
  await expect(page.getByTestId('scenario-select')).toHaveValue('baseline');
});

test('Ridge of Record: inspect seeks a sample the bundle marks blocked, outlines the run on the ribbon, and Return restores', async ({ page }) => {
  await page.goto('/?site=site04_roi3#sky'); // Site04-specific values (Explore opens on Site01 ROI6 since 15 Nov 18:15; see store/siteDefaults.ts)
  await page.getByTestId('instrument').waitFor();
  const before = await page.getByTestId('sample-pos').textContent();
  // the "ridges of record" list is always in the instrument when the bundle carries attribution for the series shown
  await page.getByTestId('ridge-go-R3').click();
  await expect(page.getByTestId('cam-ridge')).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByTestId('ridge-3d-label')).toContainText('R3');
  const run = page.getByTestId('ribbon-run');
  await expect(run).toHaveCount(1);
  const i0 = Number(await run.getAttribute('data-i0'));
  const i1 = Number(await run.getAttribute('data-i1'));
  expect(i1).toBeGreaterThanOrEqual(i0);
  await expect(page.getByTestId('instrument')).toContainText('Sun blocked by');
  await page.getByTestId('ridge-return').click();
  await expect(page.getByTestId('ribbon-run')).toHaveCount(0);
  await expect(page.getByTestId('sample-pos')).toHaveText(before ?? '');
  await expect(page.getByTestId('ridge-return')).toHaveCount(0);
});

test('lighting: the display clamp is stated on screen and the true-elevation mode can be switched on', async ({ page }) => {
  await page.goto('/#sky');
  const tag = page.getByTestId('light-tag');
  await expect(tag).toContainText('Light: display');
  await page.getByTestId('light-true').click();
  await expect(page.getByTestId('light-true')).toHaveAttribute('aria-pressed', 'true');
  await expect(tag).toContainText('Light: true Sun elevation');
});

test('guided demo: five scenes driven by live data, exitable with Esc', async ({ page }) => {
  await page.goto('/');
  await page.getByTestId('story-guide').click();
  const g = page.getByTestId('guide');
  await expect(g).toBeVisible();
  await expect(g).toContainText('1 / 5');
  await expect(page).toHaveURL(/#sky$/);
  await page.getByTestId('guide-next').click();
  await expect(g).toContainText('Ridge of Record');
  await expect(page.getByTestId('ribbon-run')).toHaveCount(1);
  await page.getByTestId('guide-next').click();
  const cert = roi3.all_maps_100pct_sun_mast_m;
  await expect(page.getByTestId('guide-body')).toContainText(`At ${cert} m`);
  await expect(page.getByTestId(`mast-${cert}`)).toHaveAttribute('aria-checked', 'true');
  await page.getByTestId('guide-next').click();
  await expect(page.getByTestId('guide-body')).toContainText(`${coverage.sites.site04_roi3.sun_pct.toFixed(1)} %`);
  await expect(page.getByTestId('guide-body')).toContainText(`${row(1, 'sun_centre_pct').pass} tested realizations`);
  await page.getByTestId('guide-next').click();
  await expect(page).toHaveURL(/#decision$/);
  await expect(page.getByTestId('guide-finish')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(g).toHaveCount(0);
});

test('decision page labels each number with its solver; coverage explains what it measures', async ({ page }) => {
  await page.goto('/#decision');
  await expect(page.getByTestId('src-legend')).toContainText('repo solver');
  await expect(page.getByTestId('src-bundle')).toBeVisible();
  await expect(page.getByTestId('coverage-explain')).toContainText('What is measured');
  await expect(page.getByTestId('coverage-claim')).toContainText(`${row(1, 'sun_centre_pct').pass} tested realizations meet`);
  await expect(page.getByTestId('coverage-claim')).toContainText(`However, only ${coverage.sites.site04_roi3.sun_pct.toFixed(1)} %`);
});
