// Section R: Simple-mode post effects (WebGL EffectComposer) against the view before them, in Google Chrome on this Mac's GPU.
// The same method as the R gate (scripts/proto_webgpu_compare.mjs on branch r-webgpu-proto).
//
//   # "current": a build of the commit before section R, served on its own port
//   git archive 70779c7 web/src web/index.html web/tsconfig.json web/vite.config.ts web/package.json | tar -x -C /tmp/base
//   (cd /tmp/base/web && ln -s <repo>/web/node_modules . && ln -s <repo>/web/public . && npx vite build && npx vite preview --port 4175 --strictPort) &
//   # "new": this working tree
//   (cd web && npx vite build && npx vite preview --port 4176 --strictPort) &
//   cd web && node scripts/post_compare.mjs [perf] [shots] [checks] [expert]      (no argument = all four)
//
// perf    time to first frame (5 fresh browsers each, interleaved), frame time p50 / p95 over 10 s idle and 10 s of orbiting,
//         long tasks (> 50 ms), with the display's vsync and with the frame-rate limit off (the real cost per frame)
// shots   Approach and Mast-eye, current vs new, at 1440x900 and 390x844 (as a narrow window, and as an emulated phone)
// checks  ground brightness current vs new at the same sample and camera; bloom limited to the Sun; grain is zero-mean
// expert  Expert mode Explore / Decision / Evidence at 1440x900, 1024x768 and 390x844, current vs new, pixel by pixel
// Display-only measurement: it changes nothing in the app. Output: docs/perf/r-post/ (results.json + PNGs).
import { execSync } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { chromium } from '@playwright/test';

const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const BASE = process.env.POLARIS_BASE_URL ?? 'http://127.0.0.1:4175';
const NEW = process.env.POLARIS_NEW_URL ?? 'http://127.0.0.1:4176';
const OUT = process.env.POLARIS_OUT ?? '../docs/perf/r-post';
const SITE = 'site04_roi3';
const SAMPLE = '2026-11-18T21:00:00Z'; // a bundle sample of site04_roi3 with the Sun in sight (bundle flag); the R gate used it too
const BLOCKED = '2026-11-27T02:00:00Z'; // a bundle sample of site04_roi3 where the bundle says the Sun is blocked
const want = (k) => process.argv.length <= 2 || process.argv.includes(k);
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const sh = (c) => { try { return execSync(c, { encoding: 'utf8' }).trim(); } catch { return null; } };
mkdirSync(OUT, { recursive: true });

const FLAGS = ['--use-angle=metal', '--ignore-gpu-blocklist', '--enable-gpu-rasterization', '--disable-background-timer-throttling', '--disable-renderer-backgrounding',
  '--disable-backgrounding-occluded-windows', '--disable-features=BatterySaverModeAvailable,HighEfficiencyModeAvailable,CalculateNativeWinOcclusion'];
const UNCAPPED = ['--disable-frame-rate-limit', '--disable-gpu-vsync'];
const launch = (extra = []) => chromium.launch({ headless: false, executablePath: existsSync(CHROME) ? CHROME : undefined, args: [...FLAGS, ...extra] });
const simple = (origin, cam, q = '', t = SAMPLE) => `${origin}/?mode=simple&site=${SITE}&t=${t}&cam=${cam}${q}`;
const READY = '[data-testid=scene3d][data-context=loaded]';

const VARIANTS = [
  { id: 'current', origin: BASE, q: '', label: 'Current (70779c7)' },
  { id: 'new-high', origin: NEW, q: '&quality=high', label: 'New · high tier' },
  { id: 'new-medium', origin: NEW, q: '&quality=medium', label: 'New · medium tier' },
  { id: 'new-low', origin: NEW, q: '&quality=low', label: 'New · low tier (post off)' },
];

/** frame-time statistics and long tasks over `ms` of requestAnimationFrame callbacks (runs in the page) */
const measureSrc = `(ms) => new Promise((res) => {
  const lt = []; const po = new PerformanceObserver((l) => l.getEntries().forEach((e) => lt.push(Math.round(e.duration)))); po.observe({ type: 'longtask' });
  const ts = []; const s = performance.now();
  const f = (t) => { ts.push(t); if (t - s < ms) requestAnimationFrame(f); else {
    po.disconnect();
    const d = ts.slice(1).map((t, i) => t - ts[i]).sort((a, b) => a - b);
    const q = (p) => +d[Math.min(d.length - 1, Math.floor(d.length * p))].toFixed(2);
    res({ frames: d.length, fps: +(d.length / ((ts[ts.length - 1] - ts[0]) / 1000)).toFixed(1), meanMs: +(d.reduce((a, b) => a + b, 0) / d.length).toFixed(3), p50Ms: q(0.5), p95Ms: q(0.95), p99Ms: q(0.99), maxMs: q(1), over33ms: d.filter((x) => x > 33.4).length, longTasksMs: lt });
  } };
  requestAnimationFrame(f);
})`;

