import { test, expect, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

/**
 * S13 (18 Nov 2026): "Check a spot" on the globe, in the layout Sid set the same day: no side panel, a card beside a pressed
 * pin, a box along the bottom for typed coordinates, and a marker with its answer card wherever the Moon is clicked. Every expected value is read here from a file: the NASA values from the
 * web copy's manifest check points (which scripts/build_pgda69_web.py read from the original TIFs), our own results from the
 * certainty sidecar, coordinates and the match distance from the ROI bundle. Nothing is typed in.
 */
test.use({ storageState: { cookies: [], origins: [] } });

const __dirname = dirname(fileURLToPath(import.meta.url));
type Check = { name: string; siteId?: string; lat: number; lonE: number; row: number; col: number; inCopy: boolean; sunRaw: number; earthRaw: number; sun3x3: [number, number]; earth3x3: [number, number] };
const manifest = JSON.parse(readFileSync(resolve(__dirname, '../../public/pgda69-spot/manifest.json'), 'utf8')) as {
  grid: { scale: number; cellM: number; fullEdgeLatDeg: number };
  copy: { halfWidthM: number; inscribedLatDeg: number; row0: number; col0: number; widthPx: number; heightPx: number };
  checks: Check[];
  meaning: { sunShort: string };
};
const meaning = manifest.meaning;
type Row = { mast_m: number; metric: string; min: number; max: number; n_clones: number };
const sidecar = JSON.parse(readFileSync(resolve(__dirname, '../../public/certainty/sidecar.json'), 'utf8')) as { sites: Record<string, { sampled_masts_m: number[]; certainty_curve: Row[] }> };
const bundle = JSON.parse(readFileSync(resolve(__dirname, '../../../data/viewer/polaris-x5d-roi-2026-11-14-v2.json'), 'utf8')) as {
  datasets: { siteId: string; site: { name: string; latitudePlanetocentricDeg: number; longitudeEastDeg: number }; derived: { scenarios: { kind?: string; observer?: { mastM: number }; samples?: unknown; parameters?: { east_m?: number; north_m?: number } }[] } }[];
};
// S14: the any-site file (original, not the web copy) and its done row nearest to a point, found by largest dot product
const anySite = JSON.parse(readFileSync(resolve(__dirname, '../../../data/anysite/precompute_summary.json'), 'utf8')) as { sites: { id: string; status: string; lat: number; lon: number; slope_deg: number }[] };
function nearestAnySite(lat: number, lon: number) {
  const v = (la: number, lo: number) => [Math.cos((la * Math.PI) / 180) * Math.cos((lo * Math.PI) / 180), Math.cos((la * Math.PI) / 180) * Math.sin((lo * Math.PI) / 180), Math.sin((la * Math.PI) / 180)];
  const q = v(lat, lon);
  const dot = (s: { lat: number; lon: number }) => v(s.lat, s.lon).reduce((n, x, i) => n + x * q[i], 0);
  return anySite.sites.filter((s) => s.status === 'done').reduce((a, b) => (dot(b) > dot(a) ? b : a));
}
const pct = (raw: number) => `${(raw * manifest.grid.scale * 100).toFixed(1)} %`;
/** what the card says beside a value: the lowest and highest of the cells around it, e.g. "6.3–85.2 % within one 60 m cell" */
const span = (r: [number, number]) => `${(r[0] * manifest.grid.scale * 100).toFixed(1)}–${(r[1] * manifest.grid.scale * 100).toFixed(1)} % within one ${manifest.grid.cellM} m cell`;
const steps = bundle.datasets.flatMap((d) => d.derived.scenarios).filter((s) => s.kind === 'position_offset').map((s) => Math.hypot(s.parameters!.east_m!, s.parameters!.north_m!));
const stepM = Math.min(...steps);
const range = (r: Row) => (r.min === r.max ? `${r.min.toFixed(1)} %` : `${r.min.toFixed(1)}–${r.max.toFixed(1)} %`);

const globeDir = resolve(__dirname, '../../public/globe');
const hasGlobe = existsSync(globeDir) && readdirSync(globeDir).some((f) => f.endsWith('.glb'));
const sev = (v: { impact?: string | null; id: string; nodes: { target: unknown[] }[] }[]) => v.filter((x) => x.impact === 'serious' || x.impact === 'critical').map((x) => `${x.id}: ${x.nodes.map((n) => n.target.join(' ')).join(', ')}`);

async function openGlobe(page: Page) {
  await page.goto('/');
  await expect(page.locator('[data-testid=simple-globe][data-shown=true]')).toBeVisible({ timeout: 45_000 });
  await expect(page.getByTestId('simple-mode')).not.toHaveAttribute('data-intro', /.+/, { timeout: 30_000 });
  await expect(page.getByTestId('spot-box')).toBeVisible();
}
async function typePoint(page: Page, lat: number | string, lon: number | string) {
  await page.getByTestId('spot-lat').fill(String(lat));
  await page.getByTestId('spot-lon').fill(String(lon));
  await page.getByTestId('spot-lon').press('Enter');
}
const answer = (page: Page) => page.getByTestId('spot-answer');
const pin = (page: Page, id: string) => page.getByTestId(`globe-pin-${id}`).getByRole('button');
type GlobeHook = { camera: { position: { x: number; y: number; z: number; length(): number } }; nav: { zoomNow: number; zoomMin: number } };
/** a point of the Moon's disc clear of the pins and the bottom box */
async function moonPoint(page: Page) {
  const view = (await page.locator('.s-globe-view').boundingBox())!;
  return { view, x: view.x + view.width / 2 + 90, y: view.y + view.height / 2 - 110 };
}

test.describe('S13 Check a spot', () => {
  test.skip(!hasGlobe, 'no Moon model in public/globe (git-ignored NASA asset)');

  test('the NASA map copy is not fetched until the box is used, and then only the tiles a point needs', async ({ page }) => {
    const asked: string[] = [];
    page.on('request', (r) => r.url().includes('/pgda69-spot/') && asked.push(r.url().split('/pgda69-spot/')[1]));
    await openGlobe(page);
    await page.waitForTimeout(1500);
    expect(asked).toEqual([]);
    await page.getByTestId('spot-lat').focus();
    await expect.poll(() => asked).toEqual(['manifest.json']);
    const site = bundle.datasets[0].site;
    await typePoint(page, site.latitudePlanetocentricDeg, site.longitudeEastDeg);
    await expect(answer(page)).toHaveAttribute('data-coverage', 'cell');
    const tiles = asked.filter((a) => a.startsWith('tiles/'));
    expect(tiles.length).toBeGreaterThanOrEqual(1);
    expect(tiles.length).toBeLessThanOrEqual(4);
  });

  test('the side panel is gone and nothing it said has left the page', async ({ page }) => {
    await openGlobe(page);
    await expect(page.locator('.s-globe-card')).toHaveCount(0);
    // the Moon's view runs the full width of the window
    const view = (await page.locator('.s-globe-view').boundingBox())!;
    expect([view.x, view.width]).toEqual([0, page.viewportSize()!.width]);
    // the top bar, the Expert banner, the credits and "About this view" are where they were
    for (const id of ['simple-banner', 'mode-expert', 'simple-footer', 'globe-about', 'simple-mast-stepper']) await expect(page.getByTestId(id)).toBeVisible();
    // the heading, the question and each site's row are still in the page, as a list of buttons
    const list = page.getByTestId('globe-sites');
    await expect(list.getByRole('heading', { level: 1 })).toHaveText('The Moon’s south pole');
    await expect(list).toContainText('Does a lander here keep the Sun? Pick a site to fly down to its terrain.');
    for (const d of bundle.datasets) {
      const row = page.getByTestId(`globe-row-${d.siteId}`);
      await expect(row.getByRole('button')).toHaveCount(1);
      await expect(row.locator('.s-globe-site-name')).toHaveText(d.site.name);
      // the row says what the pin says
      const label = (await pin(page, d.siteId).getAttribute('aria-label'))!;
      expect(label).toContain(await row.locator('.s-globe-site-line').innerText());
    }
    // the shimmer legend and the honesty label moved into About this view
    const about = page.getByTestId('globe-about');
    await about.locator('summary').click();
    await expect(about.getByTestId('globe-legend')).toBeVisible();
    await expect(about.getByTestId('globe-legend')).toContainText('terrain variants disagree (Sun in sight, max − min)');
    await expect(about.locator('.s-honesty')).toHaveText('SOURCE-BASED · UNVALIDATED');
    await expect(about.locator('a.s-honesty')).toHaveAttribute('href', '?mode=expert#evidence');
  });

  test('first visit: a hint by the box, gone after the first click and not shown again', async ({ page }) => {
    await openGlobe(page);
    await expect(page.getByTestId('spot-hint')).toHaveText('Click a pin or anywhere on the Moon');
    const hint = (await page.getByTestId('spot-hint').boundingBox())!;
    const box = (await page.getByTestId('spot-box').boundingBox())!;
    expect(box.y - (hint.y + hint.height)).toBeLessThan(60); // near the box, above it
    expect(hint.y + hint.height).toBeLessThanOrEqual(box.y + 1);
    const p = await moonPoint(page);
    await page.mouse.click(p.x, p.y);
    await expect(page.getByTestId('spot-hint')).toHaveCount(0);
    await page.reload();
    await expect(page.locator('[data-testid=simple-globe][data-shown=true]')).toBeVisible({ timeout: 45_000 });
    await expect(page.getByTestId('simple-mode')).not.toHaveAttribute('data-intro', /.+/, { timeout: 30_000 });
    await expect(page.getByTestId('spot-box')).toBeVisible();
    await expect(page.getByTestId('spot-hint')).toHaveCount(0);
  });

  for (const d of bundle.datasets) {
    test(`pin card: ${d.site.name} shows what its panel row showed, and flies down to the terrain`, async ({ page }) => {
      await openGlobe(page);
      const row = page.getByTestId(`globe-row-${d.siteId}`);
      const line = await row.locator('.s-globe-site-line').innerText();
      const spread = await row.locator('.s-globe-site-spread').textContent();
      const side = sidecar.sites[d.siteId];
      await pin(page, d.siteId).click();
      // pressing a pin opens its card; it no longer flies at once
      const card = page.getByTestId('pin-card');
      await expect(card).toBeVisible();
      await expect(page.getByTestId('simple-mode')).toHaveAttribute('data-place', 'globe');
      await expect(card.getByRole('heading')).toHaveText(d.site.name);
      await expect(page.getByTestId('pin-card-line')).toHaveText(line);
      if (side) {
        const mast = Number((await page.getByTestId('simple-mast-current').innerText()).replace(/[^\d.]/g, ''));
        const sun = side.certainty_curve.find((r) => r.mast_m === mast && r.metric === 'sun_centre_pct')!;
        await expect(page.getByTestId('pin-card-line')).toContainText(`Sun in sight ${range(sun)} at a ${mast} m mast`);
        await expect(page.getByTestId('pin-card-spread')).toHaveText(spread!);
        expect(spread).toContain(sun.max === sun.min ? `all ${sun.n_clones} terrain variants agree` : `differ by ${(sun.max - sun.min).toFixed(1)} points`);
      } else {
        await expect(page.getByTestId('pin-card-line')).toHaveText('No answer: the certainty sidecar has no rows for this site');
        await expect(page.getByTestId('pin-card-spread')).toHaveCount(0);
      }
      await expect(card).toContainText('terrain variants disagree (Sun in sight, max − min)');
      await expect(card.locator('.s-honesty')).toHaveText('SOURCE-BASED · UNVALIDATED');
      // the card stands next to its pin
      const [cb, pb] = [(await card.boundingBox())!, (await pin(page, d.siteId).boundingBox())!];
      const gapX = Math.max(cb.x - (pb.x + pb.width), pb.x - (cb.x + cb.width));
      expect(gapX).toBeGreaterThanOrEqual(0);
      expect(gapX).toBeLessThan(60);
      await page.getByTestId('pin-card-fly').click();
      await expect(page.getByTestId('simple-mode')).toHaveAttribute('data-place', 'site', { timeout: 10_000 });
      await expect(page.getByTestId('simple-site')).toHaveText(d.site.name);
    });
  }

  test('pin card: Esc, its close button and a click on empty space each close it; one card at a time', async ({ page }) => {
    const [a, b] = bundle.datasets;
    await openGlobe(page);
    const card = page.getByTestId('pin-card');
    await pin(page, a.siteId).click();
    await expect(card).toHaveAttribute('data-site', a.siteId);
    await page.keyboard.press('Escape');
    await expect(card).toHaveCount(0);
    await pin(page, a.siteId).click();
    await page.getByTestId('pin-card-close').click();
    await expect(card).toHaveCount(0);
    await pin(page, a.siteId).click();
    await expect(card).toBeVisible();
    // empty space: the sky beside the Moon
    const view = (await page.locator('.s-globe-view').boundingBox())!;
    await page.mouse.click(view.x + 14, view.y + 14);
    await expect(card).toHaveCount(0);
    await expect(page.getByTestId('spot-card')).toHaveCount(0);
    // another pin replaces the card; a click on the Moon replaces it with that spot's card
    await pin(page, a.siteId).click();
    await pin(page, b.siteId).click();
    await expect(card).toHaveCount(1);
    await expect(card).toHaveAttribute('data-site', b.siteId);
    const p = await moonPoint(page);
    await page.mouse.click(p.x, p.y);
    await expect(page.getByTestId('spot-card')).toBeVisible();
    await expect(card).toHaveCount(0);
    await pin(page, a.siteId).click();
    await expect(card).toBeVisible();
    await expect(page.getByTestId('spot-card')).toHaveCount(0);
    await expect(page.getByTestId('spot-mark')).not.toHaveAttribute('data-on', 'true');
  });

  test('keyboard and screen readers: the off-screen site list opens the same cards (Tab, Enter), Enter again flies, Esc gives focus back', async ({ page }) => {
    const d = bundle.datasets[1];
    await openGlobe(page);
    const list = page.getByTestId('globe-sites');
    // off screen until a button in it has keyboard focus
    expect((await list.boundingBox())!.width).toBeLessThanOrEqual(1);
    await page.locator('#simple-main').focus();
    const reached: string[] = [];
    for (let i = 0; i < 60 && reached.length < bundle.datasets.length; i++) {
      await page.keyboard.press('Tab');
      const id = await page.evaluate(() => document.activeElement?.closest('[data-testid^="globe-row-"]')?.getAttribute('data-testid') ?? null);
      if (id) reached.push(id.replace('globe-row-', ''));
    }
    expect(reached).toEqual(bundle.datasets.map((x) => x.siteId));
    expect((await list.boundingBox())!.width).toBeGreaterThan(200);
    await expect(list).toBeInViewport({ ratio: 1 });
    const btn = page.getByTestId(`globe-row-${d.siteId}`).getByRole('button');
    await btn.focus();
    await expect(btn).toHaveAccessibleName(new RegExp(d.site.name.replace(/[()]/g, '\\$&')));
    await page.keyboard.press('Enter');
    await expect(page.getByTestId('pin-card')).toHaveAttribute('data-site', d.siteId);
    await expect(btn).toHaveAttribute('aria-expanded', 'true');
    await expect(page.getByTestId('pin-card-fly')).toBeFocused();
    await page.keyboard.press('Escape');
    await expect(page.getByTestId('pin-card')).toHaveCount(0);
    await expect(btn).toBeFocused();
    await page.keyboard.press('Enter');
    await expect(page.getByTestId('pin-card-fly')).toBeFocused();
    await page.keyboard.press('Enter');
    await expect(page.getByTestId('simple-mode')).toHaveAttribute('data-place', 'site', { timeout: 10_000 });
    await expect(page.getByTestId('simple-site')).toHaveText(d.site.name);
  });

  for (const d of bundle.datasets) {
    test(`a typed point at ${d.site.name} shows the file values: ours from the sidecar, NASA's from the map`, async ({ page }) => {
      const k = manifest.checks.find((c) => c.siteId === d.siteId)!;
      await openGlobe(page);
      await typePoint(page, d.site.latitudePlanetocentricDeg, d.site.longitudeEastDeg);
      const a = answer(page);
      await expect(a).toHaveAttribute('data-coverage', 'cell');
      // the cell and the stored values are the ones the build script read from the TIF
      await expect(a).toHaveAttribute('data-row', String(k.row));
      await expect(a).toHaveAttribute('data-col', String(k.col));
      await expect(a).toHaveAttribute('data-sun-raw', String(k.sunRaw));
      await expect(a).toHaveAttribute('data-earth-raw', String(k.earthRaw));
      await expect(page.getByTestId('spot-nasa-sun')).toHaveText(pct(k.sunRaw));
      await expect(page.getByTestId('spot-nasa-earth')).toHaveText(pct(k.earthRaw));
      await expect(page.getByTestId('spot-nasa-sun-range')).toHaveText(span(k.sun3x3));
      await expect(page.getByTestId('spot-nasa-earth-range')).toHaveText(span(k.earth3x3));
      await expect(page.getByTestId('spot-nasa-label')).toHaveText('18.6-year average (NASA PGDA 69, Mazarico et al. 2011), not our 14-day window.');
      await expect(page.getByTestId('spot-nasa')).toContainText('counts as visible if any part of its disc shows');
      await expect(page.getByTestId('spot-nasa')).toContainText(meaning.sunShort);
      // Sid, 18 Nov: the Sun map is the long-term average fraction of the disc in view (label title and column), not "any part"
      expect(meaning.sunShort).toBe('average share of the Sun’s disc in view');
      await expect(page.getByTestId('spot-nasa')).not.toContainText('share of hours with any part');
      // Sid, 18 Nov: no warning trigger. The value ("here") and the range around it are always shown, however wide the range
      await expect(page.getByTestId('spot-nasa')).toContainText(`${pct(k.sunRaw)} here`);
      await expect(page.getByTestId('spot-nasa')).toContainText(`${pct(k.earthRaw)} here`);
      await expect(page.getByTestId('spot-warn')).toHaveCount(0);
      await expect(page.getByTestId('spot-nasa')).not.toContainText(/warning|threshold|points or more/i);
      // our own result: this site, at no distance, with the sidecar's rows at the mast on screen (or the reason there are none)
      const ours = page.getByTestId('spot-ours');
      await expect(ours).toHaveAttribute('data-match', d.siteId);
      await expect(page.getByTestId('spot-ours-site')).toHaveText(d.site.name);
      await expect(page.getByTestId('spot-ours-distance')).toHaveText('0 m from your point');
      await expect(ours).toContainText(`within ${Math.round(stepM / 2)} m of a site: half the ${Math.round(stepM)} m step`);
      // the card names the file and the field the step was read from
      await expect(ours).toContainText('(east_m / north_m of its position_offset scenarios in polaris-x5d-roi-2026-11-14-v2.json)');
      const side = sidecar.sites[d.siteId];
      if (side) {
        const mast = Number((await page.getByTestId('simple-mast-current').innerText()).replace(/[^\d.]/g, ''));
        expect(side.sampled_masts_m).toContain(mast);
        const sun = side.certainty_curve.find((r) => r.mast_m === mast && r.metric === 'sun_centre_pct')!;
        const both = side.certainty_curve.find((r) => r.mast_m === mast && r.metric === 'both_centre_pct')!;
        await expect(page.getByTestId('spot-ours-sun')).toHaveText(range(sun));
        await expect(page.getByTestId('spot-ours-both')).toHaveText(range(both));
        await expect(page.getByTestId('spot-ours-mast')).toHaveText(`${mast} m mast · ${sun.n_clones} terrain variants`);
      } else {
        await expect(page.getByTestId('spot-ours-none')).toContainText('the certainty sidecar has no rows for this site');
        await expect(page.getByTestId('spot-ours-sun')).toHaveCount(0);
      }
      // S14 Part A (18 Nov 2026, Sid): the slope row is now filled from the nearest computed point of the any-site file, in
      // the nearest-point wording. This replaces the S13 assertion that it read "Not yet available" (simple-s14.spec.ts holds
      // the rest: the row's point and distance, and "Not yet available" when the file cannot be loaded).
      const nearSlope = nearestAnySite(d.site.latitudePlanetocentricDeg, d.site.longitudeEastDeg);
      await expect(page.getByTestId('spot-slope-value')).toHaveText(`${nearSlope.slope_deg.toFixed(1)}°`);
      await expect(page.getByTestId('spot-slope')).toContainText('not at your spot itself');
      // screen readers hear the values when the check finishes
      const spoken = page.getByTestId('spot-spoken');
      await expect(spoken).toHaveAttribute('role', 'status');
      await expect(spoken).toContainText(`Sun ${pct(k.sunRaw)}`);
      await expect(spoken).toContainText(`Earth ${pct(k.earthRaw)}`);
      await expect(spoken).toContainText(`Slope at the nearest computed point: ${nearSlope.slope_deg.toFixed(1)}°.`); // S14: was 'Slope: not yet available.'
      // the marker is down and the card stands next to it
      await expect(page.getByTestId('spot-mark')).toHaveAttribute('data-on', 'true');
      // (both are placed by the globe's next drawn frame)
      await expect
        .poll(async () => {
          const [cb, mb] = [(await page.getByTestId('spot-card').boundingBox())!, (await page.getByTestId('spot-mark').boundingBox())!];
          const gapX = Math.max(cb.x - mb.x, mb.x - (cb.x + cb.width));
          return gapX > 0 && gapX < 60;
        })
        .toBe(true);
      // a site we computed: both ways on are offered, and the terrain button flies down to this site
      await expect(page.getByTestId('spot-zoom')).toBeVisible();
      await expect(page.getByTestId('spot-terrain-note')).toHaveCount(0);
      await expect(page.getByTestId('spot-fly')).toHaveText('Fly down to the terrain');
      await page.getByTestId('spot-fly').click();
      await expect(page.getByTestId('simple-mode')).toHaveAttribute('data-place', 'site', { timeout: 10_000 });
      await expect(page.getByTestId('simple-site')).toHaveText(d.site.name);
    });
  }

  test('our result follows the mast picked in the top bar, and is not shown away from a site', async ({ page }) => {
    await openGlobe(page);
    await page.getByTestId('simple-mast-up').click();
    const mast = Number((await page.getByTestId('simple-mast-current').innerText()).replace(/[^\d.]/g, ''));
    // a site the sidecar sampled at that height
    const d = bundle.datasets.find((x) => sidecar.sites[x.siteId]?.sampled_masts_m.includes(mast))!;
    const side = sidecar.sites[d.siteId];
    expect(side.sampled_masts_m.indexOf(mast)).toBeGreaterThan(0);
    await typePoint(page, d.site.latitudePlanetocentricDeg, d.site.longitudeEastDeg);
    await expect(page.getByTestId('spot-ours')).toHaveAttribute('data-match', d.siteId);
    await expect(page.getByTestId('spot-ours-mast')).toContainText(`${mast} m mast`);
    await expect(page.getByTestId('spot-ours-sun')).toHaveText(range(side.certainty_curve.find((r) => r.mast_m === mast && r.metric === 'sun_centre_pct')!));
    // 0.01° of latitude away from the pole is about 300 m: outside the stated distance, so no result of ours is shown
    await typePoint(page, d.site.latitudePlanetocentricDeg + 0.01, d.site.longitudeEastDeg);
    await expect(page.getByTestId('spot-ours')).toHaveAttribute('data-match', 'none');
    await expect(page.getByTestId('spot-ours-none')).toContainText(`The nearest site we computed is ${d.site.name}`);
    await expect(page.getByTestId('spot-ours-none')).toContainText(`only within ${Math.round(stepM / 2)} m of it`);
    await expect(page.getByTestId('spot-ours-sun')).toHaveCount(0);
    await expect(answer(page)).toHaveAttribute('data-coverage', 'cell');
    // away from a site there is no terrain to fly down to, and the card says so plainly
    await expect(page.getByTestId('spot-fly')).toHaveCount(0);
    await expect(page.getByTestId('spot-terrain-note')).toHaveText(`Ground-level terrain exists only for the ${bundle.datasets.length} sites we computed; this spot is not one of them.`);
    await expect(page.getByTestId('spot-zoom')).toBeVisible();
  });

  test('"Zoom in here" flies the globe camera close over the spot', async ({ page }) => {
    const k = manifest.checks.find((c) => !c.siteId && c.inCopy)!;
    await openGlobe(page);
    await typePoint(page, k.lat, k.lonE);
    await expect(answer(page)).toHaveAttribute('data-lat', String(k.lat));
    await page.getByTestId('spot-zoom').click();
    // the camera ends over the spot (model frame: globeMath.moonDir) at the closest zoom this Moon model allows
    const want = [-Math.cos((k.lat * Math.PI) / 180) * Math.sin((k.lonE * Math.PI) / 180), Math.sin((k.lat * Math.PI) / 180), -Math.cos((k.lat * Math.PI) / 180) * Math.cos((k.lonE * Math.PI) / 180)];
    await expect
      .poll(
        () =>
          page.evaluate((w) => {
            const g = (window as unknown as { __polarisGlobe: GlobeHook }).__polarisGlobe;
            const c = g.camera.position;
            const l = c.length();
            return [Math.acos(Math.min(1, (c.x * w[0] + c.y * w[1] + c.z * w[2]) / l)) < 1e-6, Math.abs(g.nav.zoomNow - g.nav.zoomMin) < 1e-9 && g.nav.zoomMin < 1];
          }, want),
        { timeout: 8000 },
      )
      .toEqual([true, true]);
    // the marker is at the middle of the view, the card is still open beside it, and the way back is offered
    const view = (await page.locator('.s-globe-view').boundingBox())!;
    const mark = (await page.getByTestId('spot-mark').boundingBox())!;
    expect(Math.hypot(mark.x - (view.x + view.width / 2), mark.y - (view.y + view.height / 2))).toBeLessThan(2);
    await expect(page.getByTestId('spot-card')).toBeVisible();
    await expect(page.getByTestId('globe-home')).toBeVisible();
    await page.getByTestId('globe-home').click();
    await expect(page.getByTestId('globe-home')).toHaveCount(0, { timeout: 8000 });
  });

  test('other check points across the copy show the values read from the TIFs', async ({ page }) => {
    await openGlobe(page);
    const inner = (k: Check) => k.row - manifest.copy.row0 > 0 && k.col - manifest.copy.col0 > 0 && k.row - manifest.copy.row0 < manifest.copy.heightPx - 1 && k.col - manifest.copy.col0 < manifest.copy.widthPx - 1;
    const some = manifest.checks.filter((k) => !k.siteId && k.inCopy && inner(k)).slice(0, 12);
    expect(some.length).toBe(12);
    for (const k of some) {
      await typePoint(page, k.lat, k.lonE);
      await expect(answer(page)).toHaveAttribute('data-lat', String(k.lat));
      await expect(answer(page)).toHaveAttribute('data-row', String(k.row));
      await expect(answer(page)).toHaveAttribute('data-col', String(k.col));
      await expect(page.getByTestId('spot-nasa-sun')).toHaveText(pct(k.sunRaw));
      await expect(page.getByTestId('spot-nasa-earth')).toHaveText(pct(k.earthRaw));
      await expect(page.getByTestId('spot-nasa-sun-range')).toHaveText(span(k.sun3x3));
      await expect(page.getByTestId('spot-nasa-earth-range')).toHaveText(span(k.earth3x3));
      await expect(page.getByTestId('spot-warn')).toHaveCount(0);
    }
  });

  test('points outside 85–90° S, off the web copy, or not coordinates at all say so plainly', async ({ page }) => {
    await openGlobe(page);
    // north of NASA's map
    await typePoint(page, -80, 20);
    await expect(answer(page)).toHaveAttribute('data-coverage', 'outside-map');
    await expect(page.getByTestId('spot-nasa-none')).toHaveText(`NASA’s map covers ${Math.abs(manifest.grid.fullEdgeLatDeg)}° S to the pole. This point is at 80.0000° S, outside it, so there is no NASA value to show.`);
    await expect(page.getByTestId('spot-nasa-sun')).toHaveCount(0);
    await expect(page.getByTestId('spot-ours')).toHaveAttribute('data-match', 'none');
    // on NASA's map but outside the part shipped
    const out = manifest.checks.find((k) => !k.inCopy)!;
    await typePoint(page, out.lat, out.lonE);
    await expect(answer(page)).toHaveAttribute('data-coverage', 'outside-copy');
    await expect(page.getByTestId('spot-nasa-none')).toContainText(`only a square of it centred on the pole, ${((2 * manifest.copy.halfWidthM) / 1000).toFixed(1)} km on a side in the map’s grid: all of it south of ${Math.abs(manifest.copy.inscribedLatDeg).toFixed(2)}° S`);
    await expect(page.getByTestId('spot-nasa-sun')).toHaveCount(0);
    // not a coordinate: the box is marked, the message is an alert, and the old card and marker are gone
    await typePoint(page, 'north pole', 20);
    await expect(page.getByTestId('spot-error')).toHaveAttribute('role', 'alert');
    await expect(page.getByTestId('spot-error')).toContainText('Latitude is not a number');
    await expect(page.getByTestId('spot-lat')).toHaveAttribute('aria-invalid', 'true');
    await expect(page.getByTestId('spot-lat')).toBeFocused();
    await expect(page.getByTestId('spot-card')).toHaveCount(0);
    await expect(page.getByTestId('spot-mark')).not.toHaveAttribute('data-on', 'true');
    await typePoint(page, -95, 20);
    await expect(page.getByTestId('spot-error')).toContainText('between −90 and 90');
    await typePoint(page, -89, 500);
    await expect(page.getByTestId('spot-error')).toContainText('Longitude must be between');
    await expect(page.getByTestId('spot-lon')).toBeFocused();
    await typePoint(page, '', '');
    await expect(page.getByTestId('spot-error')).toContainText('Enter a latitude and a longitude');
  });

  test('pasting "lat, lon" fills both boxes and checks; typing it into one box works too', async ({ page, context }) => {
    const d = bundle.datasets[1];
    const k = manifest.checks.find((c) => c.siteId === d.siteId)!;
    const text = `${d.site.latitudePlanetocentricDeg}, ${d.site.longitudeEastDeg}`;
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);
    await openGlobe(page);
    await page.evaluate((t) => navigator.clipboard.writeText(t), text);
    await page.getByTestId('spot-lat').focus();
    await page.keyboard.press('ControlOrMeta+v');
    await expect(page.getByTestId('spot-lat')).toHaveValue(String(d.site.latitudePlanetocentricDeg));
    await expect(page.getByTestId('spot-lon')).toHaveValue(String(d.site.longitudeEastDeg));
    await expect(answer(page)).toHaveAttribute('data-sun-raw', String(k.sunRaw));
    // typed into the latitude box alone
    await page.getByTestId('spot-lon').fill('');
    await page.getByTestId('spot-lat').fill(text.replace(',', ' '));
    await page.getByTestId('spot-lat').press('Enter');
    await expect(page.getByTestId('spot-lon')).toHaveValue(String(d.site.longitudeEastDeg));
    await expect(answer(page)).toHaveAttribute('data-row', String(k.row));
  });

  test('a click on the Moon drops a marker there and opens its card; a click that ends a drag does not', async ({ page }) => {
    await openGlobe(page);
    const { view, x, y } = await moonPoint(page);
    await page.mouse.click(x, y);
    await expect(answer(page)).toBeVisible();
    const lat = await page.getByTestId('spot-lat').inputValue();
    const lon = await page.getByTestId('spot-lon').inputValue();
    expect(lat).toMatch(/^-\d+\.\d{4}$/);
    expect(lon).toMatch(/^-?\d+\.\d{4}$/);
    await expect(answer(page)).toHaveAttribute('data-lat', String(Number(lat)));
    await expect(answer(page)).toHaveAttribute('data-lon', String(Number(lon)));
    await expect(page.getByTestId('spot-point')).toContainText('Placed by a click');
    await expect(page.getByTestId('spot-mark')).toHaveAttribute('data-on', 'true');
    // the marker stands under the pointer (the coordinates were rounded to four decimals) and the card next to the marker
    const mark = (await page.getByTestId('spot-mark').boundingBox())!;
    expect(Math.hypot(mark.x - x, mark.y - y)).toBeLessThan(2.5);
    const cb = (await page.getByTestId('spot-card').boundingBox())!;
    const gapX = Math.max(cb.x - mark.x, mark.x - (cb.x + cb.width));
    expect(gapX).toBeGreaterThan(0);
    expect(gapX).toBeLessThan(60);
    await expect(page.getByTestId('spot-zoom')).toBeVisible();
    // the same coordinates typed give the same answer (the click only supplies coordinates)
    const before = await answer(page).evaluate((el) => ({ ...el.dataset }));
    await typePoint(page, lat, lon);
    await expect(page.getByTestId('spot-point')).not.toContainText('Placed by a click');
    expect(await answer(page).evaluate((el) => ({ ...el.dataset }))).toEqual(before);
    // a drag turns the Moon and drops nothing: the card, the boxes and the answer stay as they were
    await page.mouse.move(view.x + view.width / 2 - 150, view.y + view.height / 2 + 40);
    await page.mouse.down();
    await page.mouse.move(view.x + view.width / 2 - 60, view.y + view.height / 2 + 10, { steps: 8 });
    await page.mouse.up();
    await page.waitForTimeout(300);
    await expect(page.getByTestId('spot-lat')).toHaveValue(lat);
    await expect(page.getByTestId('spot-lon')).toHaveValue(lon);
    expect(await answer(page).evaluate((el) => ({ ...el.dataset }))).toEqual(before);
    // the card follows its marker as the Moon turns
    const [m2, c2] = [(await page.getByTestId('spot-mark').boundingBox())!, (await page.getByTestId('spot-card').boundingBox())!];
    expect(Math.hypot(m2.x - mark.x, m2.y - mark.y)).toBeGreaterThan(20);
    const gap2 = Math.max(c2.x - m2.x, m2.x - (c2.x + c2.width));
    expect(gap2).toBeGreaterThan(0);
    expect(gap2).toBeLessThan(60);
    // a click on the sky closes the card and lifts the marker
    await page.mouse.click(view.x + 14, view.y + 14);
    await expect(page.getByTestId('spot-card')).toHaveCount(0);
    await expect(page.getByTestId('spot-mark')).not.toHaveAttribute('data-on', 'true');
    await expect(page.getByTestId('spot-error')).toHaveCount(0);
  });

  test('keyboard: Tab reaches the boxes, Enter checks, Esc closes the card and gives focus back', async ({ page }) => {
    const d = bundle.datasets[0];
    const k = manifest.checks.find((c) => c.siteId === d.siteId)!;
    await openGlobe(page);
    await page.locator('#simple-main').focus();
    let reached = false;
    for (let i = 0; i < 60 && !reached; i++) {
      await page.keyboard.press('Tab');
      reached = await page.evaluate(() => document.activeElement?.getAttribute('data-testid') === 'spot-lat');
    }
    expect(reached).toBe(true);
    const ring = await page.getByTestId('spot-lat').evaluate((el) => getComputedStyle(el).outlineWidth);
    expect(ring).toBe('2px');
    await page.keyboard.type(String(d.site.latitudePlanetocentricDeg));
    await page.keyboard.press('Tab');
    await expect(page.getByTestId('spot-lon')).toBeFocused();
    await page.keyboard.type(String(d.site.longitudeEastDeg));
    await page.keyboard.press('Enter');
    await expect(page.getByTestId('spot-nasa-sun')).toHaveText(pct(k.sunRaw));
    // focus stays in the box; Tab goes on to Check, and the card's own buttons can be reached too
    await expect(page.getByTestId('spot-lon')).toBeFocused();
    await page.keyboard.press('Tab');
    await expect(page.getByTestId('spot-check')).toBeFocused();
    await page.getByTestId('spot-zoom').focus();
    await expect(page.getByTestId('spot-zoom')).toBeFocused();
    await page.keyboard.press('Escape');
    await expect(page.getByTestId('spot-card')).toHaveCount(0);
    await expect(page.getByTestId('spot-lon')).toBeFocused();
    await expect(page.getByTestId('spot-mark')).not.toHaveAttribute('data-on', 'true');
    // Esc with nothing open leaves the globe as it is
    await page.keyboard.press('Escape');
    await expect(page.getByTestId('simple-mode')).toHaveAttribute('data-place', 'globe');
    // the card's close button works too
    await page.keyboard.press('Enter');
    await expect(page.getByTestId('spot-card')).toBeVisible();
    await page.getByTestId('spot-close').click();
    await expect(page.getByTestId('spot-card')).toHaveCount(0);
  });

  test('one Esc closes one thing: an open "About this view" first, then the card', async ({ page }) => {
    const d = bundle.datasets[0];
    await openGlobe(page);
    await typePoint(page, d.site.latitudePlanetocentricDeg, d.site.longitudeEastDeg);
    await expect(page.getByTestId('spot-card')).toBeVisible();
    await page.getByTestId('globe-about').locator('summary').click();
    await expect(page.getByTestId('globe-about')).toHaveAttribute('open', '');
    await expect(page.getByTestId('globe-about')).toContainText('Check a spot: a click is placed on a smooth sphere');
    await page.keyboard.press('Escape');
    await expect(page.getByTestId('globe-about')).not.toHaveAttribute('open', '');
    await expect(page.getByTestId('spot-card')).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(page.getByTestId('spot-card')).toHaveCount(0);
  });

  test('when the map copy cannot be loaded the box says so, shows no values, and Check tries again', async ({ page }) => {
    const d = bundle.datasets[0];
    const k = manifest.checks.find((c) => c.siteId === d.siteId)!;
    await page.route('**/pgda69-spot/manifest.json', (r) => r.abort());
    await openGlobe(page);
    await typePoint(page, d.site.latitudePlanetocentricDeg, d.site.longitudeEastDeg);
    await expect(page.getByTestId('spot-map-failed')).toContainText('nothing can be checked right now and nothing is substituted');
    await expect(page.getByTestId('spot-card')).toHaveCount(0);
    await expect(page.getByTestId('spot-mark')).not.toHaveAttribute('data-on', 'true');
    await page.unroute('**/pgda69-spot/manifest.json');
    await page.getByTestId('spot-check').click();
    await expect(page.getByTestId('spot-nasa-sun')).toHaveText(pct(k.sunRaw));
    await expect(page.getByTestId('spot-map-failed')).toHaveCount(0);
    // a tile that cannot be loaded: our own row still answers, the NASA row says why it is empty
    await page.route('**/pgda69-spot/tiles/**', (r) => r.abort());
    const far = manifest.checks.find((c) => !c.siteId && c.inCopy && Math.abs(c.row - k.row) > 600)!;
    await typePoint(page, far.lat, far.lonE);
    await expect(answer(page)).toHaveAttribute('data-coverage', 'failed');
    await expect(page.getByTestId('spot-nasa-none')).toContainText('could not be loaded');
    await expect(page.getByTestId('spot-nasa-sun')).toHaveCount(0);
  });

  test('editing a box while a check is still loading drops that check', async ({ page }) => {
    const d = bundle.datasets[0];
    let release: () => void = () => {};
    const held = new Promise<void>((r) => (release = r));
    await page.route('**/pgda69-spot/tiles/**', async (r) => {
      await held;
      await r.continue();
    });
    await openGlobe(page);
    await typePoint(page, d.site.latitudePlanetocentricDeg, d.site.longitudeEastDeg);
    await expect(page.getByTestId('spot-box')).toHaveAttribute('data-busy', 'true');
    await expect(page.getByTestId('spot-loading')).toBeVisible();
    await page.getByTestId('spot-lat').fill('-89');
    await expect(page.getByTestId('spot-box')).not.toHaveAttribute('data-busy', 'true');
    release();
    await page.waitForTimeout(800);
    await expect(page.getByTestId('spot-card')).toHaveCount(0);
    await expect(page.getByTestId('spot-mark')).not.toHaveAttribute('data-on', 'true');
    // checking the edited coordinates then answers for them
    await page.getByTestId('spot-lat').press('Enter');
    await expect(answer(page)).toHaveAttribute('data-lat', '-89');
  });

  test('editing a box after an answer is shown takes that answer and its marker away until Check is pressed again', async ({ page }) => {
    const [a, b] = bundle.datasets;
    const kb = manifest.checks.find((c) => c.siteId === b.siteId)!;
    await openGlobe(page);
    await typePoint(page, a.site.latitudePlanetocentricDeg, a.site.longitudeEastDeg);
    await expect(answer(page)).toHaveAttribute('data-coverage', 'cell');
    await expect(page.getByTestId('spot-mark')).toHaveAttribute('data-on', 'true');
    // one character typed into a box: the card for the old coordinates is gone at once
    await page.getByTestId('spot-lon').press('End');
    await page.keyboard.type('1');
    await expect(page.getByTestId('spot-card')).toHaveCount(0);
    await expect(page.getByTestId('spot-mark')).not.toHaveAttribute('data-on', 'true');
    await page.waitForTimeout(500);
    await expect(page.getByTestId('spot-card')).toHaveCount(0);
    // the same after a click on the Moon filled the boxes
    const p = await moonPoint(page);
    await page.mouse.click(p.x, p.y);
    await expect(answer(page)).toBeVisible();
    await page.getByTestId('spot-lat').fill(String(b.site.latitudePlanetocentricDeg));
    await expect(page.getByTestId('spot-card')).toHaveCount(0);
    await page.getByTestId('spot-lon').fill(String(b.site.longitudeEastDeg));
    await page.getByTestId('spot-lon').press('Enter');
    await expect(answer(page)).toHaveAttribute('data-sun-raw', String(kb.sunRaw));
    await expect(answer(page)).toHaveAttribute('data-lat', String(b.site.latitudePlanetocentricDeg));
  });

  test('pasting a pair that is not a valid coordinate while a check is loading drops that check too', async ({ page, context }) => {
    const d = bundle.datasets[0];
    let release: () => void = () => {};
    const held = new Promise<void>((r) => (release = r));
    await page.route('**/pgda69-spot/tiles/**', async (r) => {
      await held;
      await r.continue();
    });
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);
    await openGlobe(page);
    await typePoint(page, d.site.latitudePlanetocentricDeg, d.site.longitudeEastDeg);
    await expect(page.getByTestId('spot-box')).toHaveAttribute('data-busy', 'true');
    await page.evaluate(() => navigator.clipboard.writeText('-95, 20'));
    await page.getByTestId('spot-lat').focus();
    await page.keyboard.press('ControlOrMeta+v');
    await expect(page.getByTestId('spot-error')).toContainText('between −90 and 90');
    await expect(page.getByTestId('spot-box')).not.toHaveAttribute('data-busy', 'true');
    release();
    await page.waitForTimeout(800);
    await expect(page.getByTestId('spot-card')).toHaveCount(0);
    await expect(page.getByTestId('spot-error')).toBeVisible();
    await expect(page.getByTestId('spot-mark')).not.toHaveAttribute('data-on', 'true');
  });

  for (const [w, h] of [[1440, 900], [390, 844]] as const) {
    test.describe(`${w} × ${h}`, () => {
      test.use({ viewport: { width: w, height: h } });
      test('axe: the globe, a pin card, an answer card, and an error have no serious or critical issues; nothing overflows', async ({ page }) => {
        const d = bundle.datasets[1];
        await openGlobe(page);
        await expect(page.getByTestId('spot-box')).toBeInViewport({ ratio: 1 });
        // the box is centred along the bottom and never covers the Moon's south pole (the middle of the Moon's view)
        const [box, view] = [(await page.getByTestId('spot-box').boundingBox())!, (await page.locator('.s-globe-view').boundingBox())!];
        expect(Math.abs(box.x + box.width / 2 - w / 2)).toBeLessThanOrEqual(1);
        expect(view.y + view.height / 2).toBeLessThan(box.y - 40);
        if (w < 640) expect(view.y + view.height).toBeLessThanOrEqual(box.y + 1); // phones: the whole Moon view ends above the box
        const pole = await page.evaluate(() => {
          const g = (window as unknown as { __polarisGlobe: { camera: { position: { x: number; y: number; z: number; length(): number } } } }).__polarisGlobe;
          return g.camera.position.y / g.camera.position.length();
        });
        expect(pole).toBeLessThan(-0.999);
        await page.waitForTimeout(400);
        expect(sev((await new AxeBuilder({ page }).analyze()).violations)).toEqual([]);
        await pin(page, d.siteId).click();
        await expect(page.getByTestId('pin-card')).toBeInViewport({ ratio: 1 });
        await page.waitForTimeout(400);
        expect(sev((await new AxeBuilder({ page }).analyze()).violations)).toEqual([]);
        await page.getByTestId('pin-card-close').click();
        await typePoint(page, d.site.latitudePlanetocentricDeg, d.site.longitudeEastDeg);
        await expect(page.getByTestId('spot-nasa-sun-range')).toBeAttached();
        await expect(page.getByTestId('spot-card')).toBeInViewport({ ratio: 1 });
        // the marker stays in sight beside or above its card
        await expect(page.getByTestId('spot-mark')).toHaveAttribute('data-on', 'true');
        await expect
          .poll(async () => {
            const mark = (await page.getByTestId('spot-mark').boundingBox())!;
            const card = (await page.getByTestId('spot-card').boundingBox())!;
            return mark.x > 0 && (mark.x < card.x || mark.x > card.x + card.width || mark.y < card.y || mark.y > card.y + card.height);
          })
          .toBe(true);
        await page.waitForTimeout(400);
        expect(sev((await new AxeBuilder({ page }).analyze()).violations)).toEqual([]);
        expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(w);
        // the whole answer can be reached by scrolling the card, and its actions stay in reach
        await page.getByTestId('spot-slope').scrollIntoViewIfNeeded();
        await expect(page.getByTestId('spot-slope')).toBeInViewport();
        await expect(page.getByTestId('spot-zoom')).toBeInViewport({ ratio: 1 });
        await page.getByTestId('spot-close').click();
        await typePoint(page, 'x', 'y');
        await expect(page.getByTestId('spot-error')).toBeVisible();
        expect(sev((await new AxeBuilder({ page }).analyze()).violations)).toEqual([]);
      });
    });
  }

  test.describe('1440 × 900: hint and long cards', () => {
    test.use({ viewport: { width: 1440, height: 900 } });
    test('the hints hide while a card is open (the card would cover them) and come back when it closes', async ({ page }) => {
      const d = bundle.datasets[1];
      await openGlobe(page);
      await expect(page.getByTestId('globe-hint')).toBeVisible();
      // a typed check opens a card without a click on the Moon: the first-visit hint waits too, then comes back
      await typePoint(page, d.site.latitudePlanetocentricDeg, d.site.longitudeEastDeg);
      await expect(page.getByTestId('spot-card')).toBeVisible();
      await expect(page.getByTestId('spot-hint')).toHaveCount(0);
      await expect(page.getByTestId('globe-hint')).toHaveCount(0);
      await page.getByTestId('spot-close').click();
      await expect(page.getByTestId('spot-hint')).toBeVisible();
      await pin(page, d.siteId).click();
      await expect(page.getByTestId('pin-card')).toBeVisible();
      await expect(page.getByTestId('globe-hint')).toHaveCount(0);
      await page.getByTestId('pin-card-close').click();
      await expect(page.getByTestId('globe-hint')).toBeVisible();
      await typePoint(page, d.site.latitudePlanetocentricDeg, d.site.longitudeEastDeg);
      await expect(page.getByTestId('spot-nasa-sun-range')).toBeAttached();
      await expect(page.getByTestId('globe-hint')).toHaveCount(0);
      await page.getByTestId('spot-close').click();
      await expect(page.getByTestId('globe-hint')).toBeVisible();
    });
  });

  test('a card opened by a click on the Moon gives focus to the main region when closed from inside it (Esc or its button)', async ({ page }) => {
    await openGlobe(page);
    for (const how of ['Escape', 'button'] as const) {
      const p = await moonPoint(page);
      await page.mouse.click(p.x, p.y);
      await expect(page.getByTestId('spot-card')).toBeVisible();
      await page.getByTestId('spot-close').focus();
      if (how === 'Escape') await page.keyboard.press('Escape');
      else await page.keyboard.press('Enter');
      await expect(page.getByTestId('spot-card')).toHaveCount(0);
      await expect(page.locator('#simple-main')).toBeFocused();
    }
  });

  test.describe('390 × 844: a long card fades at the edge it scrolls past', () => {
    test.use({ viewport: { width: 390, height: 844 } });
    test('more below: a fade over the foot; scrolled to the end: the fade moves under the head', async ({ page }) => {
      const d = bundle.datasets[1];
      await openGlobe(page);
      await typePoint(page, d.site.latitudePlanetocentricDeg, d.site.longitudeEastDeg);
      await expect(page.getByTestId('spot-nasa-sun-range')).toBeAttached();
      const card = page.getByTestId('spot-card');
      const fade = (sel: string, pseudo: string) => page.locator(sel).evaluate((el, p) => getComputedStyle(el, p).opacity, pseudo);
      expect(await card.evaluate((el) => el.scrollHeight > el.clientHeight + 1)).toBe(true); // this card does scroll here
      await expect(card).toHaveAttribute('data-below', '');
      await expect(card).not.toHaveAttribute('data-above', '');
      await expect.poll(() => fade('[data-testid=spot-card] .s-spot-foot', '::before')).toBe('1');
      await expect.poll(() => fade('[data-testid=spot-card] .s-gcard-head', '::after')).toBe('0');
      await card.evaluate((el) => el.scrollTo({ top: el.scrollHeight }));
      await expect(card).toHaveAttribute('data-above', '');
      await expect(card).not.toHaveAttribute('data-below', '');
      await expect.poll(() => fade('[data-testid=spot-card] .s-spot-foot', '::before')).toBe('0');
      await expect.poll(() => fade('[data-testid=spot-card] .s-gcard-head', '::after')).toBe('1');
      // the close button stays in sight while the card is scrolled
      await expect(page.getByTestId('spot-close')).toBeInViewport({ ratio: 1 });
    });
  });
});

test.describe('S13 leaves Expert mode alone', () => {
  test('Expert has no Check a spot box, no pin cards, and never asks for the map copy', async ({ page }) => {
    const asked: string[] = [];
    page.on('request', (r) => r.url().includes('/pgda69-spot/') && asked.push(r.url()));
    await page.goto('/?mode=expert');
    await expect(page.getByTestId('simple-mode')).toHaveCount(0);
    await page.waitForTimeout(1500);
    await expect(page.getByTestId('spot-box')).toHaveCount(0);
    await expect(page.locator('.s-spot, .s-spot-mark, .s-gcard, .s-spot-box')).toHaveCount(0);
    expect(asked).toEqual([]);
  });
});
