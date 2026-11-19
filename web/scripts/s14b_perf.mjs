// S14 Part B: load time and GPU memory of each Moon model (?globe=v2 | 8k | svs) on the high and the low tier, in Google
// Chrome on this Mac (GPU via ANGLE/Metal). Display-only measurement: it changes nothing in the app.
//   cd web && npm run build && node scripts/s14b_perf.mjs        -> ../tmp/s14b/perf.json
// Starts `vite preview` on port 4175. Per model, three cold-cache runs each of:
//   high  1440 x 900 at 2x, ?quality=high (post chain on)
//   low   390 x 844 at 3x, touch, CPU slowed 4x (the app picks its low tier: no post chain; svs = its reduced image)
// Reported per run:
//   firstMoonFrameMs   performance.now() at the first frame with a Moon in it (navigation start = 0; the opening sequence
//                      is playing then). The app start is the same for every model, so differences are the model's.
//   modelShownMs       when the asked model is on screen: the same as above, except for the 8k model, which comes in over
//                      the compact one (the time its crossfade starts)
//   fetched            the model files the page fetched (and the Draco decoder for v2): bytes and fetch time, from the
//                      browser's resource timings (server on localhost: this is disk and parse speed, not a network)
//   gpuTextureMB / gpuGeometryMB   what the scene holds on the GPU, worked out from the live scene: every Moon image as
//                      RGBA8 with its mipmaps (width x height x 4 x 4/3) and every vertex / index buffer
//   gpuProcessMB / rendererMB      resident memory of Chrome's GPU process and of the page's process (from `ps`)
//   idle               frame times over 4 s at rest
import { execFileSync, spawn } from 'node:child_process';
import { existsSync, mkdirSync, writeFileSync } from 'node:fs';
import { chromium } from '@playwright/test';

