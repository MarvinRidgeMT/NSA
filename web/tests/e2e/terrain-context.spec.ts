import { expect, test, type Page } from '@playwright/test';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

/**
 * Rebuild Phase 4/5 checks (14 Nov 2026): the 5 m crop is drawn inside its 80 m regional context with display-model
 * shadows, surface layers are display only (no instrument value changes when the layer changes), and a registered image
 * layer is offered only where one covers the crop. Expected values come from the context pack and the visual-layers file.
 */
const here = dirname(fileURLToPath(import.meta.url));
const pub = resolve(here, '../../public');
const shots = resolve(here, '../../docs/screenshots/rebuild');
const ctxPath = `${pub}/context/site04_roi3/context.json`;
const hasCtx = existsSync(ctxPath);
const ctx = hasCtx ? JSON.parse(readFileSync(ctxPath, 'utf8')) : null;
const layersPath = `${pub}/visual/visual_layers.json`;
const layers = existsSync(layersPath) ? JSON.parse(readFileSync(layersPath, 'utf8')).layers : [];
const RESULTS = 'site04_roi3_2026-11-14_14d_mast1m.json';
const LAYER_IDS = ['regolith', 'albedo', 'elevation', 'slope', 'normal', 'coverage', 'shadow'];

async function openExplore(page: Page, errors: string[]) {
  page.on('pageerror', (e) => errors.push(String(e)));
  // these checks were written for Site04 ROI3; Explore opens on Site01 ROI6 since 15 Nov 18:15 (store/siteDefaults.ts)
  await page.goto('/?site=site04_roi3#sky');
  await expect(page.getByTestId('scene3d')).toHaveAttribute('data-context', 'loaded', { timeout: 30_000 });
}
const overlap = (a: { x: number; y: number; width: number; height: number }, b: { x: number; y: number; width: number; height: number }) =>
  a.x < b.x + b.width && b.x < a.x + a.width && a.y < b.y + b.height && b.y < a.y + a.height;

