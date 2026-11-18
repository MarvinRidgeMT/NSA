// S13 "Check a spot": screenshots in Google Chrome on this Mac (GPU via ANGLE/Metal) into ../tmp/s13 (git-ignored).
// Display check only; the values are tested in tests/unit/spot-check.test.ts and tests/e2e/simple-s13.spec.ts.
//   cd web && npm run dev
//   node scripts/s13_shots.mjs [base URL, default http://127.0.0.1:5174/]
import { existsSync, mkdirSync, readFileSync } from 'node:fs';
import { chromium } from '@playwright/test';

const base = process.argv[2] ?? 'http://127.0.0.1:5174/';
const out = '../tmp/s13';
mkdirSync(out, { recursive: true });
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
// site coordinates come from the bundle, rounded to four decimals so each typed point lies a few metres from its site
const bundle = JSON.parse(readFileSync('../data/viewer/polaris-x5d-roi-2026-11-14-v2.json', 'utf8'));
const manifest = JSON.parse(readFileSync('public/pgda69-spot/manifest.json', 'utf8'));
const sites = bundle.datasets.map((d) => ({ id: d.siteId, lat: d.site.latitudePlanetocentricDeg.toFixed(4), lon: d.site.longitudeEastDeg.toFixed(4) }));
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
  const type = async (lat, lon) => {
    // phones: an open card is a sheet in the box's place, so it is closed first
    if (!(await page.getByTestId('spot-lat').isVisible())) await page.locator('[data-testid=spot-close], [data-testid=pin-card-close]').first().click();
    await page.getByTestId('spot-lat').fill(String(lat));
    await page.getByTestId('spot-lon').fill(String(lon));
    await page.getByTestId('spot-lon').press('Enter');
    await page.waitForSelector('[data-testid=spot-answer]');
    await page.waitForTimeout(500);
  };
  const facts = () => page.getByTestId('spot-answer').evaluate((el) => ({ ...el.dataset, text: el.innerText.replace(/\s+/g, ' ').slice(0, 260) }));
  await page.goto(`${base}?mode=simple`);
  await page.waitForSelector('[data-testid=simple-globe][data-shown=true][data-first-frame-ms]', { timeout: 60_000 });
  await page.waitForSelector('[data-testid=simple-mode]:not([data-intro])', { timeout: 60_000 });
  await page.waitForSelector('[data-testid=simple-globe]:not([data-upgrade])', { timeout: 90_000 }).catch(() => console.log(name, 'upgrade still pending'));
  await page.waitForTimeout(1500);
  const scroll = (testid, block = 'start') => page.getByTestId(testid).evaluate((el, b) => el.scrollIntoView({ block: b }), block);
  const top = () => page.getByTestId('spot-card').evaluate((el) => (el.scrollTop = 0));
  const press = (loc) => (opts.hasTouch ? loc.tap() : loc.click());
  // the globe with no card open: the Moon fills the window, the box along the bottom, the first-visit hint above it
  await shot('00-globe-no-card');
  // a pin card for each site
  for (const s of sites) {
    await press(page.locator(`[data-testid=globe-pin-${s.id}] button`));
    await page.waitForSelector('[data-testid=pin-card]');
    await page.waitForTimeout(450);
    await shot(`01-pin-card-${s.id}`);
    await press(page.getByTestId('pin-card-close'));
  }
  // the globe again, hint gone, with About this view open (the shimmer legend and the honesty label live there now)
  await press(page.getByTestId('globe-about').locator('summary'));
  await page.waitForTimeout(300);
  await shot('02-about-this-view');
  await press(page.getByTestId('globe-about').locator('summary'));
  // typed points near each site: marker, card, both ways on
  for (const s of sites) {
    await type(s.lat, s.lon);
    console.log(name, s.id, JSON.stringify(await facts()));
    await top();
    await shot(`03-typed-near-${s.id}`);
    await scroll('spot-nasa');
    await page.waitForTimeout(150);
    await shot(`04-typed-near-${s.id}-nasa-rows`);
  }
  // the widest range: the site whose surrounding cells differ most (no warning trigger: the value and the range are always shown)
  const worst = manifest.checks.filter((k) => k.siteId).sort((a, b) => b.sun3x3[1] - b.sun3x3[0] - (a.sun3x3[1] - a.sun3x3[0]))[0];
  const w = sites.find((s) => s.id === worst.siteId);
  await type(w.lat, w.lon);
  await scroll('spot-nasa');
  await page.waitForTimeout(150);
  await shot('05-widest-range-around-a-cell');
  // out of range: north of NASA's map, then on the map but outside the part shipped
  await type(-80, 20);
  await top();
  await shot('06-out-of-range-north-of-85S');
  const off = manifest.checks.find((k) => !k.inCopy);
  await type(off.lat.toFixed(4), off.lonE.toFixed(4));
  await top();
  await shot('07-outside-web-copy');
  if (await page.getByTestId('spot-close').count()) await press(page.getByTestId('spot-close'));
  await page.getByTestId('spot-lat').fill('abc');
  await page.getByTestId('spot-lon').fill('20');
  await page.getByTestId('spot-lon').press('Enter');
  await page.waitForTimeout(250);
  await shot('08-not-a-number');
  // a clicked point: a dropped marker with its card, at the whole-Moon view
  const vb = await page.locator('.s-globe-view').boundingBox();
  const cx = vb.x + vb.width / 2;
  const cy = vb.y + vb.height / 2;
  // close to the pole, where the map copy is: one pixel is several kilometres at this zoom
  if (opts.hasTouch) await page.touchscreen.tap(cx + 2, cy - 2);
  else await page.mouse.click(cx + 8, cy - 6);
  await page.waitForSelector('[data-testid=spot-answer]');
  await page.waitForTimeout(600);
  console.log(name, 'clicked', JSON.stringify(await facts()));
  await top();
  await shot('09-dropped-marker-with-card');
  // "Zoom in here" on a point inside the map copy, then a click at that zoom
  await type(sites[0].lat, sites[0].lon);
  await press(page.getByTestId('spot-zoom'));
  await page.waitForTimeout(1600);
  await top();
  await shot('10-zoomed-in-on-the-spot');
  if (!opts.hasTouch) {
    await page.mouse.click(cx - 30, cy + 22);
    await page.waitForSelector('[data-testid=spot-answer]');
    await page.waitForTimeout(600);
    console.log(name, 'clicked zoomed', JSON.stringify(await facts()));
    await shot('11-dropped-marker-zoomed-in');
    await scroll('spot-nasa');
    await page.waitForTimeout(150);
    await shot('12-dropped-marker-zoomed-in-nasa-rows');
  }
  await ctx.close();
}
await browser.close();
