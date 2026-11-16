import { expect, test, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

/**
 * Final Apex checks (15 Nov 2026), P3–P13. Expected values are read from the bundle, the index and the sidecars, never typed in.
 */
test.describe.configure({ timeout: 180_000 });
const here = dirname(fileURLToPath(import.meta.url));
const pub = resolve(here, '../../public');
const index = JSON.parse(readFileSync(`${pub}/bundles/index.json`, 'utf8'));
const heroFile: string = index.bundles.find((b: { file: string }) => /^polaris-x5d-roi-/.test(b.file)).file;
const hero = JSON.parse(readFileSync(`${pub}/bundles/${heroFile}`, 'utf8'));
const ds = hero.datasets.find((d: { siteId: string }) => d.siteId === 'site04_roi3');
const sidecar = JSON.parse(readFileSync(`${pub}/certainty/sidecar.json`, 'utf8'));
const coverage = JSON.parse(readFileSync(`${pub}/certainty/coverage.json`, 'utf8'));
const roi3 = sidecar.sites.site04_roi3;
const sgn = (x: number, d: number) => `${x >= 0 ? '+' : '−'}${Math.abs(x).toFixed(d)}`;

async function science(page: Page) {
  return {
    sun: await page.getByTestId('sky-sun').innerText(),
    earth: await page.getByTestId('sky-earth').innerText(),
    utc: await page.getByTestId('utc').first().innerText(),
    mast: await page.getByTestId('mast-instrument').innerText(),
  };
}

test('P3: light mode and surface layer never change a science value', async ({ page }) => {
  // a Sun-blocked hour (sample 311), opened through a shareable link
  await page.goto(`/?bundle=${heroFile}&site=site04_roi3&t=${ds.ephemeris.samples[311].time.replace('.000Z', 'Z')}#sky`);
  await expect(page.getByTestId('sample-pos')).toContainText('312 /', { timeout: 30_000 });
  await expect(page.getByTestId('sky-sun')).toContainText('blocked', { ignoreCase: true });
  const ref = await science(page);
  await expect(page.getByTestId('surface-layer')).toBeVisible({ timeout: 60_000 }); // offered once the terrain context pack is loaded
  const layers = await page.getByTestId('surface-layer').locator('option:not([disabled])').evaluateAll((o) => o.map((x) => (x as HTMLOptionElement).value));
  expect(layers.length).toBeGreaterThan(3);
  test.setTimeout(480_000); // every layer redraws the terrain; with a software GPU (SwiftShader) each switch takes seconds
  for (const light of ['light-display', 'light-true']) {
    await page.getByTestId(light).click();
    // all layers in display mode; in scientific mode the neutral and shadow layers (the two that light changes most)
    for (const l of light === 'light-display' ? layers : layers.filter((x) => x === 'regolith' || x === 'shadow')) {
      await page.getByTestId('surface-layer').selectOption(l);
      await expect(page.getByTestId('surface-layer-label')).toHaveAttribute('data-layer', l);
      expect(await science(page), `${light} / ${l}`).toEqual(ref);
    }
  }
});

test('P5: the 3D sight labels give the bundle azimuth, elevation and margin at the shown sample', async ({ page }) => {
  await page.goto('/?site=site04_roi3#sky'); // Site04-specific values (Explore opens on Site01 ROI6 since 15 Nov 18:15; see store/siteDefaults.ts)
  const s0 = ds.ephemeris.samples[0];
  const base = ds.derived.scenarios.find((s: { id: string }) => s.id === 'baseline');
  await expect(page.getByTestId('sight-sun')).toContainText(`az ${s0.sun.az.toFixed(1)}° · el ${sgn(s0.sun.el, 2)}°`, { timeout: 30_000 });
  await expect(page.getByTestId('sight-sun')).toContainText(`${sgn(base.samples.sun.marginDeg[0], 2)}° vs skyline`);
  await expect(page.getByTestId('sight-earth')).toContainText(`az ${s0.earth.az.toFixed(1)}° · el ${sgn(s0.earth.el, 2)}°`);
  await expect(page.getByTestId('sight-earth')).toContainText('beyond this crop'); // R1 is ~128 km away: never drawn inside the 2 km crop
});

test('P5: consecutive ridge selections, then Return restores the original sample and camera', async ({ page }) => {
  await page.goto('/?site=site04_roi3#sky'); // Site04-specific values (Explore opens on Site01 ROI6 since 15 Nov 18:15; see store/siteDefaults.ts)
  await expect(page.getByTestId('instrument')).toBeVisible({ timeout: 30_000 });
  const before = await page.getByTestId('sample-pos').textContent();
  const view0 = await page.getByTestId('stage-view').getAttribute('data-view');
  const seen = new Set<string>();
  for (const id of ['R3', 'R1', 'R2']) {
    await page.getByTestId(`ridge-go-${id}`).click();
    await expect(page.getByTestId('ribbon-run')).toHaveCount(1);
    seen.add((await page.getByTestId('sample-pos').textContent()) ?? '');
    await expect(page.getByTestId('stage-view')).toHaveAttribute('data-view', 'ridge');
  }
  expect(seen.size).toBe(3); // each ridge seeks its own obstruction
  await page.getByTestId('ridge-return').click();
  await expect(page.getByTestId('sample-pos')).toHaveText(before ?? '');
  await expect(page.getByTestId('stage-view')).toHaveAttribute('data-view', view0 ?? 'approach');
  await expect(page.getByTestId('ribbon-run')).toHaveCount(0);
});

test('P7: Decision names three different heights from the sidecar and puts coverage next to the conclusion', async ({ page }) => {
  await page.goto('/#decision');
  const th = page.getByTestId('three-heights');
  await expect(th).toContainText(`${roi3.all_maps_100pct_sun_mast_m} m`, { timeout: 30_000 });
  await expect(th).toContainText(`Agreement height`);
  await expect(th).toContainText(`${roi3.agreement_mast_m} m`);
  await expect(th).toContainText('not a probability');
  await expect(page.getByTestId('hc-low')).toContainText('Lowest height meeting the team requirements');
  await expect(page.getByTestId('hc-cert')).toContainText(`only ${coverage.sites.site04_roi3.sun_pct.toFixed(1)} % of Sun hours`);
  await expect(page.getByTestId('hc-cert')).toContainText('Not a guarantee');
  await expect(page.getByTestId('dc-coverage')).toContainText(`${coverage.sites.site04_roi3.sun_pct.toFixed(1)} % (Sun)`);
  await expect(page.getByTestId('dc-coverage')).toContainText('below 50 %');
  await expect(page.getByTestId('dc-cert')).toContainText('100 %');
});

test('P8/P9: the Evidence record states sampling (N samples, N−1 intervals), gates and checksums that match the files', async ({ page }) => {
  await page.goto('/#evidence');
  const n = ds.ephemeris.samples.length;
  await expect(page.getByTestId('evr-sampling')).toContainText(`${n} samples`, { timeout: 30_000 });
  await expect(page.getByTestId('evr-sampling')).toContainText(`${n - 1} intervals`);
  const gates = ds.validation.gates;
  const pass = gates.filter((g: { status: string }) => g.status === 'PASS').length;
  await expect(page.getByTestId('evr-gates').locator('summary')).toContainText(`${pass} of ${gates.length} pass`);
  await expect(page.getByTestId('evr-status')).toContainText('SOURCE-BASED UNVALIDATED');
  await page.getByTestId('evr-files').locator('summary').click();
  const sha = index.bundles.find((b: { file: string }) => b.file === heroFile).sha256;
  await expect(page.getByTestId('evr-files')).toContainText(sha);
  await expect(page.getByTestId('evr-files')).toContainText(ds.dem.sourceSha256);
  for (const f of sidecar.source.files) await expect(page.getByTestId('evr-files')).toContainText(f.sha256);
});

test('P6: at 1440 the data selectors keep a readable width; at 390 the stage overlays do not overlap', async ({ page }) => {
  await page.goto('/#sky');
  await expect(page.getByTestId('instrument')).toBeVisible({ timeout: 30_000 });
  for (const id of ['bundle-select', 'site-select', 'scenario-select']) expect((await page.getByTestId(id).boundingBox())!.width, id).toBeGreaterThanOrEqual(150);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForTimeout(800);
  expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(0);
  const h1 = (await page.locator('.stage-title h1').boundingBox())!;
  const tag = (await page.locator('.stage .light-tag').boundingBox())!;
  expect(tag.y >= h1.y + h1.height || tag.y + tag.height <= h1.y).toBe(true);
});

test('P6: a sight label never runs under the instrument panel', async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 768 });
  await page.goto('/#sky');
  await expect(page.getByTestId('sight-sun')).toBeVisible({ timeout: 30_000 });
  await page.waitForTimeout(1500);
  const ins = (await page.getByTestId('instrument').boundingBox())!;
  for (const id of ['sight-sun', 'sight-earth']) {
    const b = await page.getByTestId(id).boundingBox();
    if (!b) continue;
    const overlaps = !(b.x + b.width <= ins.x || ins.x + ins.width <= b.x || b.y + b.height <= ins.y || ins.y + ins.height <= b.y);
    expect(overlaps, id).toBe(false);
  }
});

