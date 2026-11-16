import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

/**
 * E3 / E4 (15 Nov 2026). E3: where the batch Coverage Gauge sidecar is shown and the bundle also has derived.coverage,
 * one extra line shows the bundle's all_hours_covered_frac exactly (copied, not computed). E4: Site04 RoI 4 has
 * all_hours_covered_frac = 0 for Sun and Earth (genuine: every window azimuth is controlled by the 80 m regional DEM),
 * so the viewer says "No clone coverage at this RoI".
 */
const here = dirname(fileURLToPath(import.meta.url));
const bundles = resolve(here, '../../../data/bundles');
const cov = (f: string) => JSON.parse(readFileSync(`${bundles}/${f}`, 'utf8')).derived.coverage;
const p2 = (f: number) => `${(f * 100).toFixed(2)} %`;

for (const f of ['site04_roi3_2026-11-14_14d_mast1m.json', 'site01_roi6_2026-11-14_14d_mast1m.json']) {
  test(`E3: ${f} shows the bundle derived.coverage values next to the batch gauge`, async ({ page }) => {
    const c = cov(f);
    await page.goto(`/?bundle=${f}#decision`);
    await expect(page.getByTestId('coverage-batch')).toBeVisible();
    const alt = page.getByTestId('coverage-bundle-alt');
    await expect(alt).toHaveText(
      `Bundle derived.coverage: Sun ${p2(c.all_hours_covered_frac)}, Earth ${p2(c.earth.all_hours_covered_frac)} (different sampling; see docs/SOLVER_RECONCILIATION.md)`,
    );
    await expect(page.getByTestId('coverage-no-clone')).toHaveCount(0);
  });
}

test('E3: Site04 RoI 3 alt line is exactly 34.42 % / 61.13 %', async ({ page }) => {
  await page.goto('/?bundle=site04_roi3_2026-11-14_14d_mast1m.json#decision');
  await expect(page.getByTestId('coverage-bundle-alt')).toContainText('Sun 34.42 %, Earth 61.13 %');
});

test('E4: Site04 RoI 4 says there is no clone coverage at this RoI', async ({ page }) => {
  const f = 'site04_roi4_2026-11-14_14d_mast1m.json';
  const c = cov(f);
  expect(c.all_hours_covered_frac).toBe(0);
  expect(c.earth.all_hours_covered_frac).toBe(0);
  await page.goto(`/?bundle=${f}#decision`);
  await expect(page.getByTestId('coverage-no-clone')).toContainText('No clone coverage at this RoI');
});
