// S14 Part B: do the three Moon models show the same ground at the same latitude and longitude? A measurement, not part of
// the app. Each model is drawn by the app itself (?globe=v2 | 8k | svs) in Google Chrome on this Mac, looked at straight down
// over the same latitude / longitude at the same zoom, lit head-on for this measurement only (so the day-night line is out of
// the picture); the middle of each picture is then matched against the 8k model's by normalised cross-correlation over shifts
// of up to ±SEARCH pixels. A shift of 0 means a pin lands on the same ground on both models. Kilometres per pixel come from
// the app's own scale (radians per pixel at the view centre) and the manifest's radius.
//   cd web && npm run build && npx vite preview --port 5174
//   node scripts/s14b_register.mjs [base URL]        -> ../tmp/s14b/registration.json
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { chromium } from '@playwright/test';

const base = process.argv[2] ?? 'http://127.0.0.1:5174/';
const out = '../tmp/s14b';
mkdirSync(`${out}/registration`, { recursive: true });
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const manifest = JSON.parse(readFileSync('public/globe/globe_manifest.json', 'utf8'));
const v2 = manifest.globes.find((g) => g.url.endsWith('polaris_moon_globe.glb'));
const radiusKm = v2.radiusKm;
const bundle = JSON.parse(readFileSync('../data/viewer/polaris-x5d-roi-2026-11-14-v2.json', 'utf8'));
const site = bundle.datasets[0].site;
// places: around the equator, mid-latitudes both ways, near each pole, and the first bundle site
const places = [[0, 0], [0, 90], [0, 180], [0, -90], [-45, 45], [45, -60], [-60, -120], [30, 150], [-80, 0], [80, 120], [site.latitudePlanetocentricDeg, site.longitudeEastDeg]];
const SIZE = 480; // side of the compared square, CSS px, at the view centre
const SEARCH = 16;
const W = 1440;
const H = 900;
const browser = await chromium.launch({ headless: false, executablePath: existsSync(CHROME) ? CHROME : undefined, args: ['--use-angle=metal', '--ignore-gpu-blocklist'] });
const shots = {};
let kmPerPx = null;
let zoom = null;
for (const model of ['8k', 'v2', 'svs']) {
  const ctx = await browser.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  await page.goto(`${base}?mode=simple&globe=${model}&quality=low`);
  await page.waitForSelector('[data-testid=simple-globe][data-shown=true][data-first-frame-ms]', { timeout: 60_000 });
  await page.waitForSelector('[data-testid=simple-mode]:not([data-intro])', { timeout: 60_000 });
  await page.waitForSelector('[data-testid=simple-globe]:not([data-upgrade])', { timeout: 120_000 });
  await page.addStyleTag({ content: '.s-globe-pins,.s-spot-layer,.s-globe-nav,.s-globe-about,.s-gcard-layer{visibility:hidden!important}' });
  await page.waitForTimeout(800);
  // one zoom for all three: the closest the coarsest model allows (each model's own limit is read from the page)
  const zMin = await page.evaluate(() => window.__polarisGlobe.nav.zoomMin);
  shots[model] = { zoomMin: zMin, asset: await page.evaluate(() => document.querySelector('[data-testid=simple-globe]').dataset.asset), img: [] };
  if (model === '8k') continue; // revisited below once every model's limit is known
  await ctx.close();
}
// second pass with the common zoom
zoom = Math.max(...Object.values(shots).map((s) => s.zoomMin)) * 1.02;
for (const c of browser.contexts()) await c.close();
for (const model of ['8k', 'v2', 'svs']) {
  const ctx = await browser.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  await page.goto(`${base}?mode=simple&globe=${model}&quality=low`);
  await page.waitForSelector('[data-testid=simple-globe][data-shown=true][data-first-frame-ms]', { timeout: 60_000 });
  await page.waitForSelector('[data-testid=simple-mode]:not([data-intro])', { timeout: 60_000 });
  await page.waitForSelector('[data-testid=simple-globe]:not([data-upgrade])', { timeout: 120_000 });
  await page.addStyleTag({ content: '.s-globe-pins,.s-spot-layer,.s-globe-nav,.s-globe-about,.s-gcard-layer{visibility:hidden!important}' });
  await page.waitForTimeout(800);
  const box = await page.locator('.s-globe-canvas canvas').first().boundingBox();
  const clip = { x: Math.round(box.x + box.width / 2 - SIZE / 2), y: Math.round(box.y + box.height / 2 - SIZE / 2), width: SIZE, height: SIZE };
  for (const [lat, lon] of places) {
    const scale = await page.evaluate(
      async ([lat, lon, zoom]) => {
        const h = window.__polarisGlobe;
        const n = h.nav;
        const r = Math.PI / 180;
        // the app's model frame (globeMath.moonDir)
        const d = h.camera.position.clone().set(-Math.cos(lat * r) * Math.sin(lon * r), Math.sin(lat * r), -Math.cos(lat * r) * Math.cos(lon * r));
        const south = d.clone().set(0, -1, 0);
        n.quietUntil = Number.MAX_VALUE;
        n.vx = n.vy = 0;
        n.home = null;
        n.q.setFromUnitVectors(south, d);
        n.zoom = n.zoomNow = zoom;
        const raf = () => new Promise((res) => requestAnimationFrame(res));
        await raf();
        await raf();
        // measurement light: head-on, earthshine out (the app's own light is put back by the next page load)
        h.scene.traverse((o) => {
          if (!o.isDirectionalLight) return;
          o.position.copy(h.camera.position);
        });
        await raf();
        await raf();
        await raf();
        return n.radPerPx;
      },
      [lat, lon, zoom],
    );
    kmPerPx = scale * radiusKm;
    const png = await page.screenshot({ clip });
    writeFileSync(`${out}/registration/${model}_${lat}_${lon}.png`, png);
    shots[model].img.push(png.toString('base64'));
  }
  await ctx.close();
}
// compare in a page (it can decode PNGs): normalised cross-correlation of grey values over integer shifts, then a parabola
// through the best shift and its neighbours for the sub-pixel part
const cmp = await (await browser.newContext()).newPage();
const match = (a, b) =>
  cmp.evaluate(
    async ([a, b, S]) => {
      const grey = async (s) => {
        const i = new Image();
        i.src = 'data:image/png;base64,' + s;
        await i.decode();
        const c = document.createElement('canvas');
        c.width = i.width;
        c.height = i.height;
        const g = c.getContext('2d');
        g.drawImage(i, 0, 0);
        const d = g.getImageData(0, 0, c.width, c.height).data;
        const o = new Float32Array(c.width * c.height);
        for (let k = 0; k < o.length; k++) o[k] = 0.299 * d[4 * k] + 0.587 * d[4 * k + 1] + 0.114 * d[4 * k + 2];
        // take out the broad brightness (a 31 px box mean), so the match is on ground detail, not on overall tone
        const w = c.width;
        const hh = c.height;
        const R = 15;
        const tmp = new Float32Array(o.length);
        const out = new Float32Array(o.length);
        for (let y = 0; y < hh; y++) {
          let s = 0;
          let n = 0;
          for (let x = -R; x < w + R; x++) {
            if (x + R < w) (s += o[y * w + x + R]), n++;
            if (x - R - 1 >= 0) (s -= o[y * w + x - R - 1]), n--;
            if (x >= 0 && x < w) tmp[y * w + x] = s / n;
          }
        }
        for (let x = 0; x < w; x++) {
          let s = 0;
          let n = 0;
          for (let y = -R; y < hh + R; y++) {
            if (y + R < hh) (s += tmp[(y + R) * w + x]), n++;
            if (y - R - 1 >= 0) (s -= tmp[(y - R - 1) * w + x]), n--;
            if (y >= 0 && y < hh) out[y * w + x] = o[y * w + x] - s / n;
          }
        }
        return { p: out, w, h: hh };
      };
      const A = await grey(a);
      const B = await grey(b);
      const ncc = (dx, dy) => {
        let sa = 0, sb = 0, saa = 0, sbb = 0, sab = 0, n = 0;
        for (let y = S; y < A.h - S; y += 2)
          for (let x = S; x < A.w - S; x += 2) {
            const p = A.p[y * A.w + x];
            const q = B.p[(y + dy) * B.w + x + dx];
            sa += p; sb += q; saa += p * p; sbb += q * q; sab += p * q; n++;
          }
        return (sab - (sa * sb) / n) / Math.sqrt((saa - (sa * sa) / n) * (sbb - (sb * sb) / n));
      };
      let best = { c: -2, dx: 0, dy: 0 };
      for (let dy = -S + 1; dy < S; dy++) for (let dx = -S + 1; dx < S; dx++) { const c = ncc(dx, dy); if (c > best.c) best = { c, dx, dy }; }
      const sub = (m, z, p) => (m - 2 * z + p === 0 ? 0 : (0.5 * (m - p)) / (m - 2 * z + p));
      const edge = Math.abs(best.dx) >= S - 1 || Math.abs(best.dy) >= S - 1;
      const fx = edge ? 0 : sub(ncc(best.dx - 1, best.dy), best.c, ncc(best.dx + 1, best.dy));
      const fy = edge ? 0 : sub(ncc(best.dx, best.dy - 1), best.c, ncc(best.dx, best.dy + 1));
      return { corr: +best.c.toFixed(3), corrAtZero: +ncc(0, 0).toFixed(3), dxPx: +(best.dx + fx).toFixed(2), dyPx: +(best.dy + fy).toFixed(2), atSearchEdge: edge };
    },
    [a, b, SEARCH],
  );