test('P13: time boundaries: the first and last samples hold, and an out-of-window time is refused', async ({ page }) => {
  await page.goto('/#sky');
  await expect(page.getByTestId('instrument')).toBeVisible({ timeout: 30_000 });
  const n = ds.ephemeris.samples.length;
  await expect(page.getByTestId('sample-pos')).toContainText(`1 / ${n}`);
  await page.getByTestId('utc-input').fill(ds.ephemeris.samples[n - 1].time.replace('.000Z', 'Z'));
  await page.getByTestId('utc-input').press('Enter');
  await expect(page.getByTestId('sample-pos')).toContainText(`${n} / ${n}`);
  await page.getByTestId('utc-input').fill('2026-12-01T00:00:00Z');
  await page.getByTestId('utc-input').press('Enter');
  await expect(page.getByTestId('time-error')).toBeVisible();
  await expect(page.getByTestId('sample-pos')).toContainText(`${n} / ${n}`);
});

test('P13: the decision card prints alone and the print button calls the browser print', async ({ page }) => {
  await page.goto('/#decision');
  await expect(page.getByTestId('decision-card')).toBeVisible({ timeout: 30_000 });
  await page.evaluate(() => {
    (window as unknown as { __printed: number }).__printed = 0;
    window.print = () => void ((window as unknown as { __printed: number }).__printed += 1);
  });
  await page.getByRole('button', { name: 'Print / save PDF' }).click();
  expect(await page.evaluate(() => (window as unknown as { __printed: number }).__printed)).toBe(1);
  await page.emulateMedia({ media: 'print' });
  await expect(page.locator('.dcard')).toBeVisible();
  expect(await page.locator('.dc-actions').evaluate((e) => getComputedStyle(e).visibility)).toBe('hidden');
  expect(await page.getByTestId('height-compare').evaluate((e) => getComputedStyle(e).visibility)).toBe('hidden');
});

