import { expect, test } from '@playwright/test';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const file = 'site04_roi3_2026-11-14_14d_mast1m.json';
const path = resolve(__dirname, '../../public/bundles', file);
const shots = resolve(__dirname, '../../docs/screenshots');

test.describe('PILOT flip-forecast traceability', () => {
  test.skip(!existsSync(path), 'run npm run sync-bundles first');
  const raw = existsSync(path) ? JSON.parse(readFileSync(path, 'utf8')) : null;

  test('small table copies forecast/actual metrics, null state and result IDs', async ({ page }) => {
    const block = raw.derived.flip_forecast;
    await page.goto(`/?bundle=${file}#decision`);
    const panel = page.getByTestId('flip-forecast');
    await expect(panel).toBeVisible();
    await expect(page.getByTestId('flip-forecast-label')).toHaveText(block.label);
    for (const value of block.forecast_vs_actual) {
      const row = page.getByTestId(`flip-forecast-row-${value.row_id}`);
      await expect(row).toHaveAttribute('data-result-id', value.result_id);
      await expect(row).toHaveAttribute('data-label', value.label);
      await expect(row.locator('td').nth(0)).toHaveAttribute('data-value', String(value.case_count));
      await expect(row.locator('td').nth(1)).toHaveAttribute('data-value', String(value.predicted_flips));
      await expect(row.locator('td').nth(2)).toHaveAttribute('data-value', String(value.actual_flips));
      await expect(row.locator('td').nth(4)).toHaveText(value.precision_display);
      await expect(row.locator('td').nth(5)).toHaveText(value.recall_display);
    }
    await page.setViewportSize({ width: 1080, height: 1000 });
    await panel.scrollIntoViewIfNeeded();
    await panel.screenshot({ path: `${shots}/12-flip-forecast-pilot.png` });
  });
});
