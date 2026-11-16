// Frame-time measurement in Google Chrome on the Mac (GPU via ANGLE/Metal), outside the Claude browser pane.
//   cd web && npm run build && node scripts/perf_mac.mjs
// Starts `vite preview` on port 4174, opens Explore at 1512x982 @2x, measures idle, camera moves, time steps and playback,
// writes docs/perf/mac-chrome-<date>.json. Display-only measurement: it changes nothing in the app.
import { execSync, spawn } from 'node:child_process';
import { existsSync, mkdirSync, writeFileSync } from 'node:fs';
import { chromium } from '@playwright/test';

const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const port = 4174;
const server = spawn('npx', ['vite', 'preview', '--port', String(port), '--strictPort'], { stdio: 'ignore' });
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
try {
  for (let i = 0; i < 40; i++) {
    try { if ((await fetch(`http://localhost:${port}/`)).ok) break; } catch { /* not up yet */ }
    await wait(250);
  }
  const browser = await chromium.launch({
    headless: false,
    executablePath: existsSync(CHROME) ? CHROME : undefined,
    args: ['--use-angle=metal', '--ignore-gpu-blocklist', '--enable-gpu-rasterization', '--disable-background-timer-throttling', '--disable-renderer-backgrounding',
      // Chrome's Energy Saver caps animation at 30 fps on battery (seen 15 Nov 01:22 and 01:37). Turn it off so the number is the app's.
      '--disable-features=BatterySaverModeAvailable,HighEfficiencyModeAvailable'],
  });
  const page = await browser.newPage({ viewport: { width: 1512, height: 982 }, deviceScaleFactor: 2 });
  const t0 = Date.now();
  await page.goto(`http://localhost:${port}/#sky`);
  await page.waitForSelector('[data-testid=scene3d][data-context=loaded]', { timeout: 60_000 });
  const modelVisibleMs = Date.now() - t0;
  await wait(3000);
  const result = await page.evaluate(async () => {
    const lt = [];
    new PerformanceObserver((l) => l.getEntries().forEach((e) => lt.push(Math.round(e.duration)))).observe({ type: 'longtask' });
    const m = async (ms) => {
      const ts = [];
      await new Promise((res) => { const s = performance.now(); const f = (t) => { ts.push(t); if (t - s < ms) requestAnimationFrame(f); else res(); }; requestAnimationFrame(f); });
      const d = ts.slice(1).map((t, i) => t - ts[i]).sort((a, b) => a - b);
      const q = (p) => +d[Math.min(d.length - 1, Math.floor(d.length * p))].toFixed(2);
      return { frames: d.length, meanMs: +(d.reduce((a, b) => a + b, 0) / d.length).toFixed(2), p50Ms: q(0.5), p95Ms: q(0.95), p99Ms: q(0.99), maxMs: q(1), over33ms: d.filter((x) => x > 33.4).length };
    };
    const gl = document.querySelector('[data-testid=scene3d] canvas').getContext('webgl2');
    const dbg = gl.getExtension('WEBGL_debug_renderer_info');
    const r = { renderer: dbg ? gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) : null, canvas: [gl.drawingBufferWidth, gl.drawingBufferHeight] };
    r.idle = await m(5000);
    document.querySelector('[data-testid=cam-context]').click(); r.cameraToContext = await m(2500);
    document.querySelector('[data-testid=cam-approach]').click(); r.cameraToApproach = await m(2500);
    const next = [...document.querySelectorAll('.temporal button')].find((b) => b.textContent.trim() === '›');
    lt.length = 0;
    const steps = [];
    for (let i = 0; i < 10; i++) { next.click(); steps.push(await m(500)); }
    r.timeSteps = { p95Ms: Math.max(...steps.map((s) => s.p95Ms)), maxMs: Math.max(...steps.map((s) => s.maxMs)), longTasksMs: lt.splice(0) };
    const play = [...document.querySelectorAll('button')].find((b) => /^Play$/.test(b.textContent.trim()));
    play.click(); r.playback = await m(8000); play.click(); r.playbackLongTasksMs = lt.splice(0);
    r.jsHeapMB = performance.memory ? Math.round(performance.memory.usedJSHeapSize / 1048576) : null;
    return r;
  });
  let power = null;
  try { power = execSync('pmset -g batt', { encoding: 'utf8' }).trim().split('\n').join(' | '); } catch { /* not macOS */ }
  const lowPowerMode = (() => { try { return /lowpowermode\s+1/.test(execSync('pmset -g', { encoding: 'utf8' })); } catch { return null; } })();
  const out = { schema: 'polaris-perf-v1', power, lowPowerMode, chromeEnergySaverDisabled: true, measuredUTC: new Date().toISOString(), browser: browser.version(), viewport: { css: [1512, 982], devicePixelRatio: 2 }, build: 'web/dist via vite preview', modelVisibleMs, ...result };
  mkdirSync('docs/perf', { recursive: true });
  const file = `docs/perf/mac-chrome-${out.measuredUTC.slice(0, 10)}.json`;
  writeFileSync(file, JSON.stringify(out, null, 2));
  console.log(JSON.stringify(out, null, 2));
  console.log(`wrote ${file}`);
  await browser.close();
} finally {
  server.kill();
}
