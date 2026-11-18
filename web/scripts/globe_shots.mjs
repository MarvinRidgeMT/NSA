// S4 globe: screenshots in Google Chrome on this Mac (GPU via ANGLE/Metal) into ../tmp/s4 (git-ignored). Display check only.
//   cd web && npm run dev            (or any server that serves the app)
//   node scripts/globe_shots.mjs [base URL, default http://127.0.0.1:5174/] [extra query, e.g. globe=compact] [file suffix]
// Takes, at 1440 x 900 (2x) and 390 x 844 (3x, touch): the globe, a pin's label (hover on desktop, focus on the phone),
// the middle of the flight, the site after arrival, and the globe again after Esc.
import { existsSync, mkdirSync } from 'node:fs';
import { chromium } from '@playwright/test';

const base = process.argv[2] ?? 'http://127.0.0.1:5174/';
const extra = process.argv[3] ? `&${process.argv[3]}` : '';
const suffix = process.argv[4] ? `-${process.argv[4]}` : '';
const out = '../tmp/s4';
mkdirSync(out, { recursive: true });
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const browser = await chromium.launch({ headless: false, executablePath: existsSync(CHROME) ? CHROME : undefined, args: ['--use-angle=metal', '--ignore-gpu-blocklist'] });
const cases = [
  ['1440x900', { viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 }],
  ['390x844', { viewport: { width: 390, height: 844 }, deviceScaleFactor: 3, hasTouch: true, isMobile: true }],
];
for (const [name, opts] of cases) {
  const ctx = await browser.newContext(opts);
  const page = await ctx.newPage();
  const shot = (what) => page.screenshot({ path: `${out}/${what}-${name}${suffix}.png` });
  await page.goto(`${base}?mode=simple${extra}`);
  await page.waitForSelector('[data-testid=simple-globe][data-shown=true][data-first-frame-ms]', { timeout: 60_000 });
  await page.waitForSelector('[data-testid=simple-globe]:not([data-upgrade])', { timeout: 60_000 });
  await page.waitForTimeout(2500);
  const globe = page.getByTestId('simple-globe');
  console.log(name, 'asset', await globe.getAttribute('data-asset'), 'post', await page.evaluate(() => '__polarisPost' in window), 'scroll', await page.evaluate(() => [document.documentElement.scrollWidth, innerWidth]));
  await shot('globe');
  const pin = page.locator('.s-globe-pin button').nth(1);
  const where = () => page.locator('.s-globe-pin').nth(1).evaluate((e) => e.style.transform);
  if (opts.hasTouch) await pin.focus();
  else await pin.hover();
  await page.waitForTimeout(500);
  await shot('pin-label');
  const before = await where();
  if (opts.hasTouch) await pin.tap();
  else await pin.click();
  // 18 Nov: a pin opens its card; the card's button flies down
  if (opts.hasTouch) await page.getByTestId('pin-card-fly').tap();
  else await page.getByTestId('pin-card-fly').click();
  await page.waitForTimeout(520);
  await shot('mid-flight');
  await page.waitForSelector('[data-testid=simple-mode][data-place=site]', { timeout: 15_000 });
  await page.waitForSelector('[data-testid=scene3d]', { timeout: 30_000 });
  await page.waitForTimeout(3000);
  await shot('arrived');
  await page.keyboard.press('Escape');
  await page.waitForTimeout(600);
  await shot('mid-return');
  await page.waitForSelector('[data-testid=simple-mode][data-place=globe]', { timeout: 15_000 });
  await page.waitForTimeout(300);
  console.log(name, 'same framing after return:', (await where()) === before, before, await where());
  await page.mouse.move(5, 5);
  await page.waitForTimeout(700);
  await shot('globe-after-return');
  await ctx.close();
}
await browser.close();
