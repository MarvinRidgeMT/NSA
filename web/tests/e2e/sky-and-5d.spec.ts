import { expect, test, type Page } from '@playwright/test';

/** Display-only exaggeration, hidden-body markers and the recomputed 5th-axis scenarios (docs/5D_SCENARIO_AXIS.md). */
const BUNDLE = 'polaris-x5d-roi-2026-11-14-v2.json';
const T = '2026-11-26T23:00:00Z'; // Site04 ROI3: bundle Sun blocked (margin -0.04 deg), Earth clear

async function bundleSeries(page: Page, scenario: string, k: number) {
  return page.evaluate(
    async ([file, id, i]) => {
      const j = await (await fetch(`bundles/${file}`)).json();
      const ds = j.datasets.find((d: { siteId: string }) => d.siteId === 'site04_roi3');
      const s = ds.derived.scenarios.find((x: { id: string }) => x.id === id);
      return { sun: s.samples.sun.marginDeg[i], sunVis: s.samples.sun.visible[i], earthVis: s.samples.earth.visible[i], az: s.ephemeris?.samples[i].sun.az ?? ds.ephemeris.samples[i].sun.az };
    },
    [BUNDLE, scenario, k] as const,
  );
}

test('vertical exaggeration is display only: bundle margins and states do not change', async ({ page }) => {
  await page.goto(`/?bundle=${BUNDLE}&site=site04_roi3&t=${T}&sc=baseline#sky`);
  await expect(page.getByTestId('scene3d')).toHaveAttribute('data-context', 'loaded', { timeout: 60_000 });
  const ref = await bundleSeries(page, 'baseline', 311);
  expect(ref.sunVis).toBe(false);
  await expect(page.getByTestId('sun-hidden-marker')).toHaveAttribute('data-hidden', 'true');
  await expect(page.getByTestId('earth-hidden-marker')).toHaveAttribute('data-hidden', 'false');
  await page.getByTestId('vertical-exaggeration').selectOption('5');
  await expect(page.getByTestId('exaggeration-tag')).toContainText('×5');
  await page.goto(page.url().replace('#sky', '#decision'));
  await expect(page.getByTestId('sun-margin')).toHaveAttribute('data-value', String(ref.sun));
});

test('5th axis: clone and offset scenarios are recomputed series; offsets use their own JPL azimuths', async ({ page }) => {
  await page.goto(`/?bundle=${BUNDLE}&site=site04_roi3&t=${T}#decision`);
  await expect(page.getByTestId('scenario-select').locator('option')).toHaveCount(9, { timeout: 30_000 });
  const opts = await page.getByTestId('scenario-select').locator('option').allTextContents();
  expect(opts.some((o) => o.startsWith('Terrain clone'))).toBe(true);
  await expect(page.getByTestId('scenario-table')).toBeVisible();
  await expect(page.getByTestId('offset-grid')).toBeVisible();
  await page.getByTestId('scenario-select').selectOption('pos_e+100_n+0');
  const east = await bundleSeries(page, 'pos_e+100_n+0', 311);
  const base = await bundleSeries(page, 'baseline', 311);
  expect(east.az).not.toBe(base.az); // its own Horizons samples, not the ROI point's
  await expect(page.getByTestId('sun-margin')).toHaveAttribute('data-value', String(east.sun));
  await expect(page.getByTestId('sun-az')).toContainText(east.az.toFixed(2));
  await expect(page.getByTestId('src-bundle')).toContainText('observer moved');
  await page.getByTestId('scenario-select').selectOption('clone003');
  await expect(page.getByTestId('src-bundle')).toContainText('PGDA 78 clone 3');
});