const result = { date: new Date().toISOString(), note: 'shift of each model against the 8k model, in screen pixels and kilometres; head-on measurement light; 480 px square at the view centre', zoom, kmPerPx: +kmPerPx.toFixed(3), v2TexelKm: +((radiusKm * Math.PI) / 2 / 1024).toFixed(3), models: Object.fromEntries(Object.entries(shots).map(([k, v]) => [k, { asset: v.asset, zoomMin: v.zoomMin }])), rows: [] };
for (const model of ['v2', 'svs'])
  for (let i = 0; i < places.length; i++) {
    const m = await match(shots['8k'].img[i], shots[model].img[i]);
    const row = { model, against: '8k', lat: places[i][0], lon: places[i][1], ...m, shiftKm: +(Math.hypot(m.dxPx, m.dyPx) * kmPerPx).toFixed(2) };
    result.rows.push(row);
    console.log(JSON.stringify(row));
  }
// and the v2 globe against the compact model directly
for (let i = 0; i < places.length; i++) {
  const m = await match(shots.svs.img[i], shots.v2.img[i]);
  const row = { model: 'v2', against: 'svs', lat: places[i][0], lon: places[i][1], ...m, shiftKm: +(Math.hypot(m.dxPx, m.dyPx) * kmPerPx).toFixed(2) };
  result.rows.push(row);
  console.log(JSON.stringify(row));
}
writeFileSync(`${out}/registration.json`, JSON.stringify(result, null, 1));
console.log('km per screen px', result.kmPerPx, 'v2 texel km', result.v2TexelKm, 'wrote', `${out}/registration.json`);
await browser.close();