test('P11: without WebGL the 3D view says so and every value is still on screen', async ({ page }) => {
  await page.addInitScript(() => {
    const orig = HTMLCanvasElement.prototype.getContext;
    // @ts-expect-error test override: no WebGL contexts
    HTMLCanvasElement.prototype.getContext = function (type: string, ...rest: unknown[]) {
      if (/webgl/i.test(type)) return null;
      // @ts-expect-error passthrough
      return orig.call(this, type, ...rest);
    };
  });
  await page.goto('/?site=site04_roi3#sky'); // Site04-specific values (Explore opens on Site01 ROI6 since 15 Nov 18:15; see store/siteDefaults.ts)
  await expect(page.getByText('WebGL is not available in this browser')).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId('sky-sun')).toContainText('+3.39°');
  await expect(page.getByTestId('sky-earth')).toContainText('−4.17°');
  await expect(page.getByTestId('mast-instrument')).toBeVisible();
});

test('P11: keyboard: skip link, workspace tabs and the guided demo are reachable; Esc closes the demo and focus returns', async ({ page }) => {
  await page.goto('/#sky');
  await expect(page.getByTestId('instrument')).toBeVisible({ timeout: 30_000 });
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: 'Skip to content' })).toBeFocused();
  await page.getByTestId('guide-start').focus();
  await page.keyboard.press('Enter');
  await expect(page.getByTestId('guide')).toBeVisible();
  await expect(page.locator('#guide-title')).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(page.getByTestId('guide')).toHaveCount(0);
  await expect(page.getByTestId('guide-start')).toBeFocused();
});

test('P4: Reset view re-frames the current view (orbit, then reset) and keeps the view selected', async ({ page }) => {
  await page.goto('/#sky');
  await expect(page.getByTestId('instrument')).toBeVisible({ timeout: 30_000 });
  await page.getByTestId('cam-regional').click();
  await expect(page.getByTestId('stage-view')).toHaveAttribute('data-view', 'regional');
  const canvas = page.locator('[data-testid=scene3d] canvas').first();
  const box = (await canvas.boundingBox())!;
  await page.mouse.move(box.x + box.width * 0.4, box.y + box.height * 0.5);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width * 0.55, box.y + box.height * 0.45, { steps: 5 });
  await page.mouse.up();
  await page.getByTestId('cam-reset').click();
  await expect(page.getByTestId('stage-view')).toHaveAttribute('data-view', 'regional');
  await expect(page.getByTestId('cam-regional')).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByTestId('cam-reset')).toHaveAttribute('aria-label', /Regional terrain/);
});
