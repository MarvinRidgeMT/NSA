// S14 Part B: the default view (no ?globe=) in Google Chrome on this Mac (GPU via ANGLE/Metal), desktop and phone, into
// ../tmp/s14b (git-ignored). Display check: the values and positions are tested in tests/e2e/simple-s14b.spec.ts.
//   cd web && npm run build && npx vite preview --port 5174
//   node scripts/s14b_default_shots.mjs [base URL, default http://127.0.0.1:5174/]
// Per size: the opening sequence part-way, the hand-off to the globe (with the model on screen and every .glb fetched),
// a pin card, Check a spot from typed coordinates (the Shackleton site), a click-dropped point, and About this view.
import { existsSync, mkdirSync, readFileSync } from 'node:fs';
import { chromium } from '@playwright/test';

const base = process.argv[2] ?? 'http://127.0.0.1:5174/';
const out = '../tmp/s14b';
mkdirSync(out, { recursive: true });
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const bundle = JSON.parse(readFileSync('../data/viewer/polaris-x5d-roi-2026-11-14-v2.json', 'utf8'));
const shack = bundle.datasets.find((d) => /shackleton/i.test(d.site.name));
const browser = await chromium.launch({ headless: false, executablePath: existsSync(CHROME) ? CHROME : undefined, args: ['--use-angle=metal', '--ignore-gpu-blocklist'] });
const cases = [
  ['1440x900', { viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 }],
  ['390x844', { viewport: { width: 390, height: 844 }, deviceScaleFactor: 3, hasTouch: true, isMobile: true }],
];
let bad = 0;
for (const [name, opts] of cases) {
  const ctx = await browser.newContext(opts);
  const page = await ctx.newPage();
  const glbs = [];
  page.on('request', (r) => r.url().endsWith('.glb') && glbs.push(r.url().split('/').pop()));
  page.on('pageerror', (e) => (bad++, console.log(name, 'PAGE ERROR', e.message)));
  page.on('console', (m) => m.type() === 'error' && !/favicon/.test(m.location().url) && (bad++, console.log(name, 'console error', m.text().slice(0, 200))));
  const shot = (what) => page.screenshot({ path: `${out}/default-${what}-${name}.png` }).then(() => console.log(`${out}/default-${what}-${name}.png`));
  const press = (loc) => (opts.hasTouch ? loc.tap() : loc.click());
  await page.goto(`${base}?mode=simple`);
  // the opening sequence, part-way (its Sun and the Moon's night side)
  await page.waitForSelector('[data-testid=simple-mode][data-intro=play]', { timeout: 30_000 });
  await page.waitForSelector('[data-testid=simple-globe][data-state=ready]', { timeout: 60_000 });
  await page.waitForTimeout(1500);
  await shot('01-intro');
  // the hand-off: the globe is the place to use, the sequence is gone
  await page.waitForSelector('[data-testid=simple-globe][data-shown=true][data-first-frame-ms]', { timeout: 60_000 });
  await page.waitForSelector('[data-testid=simple-mode]:not([data-intro])', { timeout: 60_000 });
  await page.waitForTimeout(1500);
  const asset = await page.getAttribute('[data-testid=simple-globe]', 'data-asset');
  const up = await page.getAttribute('[data-testid=simple-globe]', 'data-upgrade-state');
  console.log(name, 'model on screen', asset, 'upgrade', up, 'models fetched', JSON.stringify(glbs));
  if (asset !== 'polaris_moon_globe.glb' || up !== null || glbs.join() !== 'polaris_moon_globe.glb') (bad++, console.log(name, 'NOT THE V2 DEFAULT'));
  await shot('02-globe-after-handoff');
  // a pin card
  await press(page.locator(`[data-testid=globe-pin-${shack.siteId}] button`));
  await page.waitForSelector('[data-testid=pin-card-any], [data-testid=pin-card-any-none]');
  await page.waitForTimeout(450);
  await shot('03-pin-card');
  await press(page.getByTestId('pin-card-close'));
  // Check a spot from typed coordinates: the Shackleton site itself
  await page.getByTestId('spot-lat').fill(String(shack.site.latitudePlanetocentricDeg));
  await page.getByTestId('spot-lon').fill(String(shack.site.longitudeEastDeg));
  await page.getByTestId('spot-lon').press('Enter');
  await page.waitForSelector('[data-testid=spot-near]');
  await page.waitForTimeout(600);
  console.log(name, 'typed spot answer', await page.getByTestId('spot-ours').getAttribute('data-match'));
  await shot('04-check-a-spot-typed');
  await press(page.getByTestId('spot-close'));
  // a click on the Moon drops a point there
  const box = await page.locator('.s-globe-canvas canvas').first().boundingBox();
  const at = { x: box.x + box.width * 0.42, y: box.y + box.height * 0.45 };
  if (opts.hasTouch) await page.touchscreen.tap(at.x, at.y);
  else await page.mouse.click(at.x, at.y);
  await page.waitForSelector('[data-testid=spot-answer]', { timeout: 20_000 });
  await page.waitForTimeout(600);
  console.log(name, 'dropped point', await page.getByTestId('spot-answer').evaluate((el) => `${el.dataset.lat}, ${el.dataset.lon}`));
  await shot('05-click-dropped-point');
  await press(page.getByTestId('spot-close'));
  await page.waitForTimeout(300);
  await press(page.locator('[data-testid=globe-about] summary'));
  await page.waitForTimeout(300);
  await shot('06-about');
  await ctx.close();
}
await browser.close();
console.log(bad ? `PROBLEMS: ${bad}` : 'no page errors; v2 is the default on both sizes');
