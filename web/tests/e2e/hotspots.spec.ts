import { expect, test } from '@playwright/test';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const file = 'site04_roi3_2026-11-14_14d_mast1m.json';
const path = resolve(__dirname, '../../public/bundles', file);
const zeroFile = 'site01_roi6_2026-11-14_14d_mast1m.json';
const zeroPath = resolve(__dirname, '../../public/bundles', zeroFile);
const shots = resolve(__dirname, '../../docs/screenshots');

test.describe('PILOT information-hotspot traceability', () => {
  test.skip(!existsSync(path), 'run npm run sync-bundles first');
  const raw = existsSync(path) ? JSON.parse(readFileSync(path, 'utf8')) : null;
  const zeroRaw = existsSync(zeroPath) ? JSON.parse(readFileSync(zeroPath, 'utf8')) : null;

  test('toggle plots the bundle top ten and method without recomputing values', async ({ page }) => {
    const block = raw.derived.hotspots;
    await page.goto(`/?bundle=${file}`);
    await page.getByTestId('polar-map').scrollIntoViewIfNeeded();
    await page.getByTestId('polar-area').selectOption('Site04');
    await page.getByTestId('hotspot-toggle').check();
    const overlay = page.getByTestId('hotspot-overlay');
    await expect(overlay).toBeVisible();
    await expect(overlay).toHaveAttribute('data-result-id', block.result_id);
    await expect(overlay).toHaveAttribute('data-label', block.label);
    for (const tile of block.top_tiles) {
      const marker = page.getByTestId(`hotspot-marker-${tile.rank}`);
      await expect(marker).toHaveAttribute('data-result-id', tile.result_id);
      await expect(marker).toHaveAttribute('data-label', tile.label);
      await expect(marker).toHaveAttribute('data-tile-id', tile.tile_id);
      await expect(marker).toHaveAttribute('data-score', String(tile.score));
    }
    const caption = page.getByTestId('hotspot-caption');
    await expect(caption).toContainText(block.method.caption);
    await expect(caption).toHaveAttribute('data-result-id', block.result_id);
    await page.getByTestId('polar-map').screenshot({ path: `${shots}/11-information-hotspots-pilot.png` });
  });

  test('zero-positive bundle discloses missing clone-covered critical sensitivity', async ({ page }) => {
    test.skip(!zeroRaw, 'run npm run sync-bundles first');
    const block = zeroRaw.derived.hotspots;
    await page.goto(`/?bundle=${zeroFile}`);
    await page.getByTestId('polar-map').scrollIntoViewIfNeeded();
    await page.getByTestId('hotspot-toggle').check();
    await expect(page.getByTestId('hotspot-caption')).toContainText(block.zero_state_caption);
    await expect(page.getByTestId('hotspot-marker-1')).toHaveAttribute('data-score', String(block.top_tiles[0].score));
  });
});
