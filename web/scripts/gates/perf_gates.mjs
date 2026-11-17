// Gates (prompt §7): p95 frame <= 16 ms at globe, region and 5 m levels; cold start <= 5 s to the first globe frame.
//   cd web && npm run build && node scripts/gates/perf_gates.mjs [--uncapped] [--headless]
// Method = web/scripts/perf_mac.mjs: Google Chrome (Metal via ANGLE), vite preview of web/dist, 1512x982 @2x, frame time =
// requestAnimationFrame interval. Each level: 4 s idle + 5 s orbit drag with real mouse events (+ 5 s playback at region).
// --uncapped: vsync and the frame-rate limit off, so an interval is the frame cost, not the display period (the gate's
// deciding run, docs/v2/GATES.md); the capped run is recorded as context. Writes docs/v2/gates/perf-<mode>-<date>.json.
// Display-only measurement: it changes nothing in the app. Port: POLARIS_PLAYWRIGHT_PORT (default 4221).
import { execSync, spawn } from 'node:child_process';
import { existsSync, mkdirSync, writeFileSync } from 'node:fs';
import { chromium } from '@playwright/test';

const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const port = Number(process.env.POLARIS_PLAYWRIGHT_PORT ?? 4221);
const HEADLESS = process.argv.includes('--headless');
const UNCAPPED = process.argv.includes('--uncapped');
const GATE_P95_MS = 16;
const GATE_COLD_MS = 5000;
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const server = spawn('npx', ['vite', 'preview', '--port', String(port), '--strictPort'], { stdio: 'ignore' });

// rAF interval statistics over `ms`, run inside the page
const MEASURE = async (ms) => {
  const ts = [];
  await new Promise((res) => { const s = performance.now(); const f = (t) => { ts.push(t); if (t - s < ms) requestAnimationFrame(f); else res(); }; requestAnimationFrame(f); });
  const d = ts.slice(1).map((t, i) => t - ts[i]).sort((a, b) => a - b);
  const q = (p) => +d[Math.min(d.length - 1, Math.floor(d.length * p))].toFixed(2);
  return { frames: d.length, meanMs: +(d.reduce((a, b) => a + b, 0) / d.length).toFixed(2), p50Ms: q(0.5), p95Ms: q(0.95), p99Ms: q(0.99), maxMs: q(1), over16ms: d.filter((x) => x > 16).length, visibility: document.visibilityState, focused: document.hasFocus() };
};

async function drag(page, canvasSel, measureMs) {
  const box = await page.locator(canvasSel).first().boundingBox();
  const m = page.evaluate(MEASURE, measureMs);
  await page.mouse.move(box.x + box.width * 0.5, box.y + box.height * 0.45);
  await page.mouse.down();
  const n = Math.floor(measureMs / 20);
  for (let i = 0; i < n; i++) { await page.mouse.move(box.x + box.width * 0.5 + Math.sin(i / 25) * box.width * 0.25, box.y + box.height * 0.45 + Math.sin(i / 17) * 40); await wait(16); }
  await page.mouse.up();
  return m;
}

const level = (idle, dragM, extra = {}) => {
  const all = [idle, dragM, ...Object.values(extra)];
  const p95 = Math.max(...all.map((x) => x.p95Ms));
  return { idle, orbitDrag: dragM, ...extra, worstP95Ms: p95, pass: p95 <= GATE_P95_MS };
};

