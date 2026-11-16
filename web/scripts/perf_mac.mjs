// Frame-time measurement in Google Chrome on the Mac (GPU via ANGLE/Metal), outside the Claude browser pane.
//   cd web && npm run build && node scripts/perf_mac.mjs
// Starts `vite preview` on port 4174, opens Explore at 1512x982 @2x, measures idle, camera moves, time steps and playback,
// writes docs/perf/mac-chrome-<date>.json. Display-only measurement: it changes nothing in the app.
// `--lod` (5D Phase 9.4): opens Site04 ROI3 with the near-field LOD layer on (?lod=1), waits for the tiles to finish streaming,
// adds an orbit drag (real mouse events, so tiles stream during the measurement) and writes docs/perf/mac-chrome-lod-<date>.json.
import { execSync, spawn } from 'node:child_process';
import { existsSync, mkdirSync, writeFileSync } from 'node:fs';
import { chromium } from '@playwright/test';

const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const port = 4174;
const LOD = process.argv.includes('--lod');
// `--headless`: no window on screen (Chrome's new headless mode keeps the Metal GPU; check `renderer` in the output)
const HEADLESS = process.argv.includes('--headless');
// `--uncapped`: vsync and the frame-rate limit off, so a rAF interval is the real frame cost instead of the display period
const UNCAPPED = process.argv.includes('--uncapped');
const server = spawn('npx', ['vite', 'preview', '--port', String(port), '--strictPort'], { stdio: 'ignore' });
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
try {
  for (let i = 0; i < 40; i++) {
    try { if ((await fetch(`http://localhost:${port}/`)).ok) break; } catch { /* not up yet */ }
    await wait(250);
  }
  const browser = await chromium.launch({
    headless: HEADLESS,
    executablePath: existsSync(CHROME) ? CHROME : undefined,
    args: ['--use-angle=metal', '--ignore-gpu-blocklist', '--enable-gpu-rasterization', '--disable-background-timer-throttling', '--disable-renderer-backgrounding',
      // Chrome's Energy Saver caps animation at 30 fps on battery (seen 15 Nov 01:22 and 01:37). Turn it off so the number is the app's.
      '--disable-features=BatterySaverModeAvailable,HighEfficiencyModeAvailable',
      ...(UNCAPPED ? ['--disable-gpu-vsync', '--disable-frame-rate-limit'] : [])],
  });
  const page = await browser.newPage({ viewport: { width: 1512, height: 982 }, deviceScaleFactor: 2 });
  const pageErrors = [];
  page.on('crash', () => pageErrors.push('renderer crashed'));
  page.on('pageerror', (e) => pageErrors.push(String(e).slice(0, 300)));
  page.on('console', (msg) => { if (msg.type() === 'error' && !/Failed to load resource/.test(msg.text())) pageErrors.push(msg.text().slice(0, 300)); });
  page.on('close', () => console.error('page closed; errors so far:', JSON.stringify(pageErrors)));
  const t0 = Date.now();
  await page.goto(`http://localhost:${port}/${LOD ? '?bundle=polaris-x5d-roi-2026-11-14-v2.json&site=site04_roi3&lod=1' : ''}#sky`);
  await page.waitForSelector(LOD ? '[data-testid=scene3d][data-lod=on]' : '[data-testid=scene3d][data-context=loaded]', { timeout: 60_000 });
  if (LOD) await page.waitForFunction(() => { const p = document.querySelector('[data-testid=lod-panel]'); return p && +p.dataset.drawn > 1 && +p.dataset.pending === 0; }, null, { timeout: 60_000 });
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
    document.querySelector('[data-testid=cam-context]')?.click(); r.cameraToContext = await m(2500);
    if (document.querySelector('[data-testid=lod-panel]')) {
      // LOD: the regional and overhead framings pull in coarse levels; the orbit drag (driven from outside, below) streams tiles
      document.querySelector('[data-testid=cam-regional]').click(); r.cameraToRegional = await m(2500);
      document.querySelector('[data-testid=cam-overhead]').click(); r.cameraToOverhead = await m(2500);
    }
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
  if (LOD) {
    // orbit drag with real mouse input while measuring; then the panel's own counters
    const box = await page.locator('[data-testid=scene3d] canvas').boundingBox();
    await page.locator('[data-testid=cam-approach]').click();
    await wait(2500);
    const measure = page.evaluate(async () => {
      const ts = [];
      await new Promise((res) => { const s = performance.now(); const f = (t) => { ts.push(t); if (t - s < 6000) requestAnimationFrame(f); else res(); }; requestAnimationFrame(f); });
      const d = ts.slice(1).map((t, i) => t - ts[i]).sort((a, b) => a - b);
      const q = (p) => +d[Math.min(d.length - 1, Math.floor(d.length * p))].toFixed(2);
      return { frames: d.length, meanMs: +(d.reduce((a, b) => a + b, 0) / d.length).toFixed(2), p50Ms: q(0.5), p95Ms: q(0.95), p99Ms: q(0.99), maxMs: q(1), over16_7ms: d.filter((x) => x > 16.7).length };
    });
    await page.mouse.move(box.x + box.width * 0.5, box.y + box.height * 0.45);
    await page.mouse.down();
    for (let i = 0; i < 300; i++) { await page.mouse.move(box.x + box.width * 0.5 + i * 4, box.y + box.height * 0.45 + Math.sin(i / 20) * 40); await wait(16); }
    await page.mouse.up();
    result.orbitDrag = await measure;
    result.lodPanel = await page.evaluate(() => ({ ...document.querySelector('[data-testid=lod-panel]').dataset, source: undefined }));
  }
  let power = null;
  try { power = execSync('pmset -g batt', { encoding: 'utf8' }).trim().split('\n').join(' | '); } catch { /* not macOS */ }
  const lowPowerMode = (() => { try { return /lowpowermode\s+1/.test(execSync('pmset -g', { encoding: 'utf8' })); } catch { return null; } })();
  const out = { schema: 'polaris-perf-v1', power, lowPowerMode, chromeEnergySaverDisabled: true, pageErrors, measuredUTC: new Date().toISOString(), browser: browser.version(), viewport: { css: [1512, 982], devicePixelRatio: 2 }, build: 'web/dist via vite preview', headless: HEADLESS, uncapped: UNCAPPED, modelVisibleMs, ...result };
  mkdirSync('docs/perf', { recursive: true });
  const file = `docs/perf/mac-chrome-${LOD ? 'lod-' : ''}${HEADLESS ? 'headless-' : ''}${UNCAPPED ? 'uncapped-' : ''}${out.measuredUTC.slice(0, 10)}.json`;
  writeFileSync(file, JSON.stringify(out, null, 2));
  console.log(JSON.stringify(out, null, 2));
  console.log(`wrote ${file}`);
  await browser.close();
} finally {
  server.kill();
}
