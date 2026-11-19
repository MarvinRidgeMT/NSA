// S14 Part A (any-site results in Simple mode): screenshots in Google Chrome on this Mac (GPU via ANGLE/Metal) into ../tmp/s14
// (git-ignored). Display check only; the values are tested in tests/unit/any-site.test.ts and tests/e2e/simple-s14.spec.ts.
//   cd web && npm run build && npx vite preview --port 5174
//   node scripts/s14_shots.mjs [base URL, default http://127.0.0.1:5174/]
import { existsSync, mkdirSync, readFileSync } from 'node:fs';
import { chromium } from '@playwright/test';

const base = process.argv[2] ?? 'http://127.0.0.1:5174/';
const out = '../tmp/s14';
mkdirSync(out, { recursive: true });
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
// spots come from the files: 0.01° of latitude off each bundle site, and offsets from points of the any-site grids
const bundle = JSON.parse(readFileSync('../data/viewer/polaris-x5d-roi-2026-11-14-v2.json', 'utf8'));
const any = JSON.parse(readFileSync('../data/anysite/precompute_summary.json', 'utf8')).sites.filter((s) => s.status === 'done');
const sites = bundle.datasets.map((d) => ({ id: d.siteId, lat: d.site.latitudePlanetocentricDeg, lon: d.site.longitudeEastDeg }));
const grid1 = any.find((s) => s.group === 'south_grid_1deg' && s.lon > 30 && s.lon < 60 && s.lat < -83 && s.lat > -86);
const grid10 = any.find((s) => s.group === 'global_grid_10deg' && s.lat === 10 && s.lon === 20);
const browser = await chromium.launch({ headless: false, executablePath: existsSync(CHROME) ? CHROME : undefined, args: ['--use-angle=metal', '--ignore-gpu-blocklist'] });
const cases = [
  ['1440x900', { viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 }],
  ['390x844', { viewport: { width: 390, height: 844 }, deviceScaleFactor: 3, hasTouch: true, isMobile: true }],
];
for (const [name, opts] of cases) {
  const ctx = await browser.newContext(opts);
  const page = await ctx.newPage();
  page.on('pageerror', (e) => console.log(name, 'PAGE ERROR', e.message));
  page.on('console', (m) => m.type() === 'error' && !/favicon/.test(m.location().url) && console.log(name, 'console error', m.text().slice(0, 200)));
  const shot = (what) => page.screenshot({ path: `${out}/${what}-${name}.png` }).then(() => console.log(`${out}/${what}-${name}.png`));
  const press = (loc) => (opts.hasTouch ? loc.tap() : loc.click());
  const type = async (lat, lon) => {
    // phones: an open card is a sheet in the box's place, so it is closed first
    if (!(await page.getByTestId('spot-lat').isVisible())) await press(page.locator('[data-testid=spot-close], [data-testid=pin-card-close]').first());
    await page.getByTestId('spot-lat').fill(String(lat));
    await page.getByTestId('spot-lon').fill(String(lon));
    await page.getByTestId('spot-lon').press('Enter');
    await page.waitForSelector('[data-testid=spot-near]');
    await page.waitForTimeout(600);
    console.log(name, lat, lon, await page.getByTestId('spot-near').evaluate((el) => `${el.dataset.point} ${Number(el.dataset.distM).toFixed(1)} m`));
  };
  const scroll = (testid, block = 'start') => page.getByTestId(testid).evaluate((el, b) => el.scrollIntoView({ block: b }), block);
  const top = () => page.getByTestId('spot-card').evaluate((el) => (el.scrollTop = 0));
  await page.goto(`${base}?mode=simple`);
  await page.waitForSelector('[data-testid=simple-globe][data-shown=true][data-first-frame-ms]', { timeout: 60_000 });
  await page.waitForSelector('[data-testid=simple-mode]:not([data-intro])', { timeout: 60_000 });
  await page.waitForSelector('[data-testid=simple-globe]:not([data-upgrade])', { timeout: 90_000 }).catch(() => console.log(name, 'upgrade still pending'));
  await page.waitForTimeout(1500);
  // a pin card for each site: Earth in sight and the longest Sun gap from the any-site file (or the line saying there is no row)
  for (const s of sites) {
    await press(page.locator(`[data-testid=globe-pin-${s.id}] button`));
    await page.waitForSelector('[data-testid=pin-card-any], [data-testid=pin-card-any-none]');
    await page.waitForTimeout(450);
    await shot(`05-pin-card-${s.id}`);
    await press(page.getByTestId('pin-card-close'));
  }
  // a spot near each site (about 300 m off): the nearest computed point, its distance, the values
  for (const s of sites) {
    await type((s.lat + 0.01).toFixed(4), s.lon.toFixed(4));
    await top();
    await shot(`01-spot-near-${s.id}`);
  }
  // at a site: the detailed answer stays, the nearest computed point (the site itself, with its clone ranges) under it
  await type(sites[1].lat.toFixed(4), sites[1].lon.toFixed(4));
  await top();
  await shot(`01b-spot-at-${sites[1].id}`);
  await scroll('spot-near');
  await page.waitForTimeout(150);
  await shot(`01c-spot-at-${sites[1].id}-nearest-point`);
  // on the 1° grid, far from our sites
  await type((grid1.lat + 0.21).toFixed(4), (grid1.lon + 0.9).toFixed(4));
  await top();
  await shot('02-spot-on-1deg-grid-far-from-sites');
  // the slope row of the same card
  await scroll('spot-slope');
  await page.waitForTimeout(150);
  await shot('04-slope-row');
  // low latitude: the 10° grid (NASA's map does not reach here)
  await type((grid10.lat + 2.3).toFixed(4), (grid10.lon + 1.1).toFixed(4));
  await top();
  await shot('03-spot-at-low-latitude-10deg-grid');
  await scroll('spot-nasa');
  await page.waitForTimeout(150);
  await shot('03b-spot-at-low-latitude-lower-rows');
  // another mast picked (Sid, 18 Nov 2026): the any-site rows say they are for a 1 m mast, not the picked one
  if (await page.getByTestId('spot-close').count()) await press(page.getByTestId('spot-close'));
  await press(page.getByTestId('simple-mast-up'));
  await page.waitForTimeout(300);
  const mastNow = (await page.getByTestId('simple-mast-current').textContent()).replace(/\s+/g, '');
  for (const s of sites.slice(0, 2)) {
    await press(page.locator(`[data-testid=globe-pin-${s.id}] button`));
    await page.waitForSelector('[data-testid=pin-card-any], [data-testid=pin-card-any-none]');
    await page.waitForTimeout(450);
    await shot(`07-pin-card-${s.id}-mast-${mastNow}`);
    await press(page.getByTestId('pin-card-close'));
  }
  await type(sites[1].lat.toFixed(4), sites[1].lon.toFixed(4));
  await scroll('spot-near');
  await page.waitForTimeout(150);
  await shot(`08-spot-at-${sites[1].id}-nearest-point-mast-${mastNow}`);
  await press(page.getByTestId('spot-close'));
  await press(page.getByTestId('simple-mast-down'));
  await page.waitForTimeout(300);
  // About this view: the credit
  if (await page.getByTestId('spot-close').count()) await press(page.getByTestId('spot-close'));
  await press(page.getByTestId('globe-about').locator('summary'));
  await page.waitForTimeout(300);
  await page.getByTestId('globe-about').evaluate((el) => el.querySelectorAll('*').forEach((c) => c.scrollHeight > c.clientHeight + 4 && (c.scrollTop = c.scrollHeight)));
  await page.waitForTimeout(200);
  await shot('06-about-this-view-credit');
  await ctx.close();
}
await browser.close();
