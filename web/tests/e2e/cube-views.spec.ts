import { expect, test } from '@playwright/test';
import { existsSync, readFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { ws } from './helpers';

const __dirname = dirname(fileURLToPath(import.meta.url));
const dir = resolve(__dirname, '../../public/cubes/site04_roi3');
const has = existsSync(resolve(dir, 'launch_calendar.json.gz')) && existsSync(resolve(dir, 'decision_summary.json'));

test.describe('scenario cube views (Phases 2, 9.3 and the Decision Card rows)', () => {
  test.skip(!has, 'cubes not built');

  test('safe-and-lit grid, launch calendar and sub-axis rows show exactly the cube values', async ({ page }) => {
    const safety = JSON.parse(readFileSync(resolve(dir, 'terrain_safety.json'), 'utf8'));
    const cal = JSON.parse(gunzipSync(readFileSync(resolve(dir, 'launch_calendar.json.gz'))).toString('utf8'));
    const summary = JSON.parse(readFileSync(resolve(dir, 'decision_summary.json'), 'utf8'));
    const sl: number[] = safety.derived.safe_and_lit.metrics.k_safe_and_lit.values;

    await page.goto('/?bundle=site04_roi3_2026-11-14_14d_mast1m.json');
    await ws(page, 'decision');

    // Decision Card: one row per sub-axis question, copied from decision_summary.json
    for (const r of summary.rows) await expect(page.getByTestId(`dc-axis-${r.axis}`)).toContainText(r.value);

    // safe and lit at 10° and 8°
    const count = page.getByTestId('safe-lit-count');
    await count.scrollIntoViewIfNeeded();
    await expect(count).toHaveAttribute('data-value', String(sl.slice(0, 81).filter((k) => k === 20).length));
    await page.getByTestId('safe-lim').selectOption('1');
    await expect(count).toHaveAttribute('data-value', String(sl.slice(81).filter((k) => k === 20).length));
    await expect(page.getByTestId('sl-0_0')).toHaveAttribute('data-k', String(safety.derived.safe_and_lit.metrics.k_lit.values[40]));

    // calendar: click the centre of the canvas -> that day/hour's k
    const canvas = page.getByTestId('cal-canvas');
    await canvas.scrollIntoViewIfNeeded();
    const box = (await canvas.boundingBox())!;
    await canvas.click({ position: { x: box.width * (100.5 / 365), y: box.height * (6.5 / 24) } });
    const k = cal.metrics.k_pass.values[((0 * 3 + 0) * 365 + 100) * 24 + 6];
    await expect(page.getByTestId('cal-pick')).toHaveAttribute('data-value', String(k));
    await expect(page.getByTestId('cal-pick')).toContainText(`${cal.dims[2].values[100]} 06:00 UTC`);
  });

  test('a site without cubes shows "not in bundle" in the views', async ({ page }) => {
    await page.goto('/?bundle=demo-fixture.json');
    await ws(page, 'decision');
    await expect(page.getByTestId('cube-missing')).toBeVisible();
  });
});