test.describe('terrain context (display only)', () => {
  test.skip(!hasCtx, 'no context pack in public/context (run tools/terrain/build_terrain_context.py and npm run sync-bundles)');

  test('Explore draws the 5 m crop inside the 80 m context and says what the surface is', async ({ page }) => {
    const errors: string[] = [];
    await openExplore(page, errors);
    const chip = page.getByTestId('surface-layer-label');
    await expect(chip).toContainText('VISUAL');
    await expect(chip).toContainText('80 m PGDA 90 context');
    await expect(page.getByTestId('geometry-mode')).toContainText('REAL SURFACE');
    await page.locator('details.scene-note summary').click({ force: true });
    await expect(page.locator('details.scene-note')).toContainText(`${ctx.regional.n}² × ${ctx.regional.spacingM} m`);
    await expect(page.locator('details.scene-note')).toContainText('never set a visible/blocked state');
    expect(errors).toEqual([]);
  });

  test('surface layers are display only: every layer renders and no instrument value changes', async ({ page }) => {
    const errors: string[] = [];
    await openExplore(page, errors);
    const select = page.getByTestId('surface-layer');
    expect(await select.locator('option').evaluateAll((o) => o.map((x) => (x as HTMLOptionElement).value))).toEqual(LAYER_IDS);
    const before = await page.getByTestId('instrument').innerText();
    const ribbon = await page.getByTestId('margin-ribbon').getAttribute('aria-label');
    for (const id of LAYER_IDS) {
      if (id === 'albedo' && (await select.locator('option[value=albedo]').evaluate((o) => (o as HTMLOptionElement).disabled))) continue;
      await select.selectOption(id);
      await expect(page.getByTestId('surface-layer-label')).toHaveAttribute('data-layer', id);
      await page.waitForTimeout(250);
      expect(await page.getByTestId('instrument').innerText(), `instrument changed on layer ${id}`).toBe(before);
    }
    expect(await page.getByTestId('margin-ribbon').getAttribute('aria-label')).toBe(ribbon);
    expect(errors).toEqual([]);
  });

  test('image layer is offered only where a registered image covers the crop, and is labelled VISUAL', async ({ page }) => {
    const errors: string[] = [];
    await openExplore(page, errors);
    const opt = page.getByTestId('surface-layer').locator('option[value=albedo]');
    const scene = page.getByTestId('scene3d');
    // Site04 ROI3: no registered window covers it unless the layers file says so
    const site04Covered = layers.some((l: { siteId?: string }) => l.siteId === 'site04_roi3' || l.siteId === 'shackleton');
    if (!site04Covered) {
      expect(await opt.evaluate((o) => (o as HTMLOptionElement).disabled)).toBe(true);
      await expect(scene).toHaveAttribute('data-albedo', 'none');
    }
    const site01 = layers.find((l: { siteId?: string }) => l.siteId === 'connecting');
    test.skip(!site01, 'visual_layers.json has no Site01 layer yet (LROC NAC window not complete)');
    await page.getByTestId('site-select').selectOption({ label: 'Connecting Ridge (Site01 ROI6)' }).catch(async () => {
      await page.getByTestId('site-select').selectOption({ index: 0 });
    });
    await expect(scene).toHaveAttribute('data-context', 'loaded', { timeout: 30_000 });
    await expect(scene).toHaveAttribute('data-albedo', site01.id, { timeout: 30_000 });
    await page.getByTestId('surface-layer').selectOption('albedo');
    const chip = page.getByTestId('surface-layer-label');
    await expect(chip).toContainText(site01.label);
    await expect(chip).toContainText(site01.productId);
    await expect(chip).toContainText('not mission-time lighting');
    await page.waitForTimeout(1500);
    await page.screenshot({ path: `${shots}/site01-roi6-lroc-nac-avg-visual-1440x900.png` });
    expect(errors).toEqual([]);
  });

  test('camera row with the layer picker does not collide with the instrument or the temporal bar at 1440 × 900', async ({ page }) => {
    const errors: string[] = [];
    await page.setViewportSize({ width: 1440, height: 900 });
    await openExplore(page, errors);
    const cams = (await page.getByTestId('camera-views').boundingBox())!;
    const ins = (await page.getByTestId('instrument').boundingBox())!;
    const temporal = (await page.locator('.temporal').boundingBox())!;
    const pick = (await page.getByTestId('surface-layer').boundingBox())!;
    expect(overlap(cams, ins)).toBe(false);
    expect(overlap(cams, temporal)).toBe(false);
    expect(pick.x + pick.width).toBeLessThanOrEqual(cams.x + cams.width + 1);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    expect(errors).toEqual([]);
  });

  test('South-pole context camera and time stepping work without page errors; evidence captures', async ({ page }) => {
    test.setTimeout(180_000); // software GL in CI is slow; the Mac GPU needs a few seconds
    const errors: string[] = [];
    await page.setViewportSize({ width: 1512, height: 982 });
    await openExplore(page, errors);
    await page.waitForTimeout(2500);
    await page.screenshot({ path: `${shots}/explore-approach-regolith-1512x982.png` });
    await page.getByTestId('cam-context').click();
    await page.waitForTimeout(2500);
    await page.screenshot({ path: `${shots}/explore-context-regolith-1512x982.png` });
    for (const id of ['elevation', 'slope', 'coverage', 'shadow']) {
      await page.getByTestId('surface-layer').selectOption(id);
      await page.waitForTimeout(700);
      await page.screenshot({ path: `${shots}/explore-context-${id}-1512x982.png` });
    }
    await page.getByTestId('surface-layer').selectOption('regolith');
    const utc0 = await page.locator('.temporal').innerText();
    await page.locator('.temporal input[type=range]').focus();
    for (let i = 0; i < 6; i++) await page.keyboard.press('ArrowRight');
    await page.waitForTimeout(800);
    expect(await page.locator('.temporal').innerText()).not.toBe(utc0);
    await page.screenshot({ path: `${shots}/explore-context-regolith-sample7-1512x982.png` });
    expect(errors).toEqual([]);
  });

  test('global Moon: visual-context globe with the site marker, then enter the terrain on the regional framing', async ({ page }) => {
    test.setTimeout(180_000);
    const errors: string[] = [];
    await page.setViewportSize({ width: 1512, height: 982 });
    await openExplore(page, errors);
    const before = await page.getByTestId('instrument').innerText();
    await page.getByTestId('globe-open').click();
    const globe = page.getByTestId('global-moon');
    await expect(globe).toHaveAttribute('data-loaded', 'true', { timeout: 90_000 });
    const card = page.getByTestId('globe-card');
    await expect(card).toContainText('VISUAL CONTEXT, not numerical terrain');
    await expect(card).toContainText('NASA SVS 14959');
    await expect(card).toContainText('Shackleton Rim');
    expect(await page.getByTestId('instrument').innerText()).toBe(before); // the globe never changes a value
    await page.waitForTimeout(4000); // flight to the site
    await page.screenshot({ path: `${shots}/global-moon-site-marker-1512x982.png` });
    await page.getByTestId('globe-enter').click();
    await expect(page.getByTestId('scene3d')).toHaveAttribute('data-context', 'loaded', { timeout: 30_000 });
    await expect(page.getByTestId('cam-context')).toHaveAttribute('aria-pressed', 'true');
    await expect(page.getByTestId('global-moon')).toHaveCount(0);
    expect(errors).toEqual([]);
  });

  test('skyline-only bundle keeps the horizon panorama and offers no surface layers', async ({ page }) => {
    await page.goto(`/?bundle=${RESULTS}#sky`);
    await expect(page.getByTestId('geometry-mode')).toContainText('HORIZON GEOMETRY');
    await expect(page.getByTestId('surface-layer')).toHaveCount(0);
    await expect(page.getByTestId('cam-context')).toHaveCount(0);
  });

  test('phone width: the stage, the chip and the picker fit without horizontal scrolling', async ({ page }) => {
    const errors: string[] = [];
    await page.setViewportSize({ width: 390, height: 844 });
    await openExplore(page, errors);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
    await expect(page.getByTestId('surface-layer')).toBeVisible();
    await page.screenshot({ path: `${shots}/explore-mobile-390.png`, fullPage: false });
    expect(errors).toEqual([]);
  });
});
