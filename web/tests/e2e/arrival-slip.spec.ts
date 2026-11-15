import { expect, test } from '@playwright/test';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const file = 'site04_roi3_2026-11-14_14d_mast1m.json';
const path = resolve(__dirname, '../../public/bundles', file);
const shots = resolve(__dirname, '../../docs/screenshots');

test.describe('PILOT arrival-slip traceability', () => {
  test.skip(!existsSync(path), 'run npm run sync-bundles first');
  const raw = existsSync(path) ? JSON.parse(readFileSync(path, 'utf8')) : null;

  test('strip and exact table copy the bundle result IDs, metrics and pass counts', async ({ page }) => {
    const block = raw.derived.arrival_slip;
    await page.goto(`/?bundle=${file}`);
    await expect(page.getByTestId('arrival-slip')).toBeVisible();
    await expect(page.getByTestId('arrival-slip-label')).toHaveText(block.label);
    for (const slip of [-72, 0, 66, 72]) {
      const point = block.points.find((value: { slip_h: number }) => value.slip_h === slip);
      const cell = page.getByTestId(`arrival-slip-cell-${slip}`);
      await expect(cell).toHaveAttribute('data-result-id', point.result_id);
      await expect(cell).toHaveAttribute('data-label', point.label);
      await expect(cell).toContainText(`${point.clones.joint_pass_count}/${point.clones.pass_denominator}`);
      const row = page.getByTestId(`arrival-slip-row-${slip}`);
      await expect(row).toHaveAttribute('data-result-id', point.result_id);
      await expect(row.locator('td').nth(0)).toHaveAttribute('data-value', String(point.nominal.sun_center_visible_pct));
      await expect(row.locator('td').nth(2)).toHaveAttribute('data-value', String(point.nominal.sun_and_earth_center_visible_pct));
      await expect(row.locator('td').nth(4)).toHaveAttribute('data-value', String(point.clones.joint_pass_count));
    }
    await page.getByTestId('arrival-slip').scrollIntoViewIfNeeded();
    await page.getByTestId('arrival-slip').screenshot({ path: `${shots}/10-arrival-slip-pilot.png` });
  });
});
