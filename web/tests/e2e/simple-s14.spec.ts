import { test, expect, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

/**
 * S14 Part A (18 Nov 2026): the any-site results (POLARIS v2, Anish Meruva) in Simple mode. "Check a spot" answers any point
 * from the nearest computed point of data/anysite/precompute_summary.json, the slope row is filled from the same point, and
 * the pin cards add Earth in sight and the longest Sun gap. Every expected value is read here from the original file (not
 * the web copy), the nearest point is found a second way, and distances come from the map manifest's sphere.
 */
test.use({ storageState: { cookies: [], origins: [] } });

const __dirname = dirname(fileURLToPath(import.meta.url));
type Stat = { min: number; max: number; n: number };
type Row = { id: string; name: string; group: string; status: string; lat: number; lon: number; slope_deg: number; sun_pct: number; earth_pct: number; sun_earth_pct: number; longest_sun_gap_h: number; uncertainty?: Record<string, Record<string, Stat>> };
const file = JSON.parse(readFileSync(resolve(__dirname, '../../../data/anysite/precompute_summary.json'), 'utf8')) as { label: string; window: string; sites: Row[] };
const done = file.sites.filter((s) => s.status === 'done');
const manifest = JSON.parse(readFileSync(resolve(__dirname, '../../public/pgda69-spot/manifest.json'), 'utf8')) as { grid: { radiusM: number } };
const bundle = JSON.parse(readFileSync(resolve(__dirname, '../../../data/viewer/polaris-x5d-roi-2026-11-14-v2.json'), 'utf8')) as {
  datasets: { siteId: string; site: { name: string; latitudePlanetocentricDeg: number; longitudeEastDeg: number } }[];
};
const R = manifest.grid.radiusM;
const rad = Math.PI / 180;
const vec = (la: number, lo: number) => [Math.cos(la * rad) * Math.cos(lo * rad), Math.cos(la * rad) * Math.sin(lo * rad), Math.sin(la * rad)];
/** angle between two points from their unit vectors (a different formula from the page's haversine) */
const arcM = (a: [number, number], b: [number, number]) => {
  const [p, q] = [vec(...a), vec(...b)];
  const cross = Math.hypot(p[1] * q[2] - p[2] * q[1], p[2] * q[0] - p[0] * q[2], p[0] * q[1] - p[1] * q[0]);
  return R * Math.atan2(cross, p[0] * q[0] + p[1] * q[1] + p[2] * q[2]);
};
const nearest = (lat: number, lon: number) => done.reduce((a, b) => (arcM([lat, lon], [b.lat, b.lon]) < arcM([lat, lon], [a.lat, a.lon]) ? b : a));
const dist = (m: number) => (m < 999.5 ? `${Math.round(m)} m` : `${(m / 1000).toFixed(1)} km`);
const pct = (v: number) => `${v.toFixed(1)} %`;
const hrs = (v: number) => `${Number(v.toFixed(1))} h`;
const span = (s: Stat, unit: string) => (s.min === s.max ? `${unit === '%' ? s.min.toFixed(1) : Number(s.min.toFixed(1))} ${unit}` : `${unit === '%' ? s.min.toFixed(1) : Number(s.min.toFixed(1))}–${unit === '%' ? s.max.toFixed(1) : Number(s.max.toFixed(1))} ${unit}`);
const gridOf = (r: Row) => /_grid_(\d+)deg$/.exec(r.group)?.[1] ?? null;
const label = (r: Row) => {
  const g = gridOf(r);
  if (!g) return r.name;
  if (/pole/.test(r.name)) return `${g}° grid point at the ${r.name}`;
  return `${g}° grid point ${Number(Math.abs(r.lat).toFixed(1))}°${r.lat < 0 ? 'S' : 'N'} ${Number(Math.abs(r.lon).toFixed(1))}°${r.lon < 0 ? 'W' : 'E'}`;
};
const spacing = (r: Row) => Math.min(...done.filter((s) => s.group === r.group && s.id !== r.id).map((s) => arcM([r.lat, r.lon], [s.lat, s.lon])));
// the window line of the file, as the card words it
const win = /^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}) UTC \+ (\d+) d, hourly; mast ([\d.]+) m$/.exec(file.window)!;
const winDay = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' }).format(new Date(`${win[1]}T00:00:00Z`));
const windowText = `${win[3]} days from ${winDay} ${win[2]} UTC, hourly samples`;
/** the one mast height the file's results are for */
const OWN = Number(win[4]);
/**
 * Sid (18 Nov 2026): the any-site values are for a 1 m mast only. Beside numbers for a 1 m mast they say "1 m mast"; beside
 * numbers for another picked mast every one of them says "for a 1 m mast (not the … m mast picked above)".
 */
