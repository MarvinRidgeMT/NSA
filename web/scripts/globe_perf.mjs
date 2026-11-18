// S4 globe: first frame and frame time in Google Chrome on this Mac (GPU via ANGLE/Metal), outside the Claude browser pane.
//   cd web && npm run build && node scripts/globe_perf.mjs
// Starts `vite preview` on port 4174 and measures the Simple-mode landing globe three ways, three runs each:
//   desktop  1440 x 900 at 2x, the device's own quality tier, the best Moon model present (the 8k one when it is there)
//   desktop  the same with ?globe=compact (the compact model that is in the repository)
//   phone    390 x 844 at 3x, touch (so the app picks its low tier: lighter Moon image, no post), CPU slowed 4x
// Memory: resident size of the page's renderer process and of Chrome's GPU process (from `ps`, one page open), and the JS heap.
// Writes docs/perf/s4-globe-<date>.json. Display-only measurement: it changes nothing in the app.
import { execFileSync, spawn } from 'node:child_process';
import { existsSync, mkdirSync, writeFileSync } from 'node:fs';
import { chromium } from '@playwright/test';

const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const port = 4174;
const server = spawn('npx', ['vite', 'preview', '--port', String(port), '--strictPort'], { stdio: 'ignore' });
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

// resident memory (MB) of this Chrome's processes, by type; Playwright's Chrome is told apart by its temporary profile folder
const chromeMem = () => {
  const rows = execFileSync('ps', ['-axo', 'rss=,command='], { encoding: 'utf8', maxBuffer: 64e6 }).split('\n').filter((l) => l.includes('playwright_chromiumdev_profile'));
  const mb = (re) => rows.filter((l) => re.test(l)).map((l) => +(parseInt(l.trim(), 10) / 1024).toFixed(0));
  return { rendererMB: Math.max(0, ...mb(/--type=renderer/)), gpuProcessMB: Math.max(0, ...mb(/--type=gpu-process/)) };
};

const inPage = async () => {
  const frames = async (ms, act) => {
    const lt = [];
    const po = new PerformanceObserver((l) => l.getEntries().forEach((e) => lt.push(Math.round(e.duration))));
    po.observe({ type: 'longtask' });
    const ts = [];
    await new Promise((res) => {
      const s = performance.now();
      const f = (t) => { ts.push(t); if (performance.now() - s < ms) requestAnimationFrame(f); else res(); };
      requestAnimationFrame(f);
      act?.();
    });
    po.disconnect();
    const d = ts.slice(1).map((t, i) => t - ts[i]).sort((a, b) => a - b);
    const q = (p) => +d[Math.min(d.length - 1, Math.floor(d.length * p))].toFixed(2);
    return { frames: d.length, meanMs: +(d.reduce((a, b) => a + b, 0) / d.length).toFixed(2), p50Ms: q(0.5), p95Ms: q(0.95), p99Ms: q(0.99), maxMs: q(1), over20ms: d.filter((x) => x > 20).length, longTasksMs: lt };
  };
  const g = document.querySelector('[data-testid=simple-globe]');
  // the globe's post chain, taken now: the terrain scene has its own and clears the shared hook when it unmounts
  const post = window.__polarisPost;
  const idle = await frames(5000);
  const hook = window.__polarisGlobe;
  const glc = hook.gl.getContext();
  const pinBtn = document.querySelector('.s-globe-pin button');
  const flyIn = await frames(1200, () => { pinBtn.click(); requestAnimationFrame(() => document.querySelector('[data-testid=pin-card-fly]')?.click()); }); // 18 Nov: a pin opens its card; the card's button flies
  await new Promise((r) => setTimeout(r, 2500));
  const back = document.querySelector('[data-testid=simple-back-moon]');
  const flyOut = await frames(1200, () => back.click());
  await new Promise((r) => setTimeout(r, 1500));
  const terrainGone = !document.querySelector('.simple-stage');
  // time to issue one frame's draw calls, frame limit out of the way (gl.finish does not wait for Chrome's GPU process, so
  // this is the main-thread cost only; the rAF figures above are the whole-frame evidence). Measured last, each
  // time (measured last, so the queued GPU work cannot disturb the flights)
  await new Promise((r) => setTimeout(r, 1500));
  const N = 200;
  const t0 = performance.now();
  for (let i = 0; i < N; i++) { if (post) post.composer.render(); else hook.gl.render(hook.scene, hook.camera); glc.finish(); }
  const drawMs = +((performance.now() - t0) / N).toFixed(3);
  const ext = glc.getExtension('WEBGL_debug_renderer_info');
  return {
    renderer: ext ? glc.getParameter(ext.UNMASKED_RENDERER_WEBGL) : 'unknown',
    asset: g.dataset.asset,
    jsHeapMB: performance.memory ? +(performance.memory.usedJSHeapSize / 1048576).toFixed(1) : null,
    post: !!post,
    canvasPx: [hook.gl.domElement.width, hook.gl.domElement.height],
    firstMoonFrameMs: Number(g.dataset.firstFrameMs),
    betterModelShownMs: g.dataset.upgradeMs ? Number(g.dataset.upgradeMs) : null,
    terrainUnmountedAfterReturn: terrainGone, idle, cpuSubmitMsPerFrameUncapped: drawMs, flyIn, flyOut,
  };
};