async function firstFrame(page, url) {
  const t0 = Date.now();
  await page.goto(url);
  await page.waitForSelector(READY, { timeout: 90_000 });
  await page.evaluate(() => new Promise((res) => requestAnimationFrame(() => requestAnimationFrame(res))));
  return Date.now() - t0; // navigation start -> terrain mounted and two frames presented
}

async function perfRun(v, uncapped) {
  const browser = await launch(uncapped ? UNCAPPED : []);
  const page = await browser.newPage({ viewport: { width: 1512, height: 982 }, deviceScaleFactor: 2 });
  const errors = [];
  page.on('console', (m) => { if (m.type() === 'error' && !/favicon/.test(m.text())) errors.push(m.text().slice(0, 200)); });
  page.on('pageerror', (e) => errors.push(String(e).slice(0, 200)));
  const r = { id: v.id, vsync: !uncapped, url: simple(v.origin, 'approach', v.q) };
  r.firstFrameMs = await firstFrame(page, r.url);
  const box = await page.locator('.simple-stage').boundingBox();
  r.stageCss = { w: Math.round(box.width), h: Math.round(box.height) };
  await wait(5000); // the cast-shadow pass is spread over frames; let it finish
  r.renderer = await page.evaluate(() => {
    const c = document.querySelector('[data-testid=scene3d] canvas');
    const gl = c.getContext('webgl2');
    const dbg = gl?.getExtension('WEBGL_debug_renderer_info');
    return { device: dbg ? gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) : null, canvas: [c.width, c.height], quality: document.querySelector('[data-testid=scene3d]').dataset.quality ?? null, post: !!window.__polarisPost };
  });
  r.idle = await page.evaluate(`(${measureSrc})(10000)`);
  const cx = box.x + box.width * 0.3;
  const cy = box.y + box.height * 0.3;
  await page.mouse.move(cx, cy);
  await page.mouse.down();
  const orbit = page.evaluate(`(${measureSrc})(10000)`);
  const s = Date.now();
  while (Date.now() - s < 10_000) {
    const t = (Date.now() - s) / 1000;
    await page.mouse.move(cx + 170 * Math.sin((2 * Math.PI * t) / 5), cy + 28 * Math.sin((2 * Math.PI * t) / 2.5));
    await wait(8);
  }
  r.orbit = await orbit;
  await page.mouse.up();
  r.jsHeapMB = await page.evaluate(() => (performance.memory ? Math.round(performance.memory.usedJSHeapSize / 1048576) : null));
  r.consoleErrors = [...new Set(errors)];
  await browser.close();
  return r;
}