const mastFor = (picked: number) => (picked === OWN ? { same: true, label: `${OWN} m mast` } : { same: false, label: `for a ${OWN} m mast (not the ${picked} m mast picked above)` });
/** the mast in the top bar, as its figure reads ("1 m") */
async function topMast(page: Page) {
  return Number(/^([\d.]+)/.exec((await page.getByTestId('simple-mast-current').textContent()) ?? '')![1]);
}
const CREDIT = 'Any-site results: POLARIS v2 (Anish Meruva)';
const LOS = 'Line of sight to the disc centre, not power or communications.';
const CLONES = 'pgda78-clone';

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
const pin = (page: Page, id: string) => page.getByTestId(`globe-pin-${id}`).getByRole('button');

/** The card's nearest-point block and slope row show exactly the row `want` of the file, `d` metres away. */
async function expectNear(page: Page, lat: number, lon: number) {
  const want = nearest(lat, lon);
  const d = arcM([lat, lon], [want.lat, want.lon]);
  const near = page.getByTestId('spot-near');
  await expect(near).toHaveAttribute('data-point', want.id);
  expect(Math.abs(Number(await near.getAttribute('data-dist-m')) - d)).toBeLessThan(0.01);
  await expect(page.getByTestId('spot-near-name')).toHaveText(label(want));
  await expect(page.getByTestId('spot-near-distance')).toHaveText(`${dist(d)} from your spot`);
  await expect(page.getByTestId('spot-near-spacing')).toHaveText(gridOf(want) ? `grid spacing there ${dist(spacing(want))}` : 'a single named point, not on a grid');
  await expect(page.getByTestId('spot-near-sun')).toHaveText(pct(want.sun_pct));
  await expect(page.getByTestId('spot-near-earth')).toHaveText(pct(want.earth_pct));
  await expect(page.getByTestId('spot-near-both')).toHaveText(pct(want.sun_earth_pct));
  await expect(page.getByTestId('spot-near-gap')).toHaveText(hrs(want.longest_sun_gap_h));
  const c = want.uncertainty?.[CLONES];
  if (c) {
    await expect(page.getByTestId('spot-near-sun-clones')).toHaveText(`${span(c.sun_center_visible_pct_hourly_samples, '%')} across ${c.sun_center_visible_pct_hourly_samples.n} terrain variants`);
    await expect(page.getByTestId('spot-near-earth-clones')).toHaveText(`${span(c.earth_center_visible_pct_hourly_samples, '%')} across ${c.earth_center_visible_pct_hourly_samples.n} terrain variants`);
    await expect(page.getByTestId('spot-near-both-clones')).toHaveText(`${span(c.sun_and_earth_center_visible_pct_hourly_samples, '%')} across ${c.sun_and_earth_center_visible_pct_hourly_samples.n} terrain variants`);
    await expect(page.getByTestId('spot-near-gap-clones')).toHaveText(`${span(c.longest_sun_center_hidden_h, 'h')} across ${c.longest_sun_center_hidden_h.n} terrain variants`);
  } else {
    await expect(page.locator('[data-testid^=spot-near-][data-testid$=-clones]')).toHaveCount(0);
  }
  // said plainly: the nearest computed point, not the spot; the file's window and mast; what the numbers are not; the credit
  await expect(page.getByTestId('spot-ours').locator('.s-honesty')).toHaveText('SOURCE-BASED · UNVALIDATED');
  // slope: the same point, the same wording
  await expect(page.getByTestId('spot-slope-value')).toHaveText(`${want.slope_deg.toFixed(1)}°`);
  await expect(page.getByTestId('spot-slope-where')).toHaveText(`${label(want)}, ${dist(d)} from your spot`);
  await expect(page.getByTestId('spot-slope-note')).toContainText('the slope at the nearest point we computed, not at your spot itself');
  await expect(page.getByTestId('spot-slope-note')).toContainText(CREDIT);
  await expect(page.getByTestId('spot-slope').locator('.s-honesty')).toHaveText('SOURCE-BASED · UNVALIDATED');
  // the mast they are for: the matched site's row above them, or the top bar's mast
  const oursMast = page.getByTestId('spot-ours-mast');
  const picked = (await oursMast.count()) ? Number(/^([\d.]+) m mast/.exec((await oursMast.textContent()) ?? '')![1]) : await topMast(page);
  const ml = mastFor(picked);
  await expect(page.getByTestId('spot-near-note')).toHaveText(
    `This is the nearest point we computed, ${dist(d)} away, not your spot itself. ${ml.same ? `For ${windowText}, ${ml.label}` : `All four ${ml.label}, ${windowText}`}. Line of sight to the disc centre, not power or communications. ${CREDIT}.`,
  );
  const hints = page.getByTestId('spot-near').locator('[data-testid^=spot-near-][data-testid$=-mast]');
  if (ml.same) await expect(hints).toHaveCount(0);
  else {
    await expect(hints).toHaveCount(4);
    for (const k of ['sun', 'earth', 'both', 'gap']) await expect(page.getByTestId(`spot-near-${k}-mast`)).toHaveText(ml.label);
  }
  const spoken = page.getByTestId('spot-spoken');
  await expect(spoken).toContainText(`There, ${ml.same ? `for ${windowText}, ${ml.label}` : `${ml.label}, ${windowText}`}: Sun in sight`);
  await expect(spoken).toContainText(`Nearest computed point: ${label(want)}, ${dist(d)} from your spot. Not your spot itself.`);
  await expect(spoken).toContainText(`Sun in sight ${pct(want.sun_pct)}, Earth in sight ${pct(want.earth_pct)}, Sun and Earth together ${pct(want.sun_earth_pct)}, longest Sun gap ${hrs(want.longest_sun_gap_h)}.`);
  await expect(spoken).toContainText(`Slope at the nearest computed point: ${want.slope_deg.toFixed(1)}°.`);
  return { want, d };
}