try {
  for (let i = 0; i < 40; i++) {
    try { if ((await fetch(`http://localhost:${port}/`)).ok) break; } catch { /* not up yet */ }
    await wait(250);
  }
  const browser = await chromium.launch({
    headless: false,
    executablePath: existsSync(CHROME) ? CHROME : undefined,
    args: ['--use-angle=metal', '--ignore-gpu-blocklist', '--enable-gpu-rasterization', '--disable-background-timer-throttling', '--disable-renderer-backgrounding',
      '--disable-features=BatterySaverModeAvailable,HighEfficiencyModeAvailable'],
  });
  const out = { date: new Date().toISOString(), note: 'firstMoonFrameMs = performance.now() at the first frame that shows the Moon (navigation start = 0), server on localhost, cold cache per context' };
  const cases = [
    ['desktop_1440x900_2x', { viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 }, 1, ''],
    ['desktop_1440x900_2x_compact_model', { viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 }, 1, '?globe=compact'],
    ['phone_390x844_3x_touch_cpu4x', { viewport: { width: 390, height: 844 }, deviceScaleFactor: 3, hasTouch: true, isMobile: true }, 4, ''],
  ];
  for (const [name, opts, cpu, query] of cases) {
    const runs = [];
    for (let k = 0; k < 3; k++) {
      const ctx = await browser.newContext(opts);
      const page = await ctx.newPage();
      if (cpu > 1) await (await ctx.newCDPSession(page)).send('Emulation.setCPUThrottlingRate', { rate: cpu });
      await page.goto(`http://localhost:${port}/${query}`);
      await page.waitForSelector('[data-testid=simple-globe][data-shown=true][data-first-frame-ms]', { timeout: 60_000 });
      // the 8k model, where present, takes the compact one's place after the first frame: measure with it on screen
      await page.waitForSelector('[data-testid=simple-globe]:not([data-upgrade])', { timeout: 60_000 });
      await wait(1500);
      const memOnGlobe = chromeMem();
      runs.push({ ...(await page.evaluate(inPage)), memOnGlobe, memAfterFlights: chromeMem() });
      await ctx.close();
    }
    out[name] = runs;
    console.log(name, JSON.stringify(runs.map((r) => ({ first: r.firstMoonFrameMs, better: r.betterModelShownMs, idleP50: r.idle.p50Ms, idleP95: r.idle.p95Ms, idleMax: r.idle.maxMs, submit: r.cpuSubmitMsPerFrameUncapped, inP50: r.flyIn.p50Ms, inP95: r.flyIn.p95Ms, inMax: r.flyIn.maxMs, mem: r.memOnGlobe, heap: r.jsHeapMB, inFrames: r.flyIn.frames, outMax: r.flyOut.maxMs, asset: r.asset, post: r.post, canvas: r.canvasPx.join('x'), renderer: r.renderer }))));
  }
  await browser.close();
  mkdirSync('docs/perf', { recursive: true });
  const file = `docs/perf/s4-globe-${new Date().toISOString().slice(0, 10)}.json`;
  writeFileSync(file, JSON.stringify(out, null, 2));
  console.log('wrote', file);
} finally {
  server.kill();
}