/** Pixel statistics of two PNG files, computed in a blank page (no image library in this repo). regions: {name: [x0, y0, x1, y1]} as fractions. */
async function pixelStats(page, fileA, fileB, regions = { all: [0, 0, 1, 1] }) {
  const url = (f) => `data:image/png;base64,${readFileSync(f).toString('base64')}`;
  return page.evaluate(async ({ a, b, regions }) => {
    const load = async (u) => { const i = new Image(); i.src = u; await i.decode(); const c = document.createElement('canvas'); c.width = i.naturalWidth; c.height = i.naturalHeight; const g = c.getContext('2d', { willReadFrequently: true }); g.drawImage(i, 0, 0); return g.getImageData(0, 0, c.width, c.height); };
    const A = await load(a);
    const B = await load(b);
    const out = { size: [A.width, A.height], sameSize: A.width === B.width && A.height === B.height };
    if (!out.sameSize) return out;
    const lum = (d, k) => 0.2126 * d[k] + 0.7152 * d[k + 1] + 0.0722 * d[k + 2];
    for (const [name, [fx0, fy0, fx1, fy1]] of Object.entries(regions)) {
      const x0 = Math.floor(fx0 * A.width), x1 = Math.ceil(fx1 * A.width), y0 = Math.floor(fy0 * A.height), y1 = Math.ceil(fy1 * A.height);
      let n = 0, sa = 0, sb = 0, sabs = 0, differing = 0, over2 = 0, maxDiff = 0, sd = 0;
      for (let y = y0; y < y1; y++) for (let x = x0; x < x1; x++) {
        const k = (y * A.width + x) * 4;
        const la = lum(A.data, k), lb = lum(B.data, k);
        const d = Math.max(Math.abs(A.data[k] - B.data[k]), Math.abs(A.data[k + 1] - B.data[k + 1]), Math.abs(A.data[k + 2] - B.data[k + 2]));
        n++; sa += la; sb += lb; sabs += Math.abs(la - lb); sd += lb - la;
        if (d > 0) differing++;
        if (d > 2) over2++;
        if (d > maxDiff) maxDiff = d;
      }
      out[name] = { pixels: n, meanLumaA: +(sa / n).toFixed(3), meanLumaB: +(sb / n).toFixed(3), meanSignedDiff: +(sd / n).toFixed(4), meanAbsDiff: +(sabs / n).toFixed(4), differingPixels: differing, differingOver2Levels: over2, maxChannelDiff: maxDiff };
    }
    return out;
  }, { a: url(fileA), b: url(fileB), regions });
}

/** one image with labelled cells next to each other */
async function sideBySide(page, files, labels, outFile, width) {
  const cells = files.map((f, i) => `<figure><img src="data:image/png;base64,${readFileSync(f).toString('base64')}"><figcaption>${labels[i]}</figcaption></figure>`).join('');
  await page.setViewportSize({ width, height: 600 });
  await page.setContent(`<body style="margin:0;background:#0b0b0b;display:flex;gap:8px;padding:8px;font:13px/1.4 ui-monospace,monospace;color:#ECE7DD">
    <style>figure{margin:0;flex:1}img{width:100%;display:block}figcaption{padding:6px 2px}</style>${cells}</body>`);
  await page.locator('body').screenshot({ path: outFile });
}

const results = existsSync(`${OUT}/results.json`) ? JSON.parse(readFileSync(`${OUT}/results.json`, 'utf8')) : {};
Object.assign(results, {
  schema: 'polaris-r-post-compare-v1', measuredUTC: new Date().toISOString(), sample: SAMPLE, site: SITE, machine: sh('sysctl -n machdep.cpu.brand_string'),
  power: sh('pmset -g batt')?.split('\n').join(' | '), lowPowerMode: /lowpowermode\s+1/.test(sh('pmset -g') ?? ''), build: 'vite build + vite preview; current = 70779c7, new = working tree',
  note: 'Display-only measurement. firstFrameMs = navigation start to terrain mounted + two presented frames. Long tasks from PerformanceObserver("longtask") during each 10 s window.',
});
const save = () => writeFileSync(`${OUT}/results.json`, JSON.stringify(results, null, 2));

if (want('perf')) {
  results.perf = { viewport: { css: [1512, 982], devicePixelRatio: 2 }, runs: [], firstFrame: {} };
  // POLARIS_PERF_QUICK=current,new-high: only those variants, frame-rate limit off, no first-frame repeats (for tuning)
  const quick = process.env.POLARIS_PERF_QUICK?.split(',') ?? null;
  for (const uncapped of quick ? [true] : [false, true]) {
    for (const v of VARIANTS.filter((x) => !quick || quick.includes(x.id))) {
      const r = await perfRun(v, uncapped);
      results.perf.runs.push(r);
      console.log(`${r.id} ${uncapped ? 'uncapped' : 'vsync'}: first frame ${r.firstFrameMs} ms · idle mean ${r.idle.meanMs} p50 ${r.idle.p50Ms} p95 ${r.idle.p95Ms} long ${JSON.stringify(r.idle.longTasksMs)} · orbit mean ${r.orbit.meanMs} p50 ${r.orbit.p50Ms} p95 ${r.orbit.p95Ms} long ${JSON.stringify(r.orbit.longTasksMs)} · canvas ${r.renderer.canvas} post ${r.renderer.post}`);
      save();
    }
  }
  for (let rep = 0; rep < (quick ? 0 : 5); rep++) {
    for (const v of VARIANTS.filter((x) => x.id === 'current' || x.id === 'new-high')) {
      const browser = await launch();
      const page = await browser.newPage({ viewport: { width: 1512, height: 982 }, deviceScaleFactor: 2 });
      (results.perf.firstFrame[v.id] ??= []).push(await firstFrame(page, simple(v.origin, 'approach', v.q)));
      await browser.close();
    }
  }
  for (const k of Object.keys(results.perf.firstFrame)) {
    const runs = results.perf.firstFrame[k];
    const a = [...runs].sort((x, y) => x - y);
    results.perf.firstFrame[k] = { runsMs: runs, medianMs: a[2], minMs: a[0], maxMs: a[4] };
    console.log(`first frame ${k}: median ${a[2]} ms (min ${a[0]}, max ${a[4]})`);
  }
  save();
}