const out = { schema: 'polaris-gates-perf-v1', measuredUTC: new Date().toISOString(), gate: { p95FrameMs: GATE_P95_MS, coldStartMs: GATE_COLD_MS }, headless: HEADLESS, uncapped: UNCAPPED, port, pageErrors: [] };
try {
  for (let i = 0; i < 60; i++) {
    try { if ((await fetch(`http://localhost:${port}/`)).ok) break; } catch { /* not up yet */ }
    await wait(250);
  }
  const browser = await chromium.launch({
    headless: HEADLESS,
    executablePath: existsSync(CHROME) ? CHROME : undefined,
    args: ['--use-angle=metal', '--ignore-gpu-blocklist', '--enable-gpu-rasterization', '--disable-background-timer-throttling', '--disable-renderer-backgrounding', '--disable-backgrounding-occluded-windows',
      '--disable-features=BatterySaverModeAvailable,HighEfficiencyModeAvailable',
      ...(UNCAPPED ? ['--disable-gpu-vsync', '--disable-frame-rate-limit'] : [])],
  });
  out.browser = browser.version();
  const ctx = await browser.newContext({ viewport: { width: 1512, height: 982 }, deviceScaleFactor: 2 });   // fresh: no HTTP cache
  const page = await ctx.newPage();
  page.on('pageerror', (e) => out.pageErrors.push(String(e).slice(0, 300)));
  page.on('console', (msg) => { if (msg.type() === 'error' && !/Failed to load resource/.test(msg.text())) out.pageErrors.push(msg.text().slice(0, 300)); });

  // ---- cold start: navigation -> globe open -> first globe frame (rAF after the model reports ready)
  await page.goto(`http://localhost:${port}/#sky`);
  await page.waitForSelector('[data-testid=globe-open]', { timeout: 60_000 });
  const tButton = await page.evaluate(() => performance.now());
  await page.click('[data-testid=globe-open]');
  await page.waitForSelector('[data-testid=global-moon][data-loaded=true]', { timeout: 60_000 });
  const tGlobe = await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame((t) => r(t)))));
  const nav = await page.evaluate(() => { const n = performance.getEntriesByType('navigation')[0]; return n ? { domContentLoadedMs: Math.round(n.domContentLoadedEventEnd), loadMs: Math.round(n.loadEventEnd) } : null; });
  out.coldStart = { firstGlobeFrameMs: Math.round(tGlobe), globeButtonReadyMs: Math.round(tButton), navigation: nav,
    method: 'performance.now() from navigation start, fresh browser context (empty HTTP cache), globe opened by a click as soon as its button exists; the app starts in the terrain view, so the click is part of the path',
    pass: tGlobe <= GATE_COLD_MS };
  out.renderer = await page.evaluate(() => { const c = document.querySelector('[data-testid=global-moon] canvas'); const gl = c && (c.getContext('webgl2') || c.getContext('webgl')); const d = gl && gl.getExtension('WEBGL_debug_renderer_info'); return d ? gl.getParameter(d.UNMASKED_RENDERER_WEBGL) : null; });

  // ---- globe level
  await wait(3500);    // the fly-to-site animation
  const gIdle = await page.evaluate(MEASURE, 4000);
  const gDrag = await drag(page, '[data-testid=global-moon] canvas', 5000);
  out.globe = level(gIdle, gDrag);

  // ---- region level (terrain context scene)
  await page.click('[data-testid=globe-enter]');
  await page.waitForSelector('[data-testid=scene3d][data-context=loaded]', { timeout: 60_000 });
  await page.evaluate(() => document.querySelector('[data-testid=cam-context]')?.click());
  await wait(2500);
  const rIdle = await page.evaluate(MEASURE, 4000);
  const rDrag = await drag(page, '[data-testid=scene3d] canvas', 5000);
  const play = await page.evaluate(async (MEASURE_SRC) => {
    const MEASURE = eval(MEASURE_SRC);   // eslint-disable-line no-eval
    const b = [...document.querySelectorAll('button')].find((x) => /^Play$/.test(x.textContent.trim()));
    if (!b) return null;
    b.click(); const r = await MEASURE(5000); b.click(); return r;
  }, MEASURE.toString());
  out.region = level(rIdle, rDrag, play ? { playback: play } : {});

  // ---- 5 m level (near-field LOD tiles, PGDA 78 5 m)
  await page.goto(`http://localhost:${port}/?bundle=polaris-x5d-roi-2026-11-14-v2.json&site=site04_roi3&lod=1#sky`);
  try {
    await page.waitForSelector('[data-testid=scene3d][data-lod=on]', { timeout: 60_000 });
    await page.waitForFunction(() => { const p = document.querySelector('[data-testid=lod-panel]'); return p && +p.dataset.drawn > 1 && +p.dataset.pending === 0; }, null, { timeout: 60_000 });
    await page.evaluate(() => document.querySelector('[data-testid=cam-approach]')?.click());
    await wait(2500);
    const lIdle = await page.evaluate(MEASURE, 4000);
    const lDrag = await drag(page, '[data-testid=scene3d] canvas', 5000);
    const lodPanel = await page.evaluate(() => { const p = document.querySelector('[data-testid=lod-panel]'); return p ? Object.fromEntries(Object.entries(p.dataset)) : null; });
    out.fiveMetre = { ...level(lIdle, lDrag), lodPanel };
  } catch (e) {
    out.fiveMetre = { pass: false, error: `5 m level not reachable: ${String(e).slice(0, 200)} (LOD tiles under web/public/context/lod are git-ignored)` };
  }
  out.jsHeapMB = await page.evaluate(() => (performance.memory ? Math.round(performance.memory.usedJSHeapSize / 1048576) : null));
  await browser.close();
} finally {
  server.kill();
}
try { out.power = execSync('pmset -g batt', { encoding: 'utf8' }).trim().split('\n').join(' | '); } catch { /* not macOS */ }
try { out.lowPowerMode = /lowpowermode\s+1/.test(execSync('pmset -g', { encoding: 'utf8' })); } catch { /* */ }
out.pass = { globe: out.globe?.pass ?? false, region: out.region?.pass ?? false, fiveMetre: out.fiveMetre?.pass ?? false, coldStart: out.coldStart?.pass ?? false };
mkdirSync('../docs/v2/gates', { recursive: true });
const file = `../docs/v2/gates/perf-${HEADLESS ? 'headless' : 'headed'}-${UNCAPPED ? 'uncapped' : 'capped'}-${out.measuredUTC.slice(0, 10)}.json`;
writeFileSync(file, JSON.stringify(out, null, 2) + '\n');
console.log(JSON.stringify({ coldStart: out.coldStart, globe: out.globe?.worstP95Ms, region: out.region?.worstP95Ms, fiveMetre: out.fiveMetre?.worstP95Ms ?? out.fiveMetre?.error, pass: out.pass, renderer: out.renderer, pageErrors: out.pageErrors }, null, 1));
console.log(`wrote ${file.replace('../', '')}`);
