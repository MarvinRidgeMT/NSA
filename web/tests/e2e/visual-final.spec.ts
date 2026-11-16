import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

/**
 * Final visual-quality pass (14 Nov 2026, 21:10–23:30 EST). Pins: sight-line labels carry the bundle's margin and ridge
 * attribution (a 128 km ridge is labelled "beyond this crop", never drawn as local terrain), the camera row fits on one line
 * at 1440 px, Mast-eye hides the sight lines it looks along, and the Decision page leads with the card and the 1 m vs
 * Certainty Height comparison, values from the sidecar. Expected values are read from the source files.
 */
const here = dirname(fileURLToPath(import.meta.url));
const pub = resolve(here, '../../public');
const sidecar = JSON.parse(readFileSync(`${pub}/certainty/sidecar.json`, 'utf8'));
const roi3 = sidecar.sites.site04_roi3;
type Row = { mast_m: number; metric: string; min: number; max: number; pass: string; n_clones: number };
const row = (m: number, metric: string): Row => roi3.certainty_curve.find((r: Row) => r.mast_m === m && r.metric === metric);
const rng = (r: Row) => (r.min === r.max ? `${r.min.toFixed(1)} %` : `${r.min.toFixed(1)}–${r.max.toFixed(1)} %`);
const roi = JSON.parse(readFileSync(`${pub}/bundles/polaris-x5d-roi-2026-11-14-v2.json`, 'utf8'));
const ds = roi.datasets.find((d: { siteId: string }) => d.siteId === 'site04_roi3');
const base = ds.derived.scenarios.find((s: { id: string }) => s.id === 'baseline');
const sgn = (m: number) => `${m >= 0 ? '+' : '−'}${Math.abs(m).toFixed(2)}°`;

test('sight lines: labels carry the bundle margin and ridge; the 128 km ridge is "beyond this crop"', async ({ page }) => {
  await page.goto('/?site=site04_roi3#sky'); // Site04-specific values; Explore opens on Site01 ROI6 since 15 Nov 18:15
  await page.getByTestId('instrument').waitFor();
  const earth = page.getByTestId('sight-earth');
  await expect(earth).toBeVisible();
  await expect(earth).toContainText(`${sgn(base.samples.earth.marginDeg[0])} vs skyline`);
  await expect(earth).toContainText('R1');
  await expect(earth).toContainText('beyond this crop');
  await expect(page.getByTestId('sight-sun')).toContainText(`${sgn(base.samples.sun.marginDeg[0])} vs skyline`);
  // Ridge of Record R3: the Sun line ends on the rise, its label names R3 and the bundle margin at the selected sample
  await page.getByTestId('ridge-go-R3').click();
  const i0 = Number(await page.getByTestId('ribbon-run').getAttribute('data-i0'));
  const sun = page.getByTestId('sight-sun');
  await expect(sun).toContainText('blocked');
  await expect(sun).toContainText(`${sgn(base.samples.sun.marginDeg[i0])} vs skyline`);
  await expect(sun).toContainText('R3');
  await expect(sun).not.toContainText('beyond this crop');
});

test('Explorer at 1440 × 900: camera and display controls on one line; Mast-eye hides the sight lines', async ({ page }) => {
  await page.goto('/#sky');
  const row = page.getByTestId('camera-views');
  await expect(row).toBeVisible();
  const b = (await row.boundingBox())!;
  expect(b.height).toBeLessThanOrEqual(40);
  await expect(page.getByTestId('light-display')).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByTestId('light-tag')).toContainText('relief fill on (display only)');
  await page.getByTestId('light-true').click();
  await expect(page.getByTestId('light-tag')).toContainText('scientific, no fill');
  await page.getByTestId('cam-mast').click();
  await expect(page.getByTestId('sight-sun')).toBeHidden();
  await expect(page.getByTestId('sight-earth')).toBeHidden();
  await page.getByTestId('cam-approach').click();
  await expect(page.getByTestId('sight-earth')).toBeVisible();
});

test('Decision: card and the 1 m vs Certainty Height comparison lead the page, values from the sidecar', async ({ page }) => {
  await page.goto('/#decision');
  const cert = roi3.all_maps_100pct_sun_mast_m;
  const low = page.getByTestId('hc-low');
  const hi = page.getByTestId('hc-cert');
  await expect(low).toContainText(rng(row(1, 'sun_centre_pct')));
  await expect(low).toContainText(rng(row(1, 'both_centre_pct')));
  await expect(low).toContainText(`lowest ${row(1, 'sun_centre_pct').min.toFixed(1)} %`);
  await expect(hi).toContainText(`100 % on all ${row(cert, 'sun_centre_pct').n_clones}`);
  await expect(hi).toContainText(rng(row(cert, 'both_centre_pct')));
  await expect(hi).toContainText(row(cert, 'both_centre_pct').pass);
  for (const id of ['decision-card', 'height-compare']) {
    const bb = (await page.getByTestId(id).boundingBox())!;
    expect(bb.y).toBeLessThan(900); // starts in the first screen
  }
  // details stay one click away and keep their exact values
  await expect(page.getByTestId('cert-details')).not.toHaveAttribute('open', '');
  await page.getByTestId('cert-details').locator('summary').click();
  await expect(page.getByTestId(`cert-pass-${cert}`)).toBeVisible();
  await expect(page.getByTestId('coverage-warning')).toBeVisible();
});