if (want('shots')) {
  const browser = await launch();
  const tool = await browser.newPage();
  results.shots = [];
  const SIZES = [
    { id: '1440x900', ctx: { viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 }, note: 'desktop window, pixel ratio 2' },
    { id: '390x844-window', ctx: { viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 }, note: 'narrow desktop window on this Mac (tier picked from the device: high)' },
    { id: '390x844-phone', ctx: { viewport: { width: 390, height: 844 }, screen: { width: 390, height: 844 }, deviceScaleFactor: 3, isMobile: true, hasTouch: true }, note: 'emulated phone (touch, 390 px screen): tier picked from the device' },
  ];
  for (const size of SIZES) {
    const ctx = await browser.newContext({ ...size.ctx, reducedMotion: 'reduce' }); // reduced motion: camera cuts are instant and the grain is one fixed pattern
    for (const cam of ['approach', 'mast']) {
      const files = [];
      const info = {};
      for (const v of [VARIANTS[0], { id: 'new', origin: NEW, q: '', label: 'New (tier picked from the device)' }]) {
        const page = await ctx.newPage();
        await page.goto(simple(v.origin, cam, v.q));
        await page.waitForSelector(READY, { timeout: 90_000 });
        await wait(6000);
        info[v.id] = await page.evaluate(() => ({ quality: document.querySelector('[data-testid=scene3d]').dataset.quality ?? null, post: !!window.__polarisPost }));
        const f = `${OUT}/${size.id}-${cam}-${v.id}.png`;
        await page.locator('.simple-stage').screenshot({ path: f });
        const full = `${OUT}/${size.id}-${cam}-${v.id}-page.png`;
        await page.screenshot({ path: full });
        files.push(f);
        await page.close();
      }
      await sideBySide(tool, files, [`Current (70779c7) · ${cam} · ${size.id}`, `New · tier ${info.new.quality}${info.new.post ? ' · post on' : ' · post off'} · ${cam} · ${size.id}`], `${OUT}/compare-${size.id}-${cam}.png`, size.id === '1440x900' ? 2000 : 820);
      const stats = await pixelStats(tool, files[0], files[1]);
      results.shots.push({ size: size.id, note: size.note, cam, tier: info.new.quality, post: info.new.post, files, diff: stats.all });
      console.log(`shot ${size.id} ${cam}: tier ${info.new.quality} post ${info.new.post} · mean luma ${stats.all?.meanLumaA} -> ${stats.all?.meanLumaB} · differing pixels ${stats.all?.differingPixels}`);
    }
    await ctx.close();
  }
  await browser.close();
  save();
}

