import { expect, test, type Page } from '@playwright/test';
import { existsSync, mkdirSync, readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

/**
 * v2 T2 (docs/v2/PHASE_7_T2_PLAN.md): the Blender whole-Moon globe, the display-only analytics layers and the
 * "query any point" panel. Expected values come from the staged files (globe manifest, layer manifest, the copied
 * any-site summary), never from constants typed here. The nearest-row reference below is a plain haversine on the
 * 1,737.4 km sphere, the same rule the panel documents.
 */
const here = dirname(fileURLToPath(import.meta.url));
const pub = resolve(here, '../../public');
const shots = resolve(here, '../../playwright-report/v2-t2'); // git-ignored: the globe renders show NASA-derived imagery
mkdirSync(shots, { recursive: true });
const readJson = (p: string) => (existsSync(p) ? JSON.parse(readFileSync(p, 'utf8')) : null);
const globeMan = readJson(`${pub}/globe/globe_manifest.json`);
const hasBlender = !!globeMan?.globes?.some((g: { kind: string }) => g.kind === 'blender');
const layerMan = readJson(`${pub}/layers/v2/manifest.json`);
const builtLayers: { id: string; title: string; label: string }[] = (layerMan?.layers ?? []).filter((l: { built: boolean }) => l.built);
const summary = readJson(`${pub}/anysite/precompute_summary.json`);
type Row = { id: string; name: string; status: string; lat: number | null; lon: number | null; sun_pct?: number };
const doneRows: (Row & { lat: number; lon: number })[] = (summary?.sites ?? []).filter((r: Row) => r.status === 'done' && typeof r.lat === 'number');

function nearest(lat: number, lon: number) {
  const D = Math.PI / 180;
  let best = doneRows[0];
  let bd = Infinity;
  for (const r of doneRows) {
    const a = Math.sin(((r.lat - lat) * D) / 2) ** 2 + Math.cos(lat * D) * Math.cos(r.lat * D) * Math.sin(((r.lon - lon) * D) / 2) ** 2;
    const d = 2 * 1737.4 * Math.asin(Math.min(1, Math.sqrt(a)));
    if (d < bd) {
      bd = d;
      best = r;
    }
  }
  return { row: best, km: bd };
}

async function openGlobe(page: Page, errors: string[], url = '/?site=site04_roi3#sky') {
  page.on('pageerror', (e) => errors.push(String(e)));
  await page.goto(url);
  await expect(page.getByTestId('scene3d')).toHaveAttribute('data-context', 'loaded', { timeout: 30_000 });
  if ((await page.getByTestId('global-moon').count()) === 0) await page.getByTestId('globe-open').click();
  await expect(page.getByTestId('global-moon')).toHaveAttribute('data-loaded', 'true', { timeout: 90_000 });
}

/** Same rule as traceability.spec.ts, scoped to the globe overlay: every number with a unit needs a source and a label. */
async function traceGlobe(page: Page) {
  return page.getByTestId('global-moon').evaluate((root) => {
    const pattern = /(?:^|[\s(≥≤+−–/:])[-+−]?\d+(?:\.\d+)?(?:\s*[–-]\s*[-+−]?\d+(?:\.\d+)?)?\s*(?:%|h|m|°)(?=$|[\s,.;)·/])/u;
    const classify = (v: string) => {
      const n = v.toUpperCase();
      return n.includes('DEMO') || n.includes('SCENARIO') || n.includes('SOURCE-BASED') || n.includes('SOURCE_BASED') || n === 'VALIDATED' || n.includes('VALIDATED_NASA_JPL');
    };
    const visible = (el: Element) => {
      const s = getComputedStyle(el);
      const r = el.getBoundingClientRect();
      return s.display !== 'none' && s.visibility !== 'hidden' && r.width > 0 && r.height > 0;
    };
    const matches = (el: Element) => pattern.test((el.textContent ?? '').replace(/\s+/g, ' ').trim());
    const cands = Array.from(root.querySelectorAll('*')).filter((el) => visible(el) && matches(el) && !Array.from(el.children).some(matches));
    const bad: string[] = [];
    for (const el of cands) {
      let n: Element | null = el;
      let trace: string | null = null;
      let ok = false;
      while (n) {
        trace ??= n.getAttribute('data-result-id') ?? n.getAttribute('data-source');
        for (const a of ['data-label', 'data-classification']) {
          const v = n.getAttribute(a);
          if (v && classify(v)) ok = true;
        }
        n = n.parentElement;
      }
      if (!trace || !ok) bad.push((el.textContent ?? '').replace(/\s+/g, ' ').trim().slice(0, 140));
    }
    return { scanned: cands.length, bad };
  });
}

test.describe('v2 whole-Moon globe, layers and query panel', () => {
  test.setTimeout(180_000);

  test('the Blender globe is shown (SVS only as a fallback) and the card names its builder', async ({ page }) => {
    const errors: string[] = [];
    await page.setViewportSize({ width: 1512, height: 982 });
    await openGlobe(page, errors);
    const globe = page.getByTestId('global-moon');
    const note = page.getByTestId('globe-asset-note');
    if (hasBlender) {
      await expect(globe).toHaveAttribute('data-asset', 'blender');
      await expect(note).toContainText('blender/v2/globe.py');
      await expect(note).toContainText('Khronos glTF Blender I/O');
      await expect(note).toContainText('LROC WAC');
    } else {
      await expect(globe).toHaveAttribute('data-asset', 'svs');
      await expect(note).toContainText('fallback');
    }
    await expect(page.getByTestId('globe-card')).toContainText('VISUAL CONTEXT, not numerical terrain');
    await page.waitForTimeout(3000); // flight to the site
    await page.screenshot({ path: `${shots}/globe-blender-1512x982.png` });
    expect(errors).toEqual([]);
  });

  test('every built layer drapes, shows its legend, label and source, and changes no instrument value', async ({ page }) => {
    test.skip(!hasBlender || builtLayers.length === 0, 'needs the Blender globe and staged layers (web/scripts/sync_v2_layers.py)');
    const errors: string[] = [];
    await page.setViewportSize({ width: 1512, height: 982 });
    await openGlobe(page, errors);
    const before = await page.getByTestId('instrument').innerText();
    const globe = page.getByTestId('global-moon');
    await page.getByTestId('globe-tab-layers').click();
    await expect(page.getByTestId('globe-tab-layers')).toHaveAttribute('aria-selected', 'true');
    for (const l of builtLayers) {
      await page.getByTestId(`globe-layer-${l.id}`).check();
      await expect(globe).toHaveAttribute('data-drape', l.id, { timeout: 30_000 });
      const detail = page.getByTestId('globe-layer-detail');
      await expect(detail).toContainText(l.title);
      await expect(detail).toHaveAttribute('data-label', /SOURCE-BASED · UNVALIDATED/);
      await expect(detail).toHaveAttribute('data-source', /layers\/v2\/manifest\.json/);
      await expect(page.getByTestId('globe-legend')).toBeVisible();
      await expect(page.getByTestId('globe-layer-label')).toContainText('SOURCE-BASED · UNVALIDATED');
      if (['coverage-res', 'slope', 'earth-vis', 'sun-vis'].includes(l.id)) {
        await page.waitForTimeout(400);
        await page.screenshot({ path: `${shots}/globe-layer-${l.id}-1512x982.png` });
      }
      const t = await traceGlobe(page); // legend values, stats and labels of this layer
      expect(t.bad, `untraced values with layer ${l.id}`).toEqual([]);
    }
    await page.getByTestId('globe-layer-opacity').fill('0.4');
    await page.getByTestId('globe-layer-none').check();
    await expect(globe).toHaveAttribute('data-drape', 'none');
    expect(await page.getByTestId('instrument').innerText()).toBe(before);
    expect(errors).toEqual([]);
  });

  test('click on the globe -> nearest precomputed row with provenance and the reproduce command', async ({ page }) => {
    test.skip(doneRows.length === 0, 'needs anysite/precompute_summary.json (npm run sync-bundles)');
    const errors: string[] = [];
    await page.setViewportSize({ width: 1512, height: 982 });
    await openGlobe(page, errors);
    await page.waitForTimeout(3000); // let the flight settle
    // click a point of the globe canvas that no panel covers (checked with elementFromPoint), right of the globe panel
    const box = (await page.getByTestId('global-moon').boundingBox())!;
    const pt = { x: box.x + box.width * 0.55, y: box.y + box.height * 0.32 };
    expect(await page.evaluate(({ x, y }) => document.elementFromPoint(x, y)?.tagName, pt)).toBe('CANVAS');
    await page.mouse.click(pt.x, pt.y);
    await expect(page.getByTestId('query-picked')).toContainText('globe click');
    await expect(page.getByTestId('query-lat')).not.toHaveValue(''); // filled from the pick
    await expect(page.getByTestId('query-lon')).not.toHaveValue('');
    const lat = Number(await page.getByTestId('query-lat').inputValue());
    const lon = Number(await page.getByTestId('query-lon').inputValue());
    expect(Number.isFinite(lat) && Number.isFinite(lon)).toBe(true);
    await expect(page.getByTestId('globe-tab-query')).toHaveAttribute('aria-selected', 'true'); // a pick opens the Query tab
    const exp = nearest(lat, lon);
    const res = page.getByTestId('query-result');
    await expect(res).toHaveAttribute('data-site-id', exp.row.id);
    await expect(page.getByTestId('query-site-name')).toHaveText(exp.row.name);
    await expect(page.getByTestId('query-sun')).toContainText(`${exp.row.sun_pct!.toFixed(2)} % of hourly samples`);
    await expect(res).toHaveAttribute('data-label', 'SOURCE-BASED · UNVALIDATED');
    await expect(page.getByTestId('query-command')).toContainText(`science.anysite.solve --lat ${exp.row.lat} --lon ${exp.row.lon} --mast 1`);
    await page.getByTestId('query-provenance').locator('summary').click();
    await expect(page.getByTestId('query-provenance')).toContainText('JPL Horizons responses (SHA-256)');
    await expect(page.getByTestId('query-provenance')).toContainText('sha256');
    // nothing is computed: with no solver behind the proxy the panel says so and the button stays disabled
    await expect(page.getByTestId('query-solver')).toHaveAttribute('data-state', /down|running/, { timeout: 10_000 });
    if ((await page.getByTestId('query-solver').getAttribute('data-state')) === 'down') {
      await expect(page.getByTestId('query-solver-down')).toContainText('Solver API not running');
      await expect(page.getByTestId('query-compute')).toBeDisabled();
    }
    await page.screenshot({ path: `${shots}/globe-query-click-1512x982.png` });
    const t = await traceGlobe(page);
    console.log(`GLOBE_TRACE scanned=${t.scanned} failed=${t.bad.length}`);
    expect(t.bad).toEqual([]);
    expect(t.scanned).toBeGreaterThan(8);
    expect(errors).toEqual([]);
  });

  test('keyboard: layers by arrow keys, a typed point by Enter, the site marker button', async ({ page }) => {
    test.skip(doneRows.length === 0, 'needs anysite/precompute_summary.json');
    const errors: string[] = [];
    await page.setViewportSize({ width: 1440, height: 900 });
    await openGlobe(page, errors);
    // the tabs are buttons in the tab order
    await page.getByTestId('globe-tab-layers').focus();
    await page.keyboard.press('Enter');
    await expect(page.getByTestId('globe-tab-layers')).toHaveAttribute('aria-selected', 'true');
    if (hasBlender && builtLayers.length) {
      await page.getByTestId('globe-layer-none').focus();
      await page.keyboard.press('ArrowDown');
      await expect(page.getByTestId(`globe-layer-${builtLayers[0].id}`)).toBeChecked();
    }
    await page.getByTestId('globe-tab-query').focus();
    await page.keyboard.press('Enter');
    await page.getByTestId('query-lat').focus();
    await page.keyboard.type('-89.47409');
    await page.keyboard.press('Tab');
    await expect(page.getByTestId('query-lon')).toBeFocused();
    await page.keyboard.type('-137.3813');
    await page.keyboard.press('Enter');
    const exp = nearest(-89.47409, -137.3813);
    await expect(page.getByTestId('query-result')).toHaveAttribute('data-site-id', exp.row.id);
    await expect(page.getByTestId('query-distance')).toContainText(exp.km < 0.05 ? 'at the picked point' : 'km from the picked point');
    await page.keyboard.press('Tab'); // Query button
    await page.keyboard.press('Tab'); // Use site marker
    await expect(page.getByTestId('query-marker')).toBeFocused();
    await page.keyboard.press('Enter');
    await expect(page.getByTestId('query-picked')).toContainText('site marker');
    expect(errors).toEqual([]);
  });

  test('compute now through a running solver API (route mocked in this test) shows the answer with its label', async ({ page }) => {
    const errors: string[] = [];
    // Route mock of science/api/server.py: GET v1/health, POST v1/solve -> the captured real answer
    // (web/tests/fixtures/v1-solve-result.site01_roi6.json, checked against the API by science/api/tests/test_web_fixture.py).
    const solveFx = readJson(resolve(here, '../fixtures/v1-solve-result.site01_roi6.json'));
    await page.route('**/solver-api/v1/health', (r) => r.fulfill({ json: { ok: true, version: '1.0.0', precomputed_sites: 1252 } }));
    let body: Record<string, unknown> | null = null;
    await page.route('**/solver-api/v1/solve', (r) => {
      body = r.request().postDataJSON();
      return r.fulfill({ json: solveFx.response });
    });
    await page.setViewportSize({ width: 1440, height: 900 });
    await openGlobe(page, errors);
    await page.getByTestId('globe-tab-query').click();
    await page.getByTestId('query-lat').fill('-85.5');
    await page.getByTestId('query-lon').fill('30');
    await page.getByTestId('query-go').click();
    await expect(page.getByTestId('query-solver')).toHaveAttribute('data-state', 'running');
    await page.getByTestId('query-compute').click();
    const out = page.getByTestId('query-computed');
    const r = solveFx.response;
    await expect(out).toContainText(`${r.metrics.sun_center_visible_pct_hourly_samples.value.toFixed(2)} % of hourly samples`);
    await expect(out).toContainText(`${r.site_hash}.json`);
    await expect(out).toContainText(r.terrain.near_product);
    await expect(out).toHaveAttribute('data-label', r.label);
    await expect(page.getByTestId('query-computed-command')).toHaveText(r.reproduce.recompute);
    expect(body).toMatchObject({ world: 'moon', lat: -85.5, lon: 30, mast_m: 1, days: 14, step_h: 1, compute: true });
    expect(errors).toEqual([]);
  });

  test('deep link globe=1&gl=… restores the globe and its layer', async ({ page }) => {
    test.skip(!hasBlender || !builtLayers.some((l) => l.id === 'slope'), 'needs the Blender globe and the slope layer');
    const errors: string[] = [];
    await openGlobe(page, errors, '/?site=site04_roi3&globe=1&gl=slope#sky');
    await page.getByTestId('globe-tab-layers').click();
    await expect(page.getByTestId('globe-layer-slope')).toBeChecked();
    await expect(page.getByTestId('global-moon')).toHaveAttribute('data-drape', 'slope', { timeout: 30_000 });
    await page.getByTestId('globe-layer-earth-vis').check();
    await expect.poll(() => page.evaluate(() => location.search)).toContain('gl=earth-vis');
    expect(await page.evaluate(() => location.search)).toContain('globe=1');
    await page.getByTestId('globe-tab-site').click();
    await page.getByTestId('globe-enter').click();
    await expect.poll(() => page.evaluate(() => location.search)).not.toContain('globe=1');
    expect(errors).toEqual([]);
  });

  test('390 px phone: tabbed sheet, no horizontal scroll, no overlap, every panel reachable', async ({ page }) => {
    const errors: string[] = [];
    await page.setViewportSize({ width: 390, height: 844 });
    await openGlobe(page, errors);
    const noScroll = () => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1);
    expect(await noScroll()).toBe(true);
    const tabs = page.locator('.globe-tabs');
    await expect(tabs).toBeVisible();
    await expect(page.getByTestId('globe-card')).toBeVisible();
    const box = (sel: string) => page.locator(sel).boundingBox();
    const overlap = (a: { x: number; y: number; width: number; height: number } | null, b: typeof a) =>
      !!a && !!b && a.x < b.x + b.width && b.x < a.x + a.width && a.y < b.y + b.height && b.y < a.y + a.height;
    expect(overlap(await box('.globe-tabs'), await box('[data-testid="globe-card"]'))).toBe(false);
    // the sheet leaves the upper part of the globe visible
    const sheet = (await box('.globe-panel'))!;
    const stage = (await box('[data-testid="global-moon"]'))!;
    expect(sheet.height).toBeLessThanOrEqual(stage.height * 0.56);
    expect(sheet.x).toBeGreaterThanOrEqual(stage.x);
    expect(sheet.x + sheet.width).toBeLessThanOrEqual(stage.x + stage.width + 0.5);
    await page.screenshot({ path: `${shots}/globe-mobile-site-390.png` });
    await page.getByTestId('globe-tab-layers').click();
    await expect(page.getByTestId('globe-card')).toBeHidden();
    await expect(page.getByTestId('globe-layers')).toBeVisible();
    expect(overlap(await box('.globe-tabs'), await box('[data-panel="layers"]'))).toBe(false);
    if (hasBlender && builtLayers.length) {
      await page.getByTestId(`globe-layer-${builtLayers[0].id}`).check();
      await expect(page.getByTestId('globe-legend')).toBeVisible();
    }
    expect(await noScroll()).toBe(true);
    await page.screenshot({ path: `${shots}/globe-mobile-layers-390.png` });
    await page.getByTestId('globe-tab-query').click();
    await expect(page.getByTestId('query-panel')).toBeVisible();
    await page.getByTestId('query-marker').click();
    if (doneRows.length) await expect(page.getByTestId('query-result')).toBeVisible();
    expect(overlap(await box('.globe-tabs'), await box('[data-panel="query"]'))).toBe(false);
    expect(await noScroll()).toBe(true);
    await page.screenshot({ path: `${shots}/globe-mobile-query-390.png` });
    await page.getByTestId('globe-tab-site').click();
    await page.getByTestId('globe-enter').click();
    await expect(page.getByTestId('global-moon')).toHaveCount(0);
    expect(errors).toEqual([]);
  });
});