const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const port = 4175;
const server = spawn('npx', ['vite', 'preview', '--port', String(port), '--strictPort'], { stdio: 'ignore' });
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const chromeMem = () => {
  const rows = execFileSync('ps', ['-axo', 'rss=,command='], { encoding: 'utf8', maxBuffer: 64e6 }).split('\n').filter((l) => l.includes('playwright_chromiumdev_profile'));
  const mb = (re) => rows.filter((l) => re.test(l)).map((l) => +(parseInt(l.trim(), 10) / 1024).toFixed(0));
  return { rendererMB: Math.max(0, ...mb(/--type=renderer/)), gpuProcessMB: Math.max(0, ...mb(/--type=gpu-process/)) };
};
const inPage = async () => {
  const g = document.querySelector('[data-testid=simple-globe]');
  const h = window.__polarisGlobe;
  const ts = [];
  await new Promise((res) => {
    const s = performance.now();
    const f = (t) => { ts.push(t); if (performance.now() - s < 4000) requestAnimationFrame(f); else res(); };
    requestAnimationFrame(f);
  });
  const d = ts.slice(1).map((t, i) => t - ts[i]).sort((a, b) => a - b);
  const q = (p) => +d[Math.min(d.length - 1, Math.floor(d.length * p))].toFixed(2);
  let tex = 0;
  let geo = 0;
  let tris = 0;
  const texList = [];
  const seenT = new Set();
  const seenG = new Set();
  h.scene.traverse((o) => {
    if (!o.isMesh) return;
    const m = o.material?.map;
    if (m?.image && !seenT.has(m.uuid)) {
      seenT.add(m.uuid);
      tex += (m.image.width * m.image.height * 4 * 4) / 3;
      texList.push(`${m.image.width}x${m.image.height}`);
    }
    if (m && o.geometry && !seenG.has(o.geometry.uuid)) {
      seenG.add(o.geometry.uuid);
      for (const a of Object.values(o.geometry.attributes)) geo += a.array.byteLength;
      if (o.geometry.index) (geo += o.geometry.index.array.byteLength), (tris += o.geometry.index.count / 3);
    }
  });
  const files = performance.getEntriesByType('resource').filter((e) => /\/globe\/.*\.glb|\/draco\//.test(e.name)).map((e) => ({ file: e.name.split('/').slice(-2).join('/'), bytes: e.decodedBodySize, fetchMs: +(e.responseEnd - e.startTime).toFixed(0), startMs: +e.startTime.toFixed(0) }));
  const ext = h.gl.getContext().getExtension('WEBGL_debug_renderer_info');
  return {
    asset: g.dataset.asset,
    renderer: ext ? h.gl.getContext().getParameter(ext.UNMASKED_RENDERER_WEBGL) : 'unknown',
    post: !!window.__polarisPost,
    canvasPx: [h.gl.domElement.width, h.gl.domElement.height],
    firstMoonFrameMs: Number(g.dataset.firstFrameMs),
    modelShownMs: g.dataset.upgradeMs ? Number(g.dataset.upgradeMs) : Number(g.dataset.firstFrameMs),
    fetched: files,
    fetchedMB: +(files.reduce((s, f) => s + f.bytes, 0) / 1048576).toFixed(2),
    moonImages: texList,
    moonTriangles: tris,
    gpuTextureMB: +(tex / 1048576).toFixed(1),
    gpuGeometryMB: +(geo / 1048576).toFixed(1),
    threeMemory: { ...h.gl.info.memory },
    jsHeapMB: performance.memory ? +(performance.memory.usedJSHeapSize / 1048576).toFixed(1) : null,
    idle: { frames: d.length, p50Ms: q(0.5), p95Ms: q(0.95), maxMs: q(1), over20ms: d.filter((x) => x > 20).length },
  };
};
try {
  for (let i = 0; i < 40; i++) {
    try { if ((await fetch(`http://localhost:${port}/`)).ok) break; } catch { /* not up yet */ }
    await wait(250);
  }
  const out = { date: new Date().toISOString(), note: 'server on localhost, cold cache per run (a new browser context each); see the header of web/scripts/s14b_perf.mjs for what each figure is' };
  const tiers = [
    ['high_1440x900_2x', { viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 }, 1, '&quality=high'],
    ['low_phone_390x844_3x_touch_cpu4x', { viewport: { width: 390, height: 844 }, deviceScaleFactor: 3, hasTouch: true, isMobile: true }, 4, ''],
  ];
  for (const model of ['v2', '8k', 'svs'])
    for (const [name, opts, cpu, query] of tiers) {
      const runs = [];
      for (let k = 0; k < 3; k++) {
        // a browser per run: the GPU process's memory then belongs to this one page
        const browser = await chromium.launch({
          headless: false,
          executablePath: existsSync(CHROME) ? CHROME : undefined,
          args: ['--use-angle=metal', '--ignore-gpu-blocklist', '--enable-gpu-rasterization', '--disable-background-timer-throttling', '--disable-renderer-backgrounding', '--disable-features=BatterySaverModeAvailable,HighEfficiencyModeAvailable'],
        });
        const ctx = await browser.newContext(opts);
        const page = await ctx.newPage();
        if (cpu > 1) await (await ctx.newCDPSession(page)).send('Emulation.setCPUThrottlingRate', { rate: cpu });
        await page.goto(`http://localhost:${port}/?mode=simple&globe=${model}${query}`);
        await page.waitForSelector('[data-testid=simple-globe][data-shown=true][data-first-frame-ms]', { timeout: 120_000 });
        await page.waitForSelector('[data-testid=simple-mode]:not([data-intro])', { timeout: 120_000 });
        await page.waitForSelector('[data-testid=simple-globe]:not([data-upgrade])', { timeout: 180_000 });
        await wait(2500);
        const r = await page.evaluate(inPage);
        runs.push({ ...r, ...chromeMem() });
        await browser.close();
        await wait(500);
      }
      out[`${model}_${name}`] = runs;
      console.log(model, name, JSON.stringify(runs.map((r) => ({ asset: r.asset, first: r.firstMoonFrameMs, shown: r.modelShownMs, fetchedMB: r.fetchedMB, fetchMs: r.fetched.map((f) => `${f.file}:${f.fetchMs}`).join(' '), texMB: r.gpuTextureMB, geoMB: r.gpuGeometryMB, images: r.moonImages.join(','), tris: r.moonTriangles, gpuProc: r.gpuProcessMB, rend: r.rendererMB, heap: r.jsHeapMB, p50: r.idle.p50Ms, p95: r.idle.p95Ms, max: r.idle.maxMs, post: r.post }))));
    }
  mkdirSync('../tmp/s14b', { recursive: true });
  writeFileSync('../tmp/s14b/perf.json', JSON.stringify(out, null, 1));
  console.log('wrote ../tmp/s14b/perf.json');
} finally {
  server.kill();
}