test.describe('S14 any-site results in Simple mode', () => {
  test.skip(!hasGlobe, 'no Moon model in public/globe (git-ignored NASA asset)');

  test('the file carries the label the cards print', () => {
    expect(file.label).toBe('SOURCE-BASED UNVALIDATED');
    expect(done.length).toBeGreaterThan(1000);
  });

  test('the any-site file is not fetched until Check a spot or a pin card is used, and then once', async ({ page }) => {
    const asked: string[] = [];
    page.on('request', (r) => r.url().includes('/anysite/') && asked.push(r.url().split('/anysite/')[1]));
    await openGlobe(page);
    await page.waitForTimeout(1500);
    expect(asked).toEqual([]);
    await pin(page, bundle.datasets[0].siteId).click();
    await expect(page.getByTestId('pin-card')).toBeVisible();
    await expect.poll(() => asked).toEqual(['points.json']);
    await page.getByTestId('pin-card-close').click();
    await typePoint(page, -86.2, 41);
    await expect(page.getByTestId('spot-near')).toBeVisible();
    await page.getByTestId('spot-close').click();
    await pin(page, bundle.datasets[1].siteId).click();
    await expect(page.getByTestId('pin-card-any')).toBeVisible();
    expect(asked).toEqual(['points.json']);
  });

  for (const d of bundle.datasets) {
    test(`a spot at ${d.site.name}: the site's detailed answer stays, and the nearest computed point is shown under it`, async ({ page }) => {
      const [lat, lon] = [d.site.latitudePlanetocentricDeg, d.site.longitudeEastDeg];
      await openGlobe(page);
      await typePoint(page, lat, lon);
      // the S13 detailed block, unchanged
      await expect(page.getByTestId('spot-ours')).toHaveAttribute('data-match', d.siteId);
      await expect(page.getByTestId('spot-ours-site')).toHaveText(d.site.name);
      await expect(page.getByTestId('spot-fly')).toBeVisible();
      const { want, d: m } = await expectNear(page, lat, lon);
      const own = done.find((s) => s.id === d.siteId);
      if (own) {
        // the file has this very site: the nearest computed point is the site itself
        expect(want.id).toBe(d.siteId);
        expect(m).toBe(0);
      } else {
        // the file has no row for this site: the nearest computed point is another one, some way off, and the card says so
        expect(want.id).not.toBe(d.siteId);
        expect(m).toBeGreaterThan(0);
        await expect(page.getByTestId('spot-near-distance')).not.toHaveText('0 m from your spot');
      }
    });

    test(`a spot near ${d.site.name} but not at it: no detailed answer, the nearest computed point instead`, async ({ page }) => {
      const [lat, lon] = [d.site.latitudePlanetocentricDeg + 0.01, d.site.longitudeEastDeg];
      await openGlobe(page);
      await typePoint(page, lat, lon);
      await expect(page.getByTestId('spot-ours')).toHaveAttribute('data-match', 'none');
      await expect(page.getByTestId('spot-ours-sun')).toHaveCount(0);
      await expect(page.getByTestId('spot-ours-none')).toContainText(`Not one of the ${bundle.datasets.length} sites with a detailed answer. The nearest site we computed is `);
      await expect(page.getByTestId('spot-fly')).toHaveCount(0);
      const { d: m } = await expectNear(page, lat, lon);
      expect(m).toBeGreaterThan(0);
    });
  }

  test('a spot on the 1° grid far from our sites is answered from its nearest grid point, with the spacing there', async ({ page }) => {
    await openGlobe(page);
    // between rings and between points of the south 1° grid, on the far side of the pole from the sites
    const ring = done.filter((s) => s.group === 'south_grid_1deg' && !/pole/.test(s.name));
    const a = ring.find((s) => s.lon > 30 && s.lon < 60 && s.lat < -83 && s.lat > -86)!;
    const [lat, lon] = [Number((a.lat + 0.21).toFixed(4)), Number((a.lon + 0.9).toFixed(4))];
    await typePoint(page, lat, lon);
    const { want, d } = await expectNear(page, lat, lon);
    expect(want.group).toBe('south_grid_1deg');
    expect(gridOf(want)).not.toBeNull();
    expect(d).toBeGreaterThan(1000);
    await expect(page.getByTestId('spot-near-name')).toContainText(`${gridOf(want)}° grid point`);
    await expect(page.getByTestId('spot-near-spacing')).toContainText('grid spacing there');
    await expect(page.getByTestId('spot-ours')).toHaveAttribute('data-match', 'none');
    // the pole itself is a grid point of its own
    const pole = done.find((s) => s.group === 'south_grid_1deg' && /pole/.test(s.name))!;
    await typePoint(page, -89.99, 10);
    await expect(page.getByTestId('spot-near')).toHaveAttribute('data-point', pole.id);
    await expect(page.getByTestId('spot-near-name')).toHaveText(`${gridOf(pole)}° grid point at the ${pole.name}`);
  });

  test('a spot at low latitude is answered from the 10° grid; NASA’s row says it is outside the map', async ({ page }) => {
    await openGlobe(page);
    for (const [lat, lon] of [
      [12.3, 47.1],
      [-31.6, -118.2],
    ]) {
      await typePoint(page, lat, lon);
      const { want, d } = await expectNear(page, lat, lon);
      expect(want.group).toBe('global_grid_10deg');
      expect(d).toBeGreaterThan(10_000);
      await expect(page.getByTestId('spot-answer')).toHaveAttribute('data-coverage', 'outside-map');
      await expect(page.getByTestId('spot-nasa-none')).toContainText('outside it, so there is no NASA value to show');
    }
    // a past landing site is a named point, not a grid point
    const named = done.find((s) => s.group === 'landing_sites')!;
    await typePoint(page, named.lat, named.lon);
    const { want } = await expectNear(page, named.lat, named.lon);
    expect(want.id).toBe(named.id);
    await expect(page.getByTestId('spot-near-name')).toHaveText(named.name);
    await expect(page.getByTestId('spot-near-spacing')).toHaveText('a single named point, not on a grid');
  });

  test('with a mast other than 1 m picked, the spot card labels every any-site value "for a 1 m mast"', async ({ page }) => {
    await openGlobe(page);
    await page.getByTestId('simple-mast-up').click();
    const up = await topMast(page);
    expect(up).not.toBe(OWN);
    // at a computed site sampled at that mast (its own result row above is for it) and far from any (the top bar's mast)
    const masts = JSON.parse(readFileSync(resolve(__dirname, '../../public/certainty/sidecar.json'), 'utf8')).sites as Record<string, { sampled_masts_m: number[] }>;
    const d = bundle.datasets.find((x) => done.some((s) => s.id === x.siteId) && masts[x.siteId]?.sampled_masts_m.includes(up))!;
    await typePoint(page, d.site.latitudePlanetocentricDeg, d.site.longitudeEastDeg);
    await expect(page.getByTestId('spot-ours-mast')).toBeVisible();
    await expectNear(page, d.site.latitudePlanetocentricDeg, d.site.longitudeEastDeg);
    await expect(page.getByTestId('spot-near-sun-mast')).toBeVisible();
    await page.getByTestId('spot-close').click();
    await typePoint(page, -86.2, 41);
    await expectNear(page, -86.2, 41);
    await expect(page.getByTestId('spot-near-sun-mast')).toBeVisible();
  });

  test('a click on the Moon is answered from the nearest computed point too', async ({ page }) => {
    await openGlobe(page);
    const view = (await page.locator('.s-globe-view').boundingBox())!;
    await page.mouse.click(view.x + view.width / 2 + 90, view.y + view.height / 2 - 110);
    const a = page.getByTestId('spot-answer');
    await expect(a).toBeVisible();
    await expectNear(page, Number(await a.getAttribute('data-lat')), Number(await a.getAttribute('data-lon')));
  });

  for (const d of bundle.datasets) {
    test(`pin card: ${d.site.name} adds Earth in sight and the longest Sun gap from its row, or says there is none`, async ({ page }) => {
      const row = done.find((s) => s.id === d.siteId && s.lat === d.site.latitudePlanetocentricDeg && s.lon === d.site.longitudeEastDeg);
      await openGlobe(page);
      await pin(page, d.siteId).click();
      const card = page.getByTestId('pin-card');
      await expect(card).toBeVisible();
      if (row) {
        await expect(page.getByTestId('pin-card-any')).toHaveAttribute('data-point', row.id);
        await expect(page.getByTestId('pin-card-earth')).toHaveText(pct(row.earth_pct));
        await expect(page.getByTestId('pin-card-gap')).toHaveText(hrs(row.longest_sun_gap_h));
        const c = row.uncertainty?.[CLONES];
        if (c) {
          await expect(page.getByTestId('pin-card-earth-clones')).toHaveText(`${span(c.earth_center_visible_pct_hourly_samples, '%')} across ${c.earth_center_visible_pct_hourly_samples.n} terrain variants`);
          await expect(page.getByTestId('pin-card-gap-clones')).toHaveText(`${span(c.longest_sun_center_hidden_h, 'h')} across ${c.longest_sun_center_hidden_h.n} terrain variants`);
        }
        // at the default 1 m mast they are labelled with it, and nothing more
        expect(await topMast(page)).toBe(OWN);
        await expect(page.getByTestId('pin-card-any-note')).toHaveText(`Both for ${windowText}, ${OWN} m mast. ${LOS} ${CREDIT}.`);
        await expect(page.getByTestId('pin-card-any-note')).toHaveAttribute('data-same-mast', 'true');
        await expect(page.getByTestId('pin-card-earth-mast')).toHaveCount(0);
        await expect(page.getByTestId('pin-card-gap-mast')).toHaveCount(0);
        // they do not follow the mast control (the file is for one mast); at another mast each says it is for 1 m
        await page.getByTestId('simple-mast-up').click();
        const up = await topMast(page);
        expect(up).not.toBe(OWN);
        await expect(card).toContainText(`at a ${up} m mast`);
        const ml = mastFor(up);
        await expect(page.getByTestId('pin-card-earth')).toHaveText(pct(row.earth_pct));
        await expect(page.getByTestId('pin-card-gap')).toHaveText(hrs(row.longest_sun_gap_h));
        await expect(page.getByTestId('pin-card-earth-mast')).toHaveText(ml.label);
        await expect(page.getByTestId('pin-card-gap-mast')).toHaveText(ml.label);
        await expect(page.getByTestId('pin-card-any-note')).toHaveText(`Both ${ml.label}, ${windowText}. ${LOS} ${CREDIT}.`);
        // and back at 1 m, the plain label again
        await page.getByTestId('simple-mast-down').click();
        await expect(page.getByTestId('pin-card-any-note')).toHaveText(`Both for ${windowText}, ${OWN} m mast. ${LOS} ${CREDIT}.`);
        await expect(page.getByTestId('pin-card-earth-mast')).toHaveCount(0);
      } else {
        await expect(page.getByTestId('pin-card-any-none')).toHaveText('Earth in sight and longest Sun gap: the any-site file has no row for this site.');
        await expect(page.getByTestId('pin-card-earth')).toHaveCount(0);
      }
      await expect(card.locator('.s-honesty')).toHaveText('SOURCE-BASED · UNVALIDATED');
      await expect(card).toBeInViewport({ ratio: 1 });
    });
  }

  test('when the any-site file cannot be loaded the card says so, shows none of its numbers, and slope reads "Not yet available"', async ({ page }) => {
    await page.route('**/anysite/points.json', (r) => r.fulfill({ status: 503, body: 'no' }));
    const d = bundle.datasets[0];
    await openGlobe(page);
    await typePoint(page, d.site.latitudePlanetocentricDeg + 0.01, d.site.longitudeEastDeg);
    await expect(page.getByTestId('spot-nasa-sun')).toBeVisible();
    await expect(page.getByTestId('spot-near')).toHaveCount(0);
    await expect(page.getByTestId('spot-near-failed')).toContainText('The any-site results could not be loaded (anysite/points.json: HTTP 503), so no nearest computed point is shown. Nothing is substituted.');
    await expect(page.getByTestId('spot-ours-none')).toContainText('None for this spot.');
    await expect(page.getByTestId('spot-slope-none')).toContainText('Not yet available');
    await expect(page.getByTestId('spot-slope-value')).toHaveCount(0);
    await expect(page.getByTestId('spot-spoken')).toContainText('Slope: not yet available.');
    // a pin card adds none of its numbers, and says why
    await page.getByTestId('spot-close').click();
    await pin(page, d.siteId).click();
    await expect(page.getByTestId('pin-card')).toBeVisible();
    await expect(page.getByTestId('pin-card-any-failed')).toHaveText('Earth in sight and longest Sun gap could not be loaded (anysite/points.json: HTTP 503), so they are not shown. Nothing is substituted; opening a card again tries again.');
    await expect(page.locator('[data-testid=pin-card-any], [data-testid=pin-card-any-none]')).toHaveCount(0);
    // the next pin card tries again, and says "loading" (not the old failure) while it does
    await page.unroute('**/anysite/points.json');
    let release: () => void = () => {};
    const held = new Promise<void>((r) => (release = r));
    await page.route('**/anysite/points.json', async (r) => {
      await held;
      await r.continue();
    });
    await page.getByTestId('pin-card-close').click();
    await pin(page, d.siteId).click();
    await expect(page.getByTestId('pin-card-any-wait')).toBeVisible();
    await expect(page.getByTestId('pin-card-any-failed')).toHaveCount(0);
    release();
    await expect(page.locator('[data-testid=pin-card-any], [data-testid=pin-card-any-none]')).toHaveCount(1);
    await expect(page.getByTestId('pin-card-any-failed')).toHaveCount(0);
    // and so does the next check
    await page.getByTestId('pin-card-close').click();
    await typePoint(page, d.site.latitudePlanetocentricDeg + 0.02, d.site.longitudeEastDeg);
    await expect(page.getByTestId('spot-near')).toBeVisible();
  });

  test('a pin card opened while the any-site file is on its way says it is loading, then shows the rows', async ({ page }) => {
    let release: () => void = () => {};
    const held = new Promise<void>((r) => (release = r));
    await page.route('**/anysite/points.json', async (r) => {
      await held;
      await r.continue();
    });
    const d = bundle.datasets.find((x) => done.some((s) => s.id === x.siteId && s.lat === x.site.latitudePlanetocentricDeg))!;
    await openGlobe(page);
    await pin(page, d.siteId).click();
    await expect(page.getByTestId('pin-card-any-wait')).toHaveText('Loading Earth in sight and longest Sun gap…');
    await expect(page.getByTestId('pin-card-earth')).toHaveCount(0);
    release();
    await expect(page.getByTestId('pin-card-earth')).toBeVisible();
    await expect(page.getByTestId('pin-card-any-wait')).toHaveCount(0);
  });

  test('a slow any-site file never holds the answer back: NASA’s rows show first, the nearest point fills in when it arrives', async ({ page }) => {
    let release: () => void = () => {};
    const held = new Promise<void>((r) => (release = r));
    await page.route('**/anysite/points.json', async (r) => {
      await held;
      await r.continue();
    });
    const d = bundle.datasets[0];
    const [lat, lon] = [d.site.latitudePlanetocentricDeg + 0.01, d.site.longitudeEastDeg];
    await openGlobe(page);
    await typePoint(page, lat, lon);
    // the file has not arrived, and still the rest of the answer is on screen
    await expect(page.getByTestId('spot-nasa-sun')).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId('spot-near')).toHaveCount(0);
    await expect(page.getByTestId('spot-near-wait')).toHaveText('Still loading the nearest computed point…');
    await expect(page.getByTestId('spot-slope-none')).toHaveText('Still loading the nearest computed point…');
    await expect(page.getByTestId('spot-card')).not.toHaveAttribute('data-busy', /.*/);
    release();
    await expectNear(page, lat, lon);
    await expect(page.getByTestId('spot-near-wait')).toHaveCount(0);
  });

  test('a file without the SOURCE-BASED UNVALIDATED label is not shown', async ({ page }) => {
    await page.route('**/anysite/points.json', async (r) => {
      const res = await r.fetch();
      await r.fulfill({ response: res, json: { ...(await res.json()), label: 'VALIDATED' } });
    });
    await openGlobe(page);
    await typePoint(page, -86.2, 41);
    await expect(page.getByTestId('spot-near-failed')).toContainText('not "SOURCE-BASED UNVALIDATED"');
    await expect(page.getByTestId('spot-near')).toHaveCount(0);
  });

  test('About this view credits the any-site results', async ({ page }) => {
    await openGlobe(page);
    await page.getByTestId('globe-about').locator('summary').click();
    await expect(page.getByTestId('globe-about')).toContainText(`${CREDIT}: the nearest-computed-point answers and slope in Check a spot, and Earth in sight and longest Sun gap on the pin cards. SOURCE-BASED · UNVALIDATED.`);
  });

  for (const [w, h] of [
    [1440, 900],
    [390, 844],
  ] as const) {
    test.describe(`${w} × ${h}`, () => {
      test.use({ viewport: { width: w, height: h } });
      test('axe: the longer answer card and pin card have no serious or critical issues; nothing overflows; every row can be reached', async ({ page }) => {
        const d = bundle.datasets.find((x) => done.some((s) => s.id === x.siteId))!;
        await openGlobe(page);
        await typePoint(page, d.site.latitudePlanetocentricDeg, d.site.longitudeEastDeg);
        await expect(page.getByTestId('spot-near')).toBeAttached();
        await expect(page.getByTestId('spot-card')).toBeInViewport({ ratio: 1 });
        await page.waitForTimeout(400);
        expect(sev((await new AxeBuilder({ page }).analyze()).violations)).toEqual([]);
        expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(w);
        for (const id of ['spot-near-gap', 'spot-near-note', 'spot-slope-value', 'spot-slope-note']) {
          await page.getByTestId(id).scrollIntoViewIfNeeded();
          await expect(page.getByTestId(id)).toBeInViewport();
        }
        await expect(page.getByTestId('spot-zoom')).toBeInViewport({ ratio: 1 });
        // no text in the card is cut off sideways
        expect(await page.getByTestId('spot-card').evaluate((el) => el.scrollWidth <= el.clientWidth)).toBe(true);
        await page.getByTestId('spot-close').click();
        await pin(page, d.siteId).click();
        await expect(page.getByTestId('pin-card-any')).toBeVisible();
        await expect(page.getByTestId('pin-card')).toBeInViewport({ ratio: 1 });
        await page.waitForTimeout(400);
        expect(sev((await new AxeBuilder({ page }).analyze()).violations)).toEqual([]);
        expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(w);
        expect(await page.getByTestId('pin-card').evaluate((el) => el.scrollWidth <= el.clientWidth)).toBe(true);
        // the way down to the terrain stays in reach without scrolling the card, and every row can be scrolled to
        await expect(page.getByTestId('pin-card-fly')).toBeInViewport({ ratio: 1 });
        for (const id of ['pin-card-gap', 'pin-card-any-note']) {
          await page.getByTestId(id).scrollIntoViewIfNeeded();
          await expect(page.getByTestId(id)).toBeInViewport();
        }
        await expect(page.getByTestId('pin-card-fly')).toBeInViewport({ ratio: 1 });
        // with another mast picked, the longer labelled rows: still clean, still in reach
        await page.getByTestId('simple-mast-up').click();
        await expect(page.getByTestId('pin-card-gap-mast')).toBeAttached();
        await page.waitForTimeout(400);
        expect(sev((await new AxeBuilder({ page }).analyze()).violations)).toEqual([]);
        expect(await page.getByTestId('pin-card').evaluate((el) => el.scrollWidth <= el.clientWidth)).toBe(true);
        for (const id of ['pin-card-earth-mast', 'pin-card-gap-mast', 'pin-card-any-note']) {
          await page.getByTestId(id).scrollIntoViewIfNeeded();
          await expect(page.getByTestId(id)).toBeInViewport();
        }
        await expect(page.getByTestId('pin-card-fly')).toBeInViewport({ ratio: 1 });
      });
    });
  }

  test('Expert never asks for the any-site file and shows none of it', async ({ page }) => {
    const asked: string[] = [];
    page.on('request', (r) => r.url().includes('/anysite/') && asked.push(r.url()));
    await page.goto('/?mode=expert');
    await expect(page.getByTestId('simple-mode')).toHaveCount(0);
    await page.waitForTimeout(1500);
    await expect(page.locator('[data-testid^=spot-near], [data-testid^=pin-card]')).toHaveCount(0);
    await expect(page.locator('body')).not.toContainText('POLARIS v2 (Anish Meruva)');
    expect(asked).toEqual([]);
  });
});
