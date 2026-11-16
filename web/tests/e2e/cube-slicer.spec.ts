import { expect, test } from '@playwright/test';
import { existsSync, readFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { ws } from './helpers';

const __dirname = dirname(fileURLToPath(import.meta.url));
const cubeFile = resolve(__dirname, '../../public/cubes/site04_roi3/centre_mast_schedule.json.gz');
const has = existsSync(cubeFile);
type Cube = { metrics: Record<string, { values: number[]; scale?: number }>; derived: Record<string, { metrics: Record<string, { values: number[]; scale?: number }> }> };

test.describe('scenario cube slicer (Phase 1)', () => {
  test.skip(!has, 'cube not built (python -m science.cube.build_cube)');

  test('slicer changes the strip and the card to exactly the cube values', async ({ page }) => {
    const cube = JSON.parse(gunzipSync(readFileSync(cubeFile)).toString('utf8')) as Cube;
    const val = (k: string, t: number, d: number, s: number) => cube.metrics[k].values[(t * 10 + d) * 8761 + s] * (cube.metrics[k].scale ?? 1);
    const band = (k: string, d: number, s: number) => cube.derived.band_over_T.metrics[k].values[d * 8761 + s] * (cube.derived.band_over_T.metrics[k].scale ?? 1);
    const kpass = (r: number, d: number, s: number) => cube.derived.k_of_N.metrics.k_pass.values[(r * 10 + d) * 8761 + s];

    await page.goto('/?bundle=site04_roi3_2026-11-14_14d_mast1m.json');
    await ws(page, 'decision');
    const slicer = page.getByTestId('cube-slicer');
    await slicer.scrollIntoViewIfNeeded();
    const card = page.getByTestId('cube-card-value');
    await expect(card).toBeVisible({ timeout: 30_000 });

    // baseline cell: nominal, 1 m, 2026-11-14 00:00, metric Sun+Earth
    await expect(card).toHaveAttribute('data-value', String(val('sun_earth_pct', 0, 0, 0)));
    await expect(card).toContainText('72.11 %');
    await expect(page.getByTestId('cube-card-band')).toHaveAttribute('data-min', String(band('sun_earth_pct_min', 0, 0)));
    await expect(page.getByTestId('cube-card-k')).toHaveAttribute('data-value', String(kpass(0, 0, 0)));

    // change mast → 5 m, start → index 4000, map → clone 7, metric → Sun
    await page.getByTestId('cube-ctl-D_mast').selectOption('4');
    await page.getByTestId('cube-ctl-S').fill('4000');
    await page.getByTestId('cube-ctl-T').selectOption('7');
    await page.getByTestId('cube-metric').selectOption('sun_pct');
    await expect(card).toHaveAttribute('data-value', String(val('sun_pct', 7, 4, 4000)));
    await expect(page.getByTestId('cube-card-band')).toHaveAttribute('data-max', String(band('sun_pct_max', 4, 4000)));
    await expect(page.getByTestId('cube-card-k')).toHaveAttribute('data-value', String(kpass(0, 4, 4000)));
    await expect(page.getByTestId('cube-strip')).toHaveAttribute('data-sel', '4000');
    await expect(page.getByTestId('cube-strip')).toHaveAttribute('data-n', '8761');

    // strip along D_mast: 10 points, band present
    await page.getByTestId('cube-free-D_mast').click();
    await expect(page.getByTestId('cube-strip')).toHaveAttribute('data-n', '10');
    await expect(page.getByTestId('cube-band')).toBeVisible();

    // requirement preset strict
    await page.getByTestId('cube-ctl-R').selectOption('1');
    await expect(page.getByTestId('cube-card-k')).toHaveAttribute('data-value', String(kpass(1, 4, 4000)));
  });

  test('a site without a cube says so', async ({ page }) => {
    await page.goto('/?bundle=demo-fixture.json');
    await ws(page, 'decision');
    await expect(page.getByTestId('cube-missing')).toContainText('not in bundle');
  });
});