if (want('checks')) {
  const browser = await launch();
  const tool = await browser.newPage();
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2, reducedMotion: 'reduce' });
  results.checks = {};
  const open = async (origin, cam, q, t) => {
    const page = await ctx.newPage();
    await page.goto(simple(origin, cam, q, t));
    await page.waitForSelector(READY, { timeout: 90_000 });
    await wait(6000);
    return page;
  };
  const shot = async (page, name) => { const f = `${OUT}/check-${name}.png`; await page.locator('[data-testid=scene3d] canvas').screenshot({ path: f }); return f; };
  const setPost = (page, o) => page.evaluate(async (o) => {
    const p = window.__polarisPost;
    if ('grain' in o) p.last.uniforms.uGrain.value = p.grainOnly.uniforms.uGrain.value = o.grain;
    if ('bloom' in o) p.bloom.strength = o.bloom;
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(() => requestAnimationFrame(r))));
  }, o);

  // 1. Ground brightness, same sample and camera. Regions are fractions of the canvas: the lower part is ground in both cameras.
  for (const cam of ['approach', 'mast']) {
    const ground = { ground: cam === 'mast' ? [0.05, 0.62, 0.95, 0.85] : [0.1, 0.55, 0.9, 0.9], sky: [0.05, 0.04, 0.95, 0.2] };
    const a = await open(BASE, cam, '');
    const fa = await shot(a, `${cam}-current`);
    const b = await open(NEW, cam, '&quality=high');
    const fb = await shot(b, `${cam}-new`);
    await setPost(b, { grain: 0 });
    const fb0 = await shot(b, `${cam}-new-nograin`);
    const low = await open(NEW, cam, '&quality=low');
    const fl = await shot(low, `${cam}-new-low`);
    results.checks[`ground-${cam}`] = {
      what: 'current vs new (high tier), canvas only, same sample and camera',
      withGrain: await pixelStats(tool, fa, fb, ground),
      grainOff: await pixelStats(tool, fa, fb0, ground),
      lowTierVsCurrent: await pixelStats(tool, fa, fl, { all: [0, 0, 1, 1] }),
    };
    console.log(`ground ${cam}:`, JSON.stringify(results.checks[`ground-${cam}`]));
    await a.close(); await b.close(); await low.close();
  }

  // 2. Bloom limited to the Sun. (a) Sun in the picture: bloom on vs off differs only near the Sun. (b) A sample where the bundle
  //    says the Sun is blocked (no HDR disc is drawn): bloom on vs off must be identical everywhere -> nothing else crosses the threshold.
  const blocked = BLOCKED; // the page's own bundle flag is read back below (pageSaysSunNow)
  results.checks.blockedSample = blocked;
  for (const [name, t] of [['sun-visible', SAMPLE], ...(blocked ? [['sun-blocked', blocked]] : [])]) {
    const p = await open(NEW, 'mast', '&quality=high', t);
    const state = await p.evaluate(() => /Sun now\s*(.+?)\s*Earth now/is.exec(document.querySelector('[data-testid=plain-answer]')?.innerText ?? '')?.[1] ?? null); // the page's own bundle reading
    await setPost(p, { grain: 0 });
    const on = await shot(p, `bloom-${name}-on`);
    await setPost(p, { bloom: 0 });
    const off = await shot(p, `bloom-${name}-off`);
    results.checks[`bloom-${name}`] = { sample: t, pageSaysSunNow: state, onVsOff: (await pixelStats(tool, off, on)).all };
    console.log(`bloom ${name} (${t}, Sun now: ${state}):`, JSON.stringify(results.checks[`bloom-${name}`].onVsOff));
    await p.close();
  }
  await ctx.close();
  await browser.close();
  save();
}

if (want('expert')) {
  // Expert mode must be unchanged: Explore (#sky), Decision, Evidence at 1440x900, 1024x768 and 390x844, current vs new, same browser, reduced motion.
  const browser = await launch();
  const tool = await browser.newPage();
  results.expert = [];
  for (const [vw, vh] of [[1440, 900], [1024, 768], [390, 844]]) for (const tab of ['sky', 'decision', 'evidence']) {
    const files = [];
    const size = vw === 1440 ? '' : `-${vw}x${vh}`;
    for (const v of [{ id: 'current', origin: BASE }, { id: 'new', origin: NEW }]) {
      const ctx = await browser.newContext({ viewport: { width: vw, height: vh }, deviceScaleFactor: 1, reducedMotion: 'reduce' });
      const page = await ctx.newPage();
      await page.goto(`${v.origin}/?mode=expert&site=${SITE}&t=${SAMPLE}#${tab}`);
      await page.waitForSelector(tab === 'sky' ? READY : `#ws-${tab}`, { timeout: 90_000 });
      await wait(tab === 'sky' ? 8000 : 3000);
      const f = `${OUT}/expert-${tab}${size}-${v.id}.png`;
      await page.screenshot({ path: f });
      files.push(f);
      await ctx.close();
    }
    const d = (await pixelStats(tool, files[0], files[1])).all;
    results.expert.push({ tab, viewport: `${vw}x${vh}`, files, diff: d });
    console.log(`expert ${tab} ${vw}x${vh}: differing pixels ${d.differingPixels} of ${d.pixels} (max channel diff ${d.maxChannelDiff})`);
  }
  await browser.close();
  save();
}
console.log(`wrote ${OUT}/results.json`);
