// S14 Part B (the POLARIS v2 globe beside the two NASA SVS models): side-by-side screenshots in Google Chrome on this Mac (GPU
// via ANGLE/Metal) into ../tmp/s14b (git-ignored). Display check only: the frame of each model is tested in
// tests/unit/globe-v2.test.ts and tests/e2e/simple-s14b.spec.ts.
//   cd web && npm run build && npx vite preview --port 5174
//   node scripts/s14b_shots.mjs [base URL, default http://127.0.0.1:5174/] [extra query, e.g. globeflat=0.5]
// For each model (?globe=v2 | 8k | svs) at 1440 x 900 (2x, the device's own tier) and 390 x 844 (3x, touch: the low tier):
//   01 the whole Moon at rest (pole-on, the slow drift held so the three pictures match)
//   02 the south pole at the zoom limit of that model
//   03 mid-flight to the Shackleton site (the bundle site whose name says Shackleton)
//   04 "About this view" open (the model's credit and labels)
import { existsSync, mkdirSync, readFileSync } from 'node:fs';
import { chromium } from '@playwright/test';

const base = process.argv[2] ?? 'http://127.0.0.1:5174/';
const extra = process.argv[3] ? `&${process.argv[3]}` : '';
const tag = process.argv[4] ? `-${process.argv[4]}` : '';
const out = '../tmp/s14b';
mkdirSync(out, { recursive: true });
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const bundle = JSON.parse(readFileSync('../data/viewer/polaris-x5d-roi-2026-11-14-v2.json', 'utf8'));
const shack = bundle.datasets.find((d) => /shackleton/i.test(d.site.name));
if (!shack) throw new Error('no bundle site is named Shackleton');
const models = (process.env.MODELS ?? 'v2,8k,svs').split(',');
const browser = await chromium.launch({ headless: false, executablePath: existsSync(CHROME) ? CHROME : undefined, args: ['--use-angle=metal', '--ignore-gpu-blocklist'] });
const cases = [
  ['1440x900', { viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 }],
  ['390x844', { viewport: { width: 390, height: 844 }, deviceScaleFactor: 3, hasTouch: true, isMobile: true }],
];
for (const model of models)
  for (const [name, opts] of cases) {
    const ctx = await browser.newContext(opts);
    const page = await ctx.newPage();
    page.on('pageerror', (e) => console.log(model, name, 'PAGE ERROR', e.message));
    page.on('console', (m) => m.type() === 'error' && !/favicon/.test(m.location().url) && console.log(model, name, 'console error', m.text().slice(0, 200)));
    const shot = (what) => page.screenshot({ path: `${out}/${what}-${model}-${name}${tag}.png` }).then(() => console.log(`${out}/${what}-${model}-${name}${tag}.png`));
    const press = (loc) => (opts.hasTouch ? loc.tap() : loc.click());
    await page.goto(`${base}?mode=simple&globe=${model}${extra}`);
    await page.waitForSelector('[data-testid=simple-globe][data-shown=true][data-first-frame-ms]', { timeout: 60_000 });
    await page.waitForSelector('[data-testid=simple-mode]:not([data-intro])', { timeout: 60_000 });
    await page.waitForSelector('[data-testid=simple-globe]:not([data-upgrade])', { timeout: 120_000 }).catch(() => console.log(model, name, 'upgrade still pending'));
    await page.waitForTimeout(1200);
    // hold the slow drift and stand exactly pole-on, so the three models are seen from the same place
    const rest = () =>
      page.evaluate(() => {
        const n = window.__polarisGlobe.nav;
        n.quietUntil = Number.MAX_VALUE;
        n.vx = n.vy = 0;
        n.home = null;
        n.q.set(0, 0, 0, 1);
        n.zoom = n.zoomNow = 1;
      });
    await rest();
    await page.waitForTimeout(400);
    const info = await page.evaluate(() => {
      const g = document.querySelector('[data-testid=simple-globe]');
      const h = window.__polarisGlobe;
      const ext = h.gl.getContext().getExtension('WEBGL_debug_renderer_info');
      return { asset: g.dataset.asset, tier: document.querySelector('[data-testid=simple-mode]')?.dataset.quality ?? null, zoomMin: +h.nav.zoomMin.toFixed(4), renderer: ext ? h.gl.getContext().getParameter(ext.UNMASKED_RENDERER_WEBGL) : '' };
    });
    console.log(model, name, JSON.stringify(info));
    await shot('01-rest');
    // the south pole at this model's zoom limit
    await page.evaluate(() => {
      const n = window.__polarisGlobe.nav;
      n.zoom = n.zoomNow = n.zoomMin;
    });
    await page.waitForTimeout(500);
    await shot('02-pole-zoom-limit');
    await rest();
    await page.waitForTimeout(400);
    // "About this view": the model's credit and labels
    await press(page.locator('[data-testid=globe-about] summary'));
    await page.waitForTimeout(300);
    await shot('04-about');
    await press(page.locator('[data-testid=globe-about] summary'));
    // mid-flight to the Shackleton site: its pin, then the card's button, then half the flight
    await press(page.locator(`[data-testid=globe-pin-${shack.siteId}] button`));
    await page.waitForSelector('[data-testid=pin-card-fly]');
    await page.waitForTimeout(400);
    await press(page.getByTestId('pin-card-fly'));
    await page.waitForFunction(() => document.querySelector('[data-testid=simple-globe]')?.dataset.phase === 'in');
    await page.waitForTimeout(430);
    await shot('03-mid-flight-shackleton');
    await ctx.close();
  }
await browser.close();

// side by side: v2 | 8k | svs for each picture and size, labelled, as one image each
if (models.length === 3) {
  const b2 = await chromium.launch();
  const pg = await b2.newPage({ viewport: { width: 2400, height: 800 } });
  for (const what of ['01-rest', '02-pole-zoom-limit', '03-mid-flight-shackleton', '04-about'])
    for (const [name] of cases) {
      const cell = (m) => `<figure><img src="data:image/png;base64,${readFileSync(`${out}/${what}-${m}-${name}${tag}.png`).toString('base64')}"><figcaption>?globe=${m}</figcaption></figure>`;
      await pg.setContent(`<style>body{margin:0;background:#000;display:flex;gap:6px;width:max-content}figure{margin:0}img{display:block;height:${name === '390x844' ? 844 : 720}px}figcaption{font:600 15px system-ui;color:#ddd;padding:6px 10px;background:#111}</style>${models.map(cell).join('')}`);
      await pg.waitForFunction(() => [...document.images].every((i) => i.complete));
      await pg.locator('body').screenshot({ path: `${out}/side-by-side-${what}-${name}${tag}.png` });
      console.log(`${out}/side-by-side-${what}-${name}${tag}.png`);
    }
  await b2.close();
}
