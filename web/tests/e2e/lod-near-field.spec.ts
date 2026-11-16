import { expect, test } from '@playwright/test';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

/**
 * 5D Phase 9.4: the near-field LOD layer (±7 km at 5 m, quadtree tiles streamed by camera distance) loads, says
 * "display only", and changes no number. The tiles are git-ignored NASA-derived rasters: built by
 * tools/terrain/build_lod_tiles.py into public/context/lod/; the test skips when they are absent.
 */
const here = dirname(fileURLToPath(import.meta.url));
const manifestPath = resolve(here, '../../public/context/lod/site04_roi3/manifest.json');
const hasTiles = existsSync(manifestPath);
const manifest = hasTiles ? JSON.parse(readFileSync(manifestPath, 'utf8')) : null;
const overlap = (a: { x: number; y: number; width: number; height: number }, b: { x: number; y: number; width: number; height: number }) =>
  a.x < b.x + b.width && b.x < a.x + a.width && a.y < b.y + b.height && b.y < a.y + a.height;

test.describe('near-field LOD (display only)', () => {
  test.skip(!hasTiles, 'no LOD tiles in public/context/lod (run tools/terrain/build_lod_tiles.py)');

  test('toggle streams the ±7 km tiles, shows "display only", and leaves every instrument number unchanged', async ({ page }) => {
    test.setTimeout(240_000); // software GL in headless Chromium: ~20 s to stream all tiles alone, longer in a busy full run
    const errors: string[] = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    await page.goto('/?site=site04_roi3#sky');
    const scene = page.getByTestId('scene3d');
    await expect(scene).toHaveAttribute('data-lod', 'available', { timeout: 30_000 });
    const panel = page.getByTestId('lod-panel');
    await expect(panel).toHaveAttribute('data-label', /SOURCE-BASED.*DISPLAY ONLY/);
    await expect(panel).toHaveAttribute('data-source', new RegExp(manifest.source.sha256.slice(0, 12)));
    const before = await page.getByTestId('instrument').innerText();
    const ribbon = await page.getByTestId('margin-ribbon').getAttribute('aria-label');

    await page.getByTestId('lod-toggle').click();
    await expect(scene).toHaveAttribute('data-lod', 'on');
    const label = page.getByTestId('lod-label');
    await expect(label).toContainText(/display only/i);
    await expect(label).toContainText('never computed from these tiles');
    // tiles stream in and finish; the finest drawn level near the observer is 5 m
    await expect.poll(async () => Number(await panel.getAttribute('data-drawn')), { timeout: 60_000 }).toBeGreaterThan(1);
    await expect.poll(async () => Number(await panel.getAttribute('data-pending')), { timeout: 150_000 }).toBe(0);
    await expect(panel).toHaveAttribute('data-finest', String(manifest.levels.at(-1).spacingM));
    await expect(label).toContainText('tiles drawn');

    expect(await page.getByTestId('instrument').innerText()).toBe(before);
    expect(await page.getByTestId('margin-ribbon').getAttribute('aria-label')).toBe(ribbon);
    // the panel does not cover the instrument
    expect(overlap((await panel.boundingBox())!, (await page.getByTestId('instrument').boundingBox())!)).toBe(false);

    await page.getByTestId('lod-toggle').click();
    await expect(scene).toHaveAttribute('data-lod', 'available');
    await expect(scene).toHaveAttribute('data-context', 'loaded', { timeout: 30_000 });
    expect(await page.getByTestId('instrument').innerText()).toBe(before);
    expect(errors).toEqual([]);
  });

  test('?lod=1 opens with the layer on; the camera views keep working', async ({ page }) => {
    test.setTimeout(120_000);
    const errors: string[] = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    await page.goto('/?site=site04_roi3&lod=1#sky');
    await expect(page.getByTestId('scene3d')).toHaveAttribute('data-lod', 'on', { timeout: 30_000 });
    await expect(page.getByTestId('lod-label')).toContainText(/display only/i);
    for (const id of ['regional', 'overhead', 'approach']) {
      await page.getByTestId(`cam-${id}`).click();
      await page.waitForTimeout(600);
    }
    await expect.poll(async () => Number(await page.getByTestId('lod-panel').getAttribute('data-drawn')), { timeout: 60_000 }).toBeGreaterThan(1);
    expect(errors).toEqual([]);
  });
});
