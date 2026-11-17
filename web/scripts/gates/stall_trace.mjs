// Frame-stall trace (docs/v2/GATES.md §6.6): which main-thread / GPU work fills the single long frames that the p95
// frame gate does not see. Same paths as perf_gates.mjs (region: Explore 3D + terrain context, camera "context";
// 5 m: ?lod=1 near-field LOD, camera "approach"), each 4 s idle + 5 s orbit drag, headed Chrome, vsync off.
//   cd web && npx vite build --minify false --outDir <dir> && node scripts/gates/stall_trace.mjs <dir> [--gpu] [--capped]
// An unminified build keeps function names. Every rAF interval > STALL_MS is marked in the trace with console.timeStamp;
// for each stall the script sums renderer-main-thread trace events and V8 CPU-profile samples (self time per function,
// and per first frame inside the app's own bundle) inside the stall window. Display-only; changes nothing in the app.
// Writes docs/v2/gates/stalls-<date>.json.
import { spawn } from 'node:child_process';
import { existsSync, mkdirSync, writeFileSync } from 'node:fs';
import { chromium } from '@playwright/test';

const DIST = process.argv.slice(2).find((a) => !a.startsWith('--')) ?? 'dist';
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const port = Number(process.env.POLARIS_STALL_PORT ?? 4231);
const STALL_MS = 100;
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const server = spawn('npx', ['vite', 'preview', '--outDir', DIST, '--port', String(port), '--strictPort'], { stdio: 'ignore' });
// Kept small: a full timeline trace of 9 s at this frame rate exceeds Node's maximum string length.
// --gpu: GPU-process and compositor events instead of the JS profile (the region stalls leave the main thread idle).
const GPU = process.argv.includes('--gpu');
// --capped: vsync and the frame-rate limit on (what a user sees); default uncapped like the deciding gate run.
const CAPPED = process.argv.includes('--capped');
const CATS = GPU ? ['devtools.timeline', 'gpu']
  : ['devtools.timeline', 'disabled-by-default-v8.cpu_profiler', 'disabled-by-default-v8.gc', 'blink.user_timing'];

const MARK = (ms) => new Promise((res) => {
  const ts = []; const s = performance.now();
  const f = (t) => { const n = ts.length; if (n && t - ts[n - 1] > 100) console.timeStamp(`stall ${(t - ts[n - 1]).toFixed(1)}`); ts.push(t); if (t - s < ms) requestAnimationFrame(f); else res(ts.slice(1).map((x, i) => x - ts[i]).filter((d) => d > 100).map((d) => +d.toFixed(1))); };
  requestAnimationFrame(f);
});

async function drag(page, sel, ms) {
  const box = await page.locator(sel).first().boundingBox();
  const m = page.evaluate(MARK, ms);
  await page.mouse.move(box.x + box.width * 0.5, box.y + box.height * 0.45); await page.mouse.down();
  for (let i = 0; i < Math.floor(ms / 20); i++) { await page.mouse.move(box.x + box.width * 0.5 + Math.sin(i / 25) * box.width * 0.25, box.y + box.height * 0.45 + Math.sin(i / 17) * 40); await wait(16); }
  await page.mouse.up();
  return m;
}

function analyse(buf) {
  const ev = JSON.parse(buf.toString()).traceEvents ?? JSON.parse(buf.toString());
  const tname = new Map(); const pname = new Map();
  for (const e of ev) if (e.ph === 'M' && e.name === 'thread_name') tname.set(`${e.pid}:${e.tid}`, e.args.name);
  for (const e of ev) if (e.ph === 'M' && e.name === 'process_name') pname.set(e.pid, e.args.name);
  const marks = ev.filter((e) => e.name === 'TimeStamp' && /^stall /.test(e.args?.data?.message ?? ''));
  if (!marks.length) return { stalls: [] };
  const main = `${marks[0].pid}:${marks[0].tid}`;
  const stalls = marks.map((m) => { const dt = +m.args.data.message.split(' ')[1]; return { t1: m.ts, t0: m.ts - dt * 1000, ms: dt }; });
  // V8 CPU profile on the main thread
  const nodes = new Map(); const samples = [];
  // main-thread samples only (the LOD worker's profile lives in the same process, on another thread)
  const prof = ev.filter((e) => (e.name === 'Profile' || e.name === 'ProfileChunk') && `${e.pid}:${e.tid}` === main);
  let t = 0;
  for (const e of prof) {
    if (e.name === 'Profile') { t = e.args.data.startTime; continue; }
    const cp = e.args.data.cpuProfile ?? {};
    for (const n of cp.nodes ?? []) nodes.set(n.id, n);
    const td = e.args.data.timeDeltas ?? [];
    (cp.samples ?? []).forEach((id, i) => { t += td[i] ?? 0; samples.push([t, id]); });
  }
  const frame = (id) => { const n = nodes.get(id); return n ? n.callFrame : null; };
  const parentOf = new Map(); for (const n of nodes.values()) for (const c of n.children ?? []) parentOf.set(c, n.id);
  for (const n of nodes.values()) if (n.parent != null) parentOf.set(n.id, n.parent);
  const label = (cf) => cf ? `${cf.functionName || '(anonymous)'} ${(cf.url || '').split('/').slice(-1)[0]}:${(cf.lineNumber ?? -1) + 1}` : '?';
  const appFrame = (id) => { for (let x = id; x != null; x = parentOf.get(x)) { const cf = frame(x); if (cf && /\/assets\/index|\/assets\/[A-Za-z0-9_-]+\.js/.test(cf.url || '')) return label(cf); } return '(no app frame)'; };
  const out = [];
  for (const s of stalls) {
    const inWin = (e) => e.ts < s.t1 && e.ts + (e.dur ?? 0) > s.t0;
    const top = {}; const gpu = {};
    for (const e of ev) {
      if (e.ph !== 'X' || !inWin(e) || (e.dur ?? 0) < 2000) continue;
      const key = `${e.pid}:${e.tid}`;
      const nm = e.name === 'FunctionCall' ? `FunctionCall ${e.args?.data?.functionName ?? ''} ${(e.args?.data?.url ?? '').split('/').slice(-1)[0]}` : e.name;
      if (key === main) top[nm] = (top[nm] ?? 0) + e.dur / 1000;
      else if (/Gpu|Viz|CrGpuMain|Compositor/.test(tname.get(key) ?? '') || /GPU/i.test(pname.get(e.pid) ?? '')) gpu[`${pname.get(e.pid) ?? e.pid}/${tname.get(key)}: ${e.name}`] = (gpu[`${pname.get(e.pid) ?? e.pid}/${tname.get(key)}: ${e.name}`] ?? 0) + e.dur / 1000;
    }
    const self = {}; const app = {}; let n = 0;
    for (const [ts, id] of samples) if (ts >= s.t0 && ts <= s.t1) {
      n++; const cf = frame(id); const k = label(cf); self[k] = (self[k] ?? 0) + 1; const a = appFrame(id); app[a] = (app[a] ?? 0) + 1;
    }
    const topk = (o, k = 8) => Object.entries(o).sort((a, b) => b[1] - a[1]).slice(0, k).map(([k2, v]) => [k2, +v.toFixed(1)]);
    out.push({ stallMs: s.ms, cpuSamples: n, mainThreadEventsMs: topk(top, 12), gpuThreadEventsMs: topk(gpu, 10),
      selfSamples: topk(self, 10), firstAppFrameSamples: topk(app, 8) });
  }
  return { mainThread: main, mainThreadName: tname.get(main), stalls: out };
}

const result = { schema: 'polaris-stall-trace-v1', measuredUTC: new Date().toISOString(), dist: DIST, stallThresholdMs: STALL_MS, capped: CAPPED, gpuTrace: GPU, levels: {} };
try {
  for (let i = 0; i < 80; i++) { try { if ((await fetch(`http://localhost:${port}/`)).ok) break; } catch { /* */ } await wait(250); }
  const browser = await chromium.launch({ headless: false, executablePath: existsSync(CHROME) ? CHROME : undefined,
    args: ['--use-angle=metal', '--ignore-gpu-blocklist', '--enable-gpu-rasterization', '--disable-background-timer-throttling',
      '--disable-renderer-backgrounding', '--disable-backgrounding-occluded-windows',
      ...(CAPPED ? [] : ['--disable-gpu-vsync', '--disable-frame-rate-limit'])] });
  result.browser = browser.version();
  const ctx = await browser.newContext({ viewport: { width: 1512, height: 982 }, deviceScaleFactor: 2 });
  const page = await ctx.newPage();
  const run = async (name, setup, canvas) => {
    await setup();
    await browser.startTracing(page, { categories: CATS });
    const idle = await page.evaluate(MARK, 4000);
    const a = analyse(await browser.stopTracing());
    await browser.startTracing(page, { categories: CATS });
    const dr = await drag(page, canvas, 5000);
    const b = analyse(await browser.stopTracing());
    result.levels[name] = { idle: { stallsMs: idle, ...a }, drag: { stallsMs: dr, ...b } };
    console.log(name, 'idle', idle, 'drag', dr);
  };
  await run('region', async () => {
    await page.goto(`http://localhost:${port}/#sky`);
    await page.waitForSelector('[data-testid=globe-open]', { timeout: 60_000 }); await page.click('[data-testid=globe-open]');
    await page.waitForSelector('[data-testid=global-moon][data-loaded=true]', { timeout: 60_000 }); await wait(3500);
    await page.click('[data-testid=globe-enter]');
    await page.waitForSelector('[data-testid=scene3d][data-context=loaded]', { timeout: 60_000 });
    await page.evaluate(() => document.querySelector('[data-testid=cam-context]')?.click()); await wait(2500);
  }, '[data-testid=scene3d] canvas');
  await run('fiveMetre', async () => {
    await page.goto(`http://localhost:${port}/?bundle=polaris-x5d-roi-2026-11-14-v2.json&site=site04_roi3&lod=1#sky`);
    await page.waitForSelector('[data-testid=scene3d][data-lod=on]', { timeout: 60_000 });
    await page.waitForFunction(() => { const p = document.querySelector('[data-testid=lod-panel]'); return p && +p.dataset.drawn > 1 && +p.dataset.pending === 0; }, null, { timeout: 90_000 });
    await page.evaluate(() => document.querySelector('[data-testid=cam-approach]')?.click()); await wait(2500);
  }, '[data-testid=scene3d] canvas');
  await browser.close();
} finally { server.kill(); }
try { result.loadAverage = (await import('node:os')).loadavg().map((x) => +x.toFixed(2)); } catch { /* */ }
mkdirSync('../docs/v2/gates', { recursive: true });
const file = `../docs/v2/gates/stalls-${GPU ? 'gpu-' : ''}${CAPPED ? 'capped-' : ''}${result.measuredUTC.slice(0, 10)}.json`;
writeFileSync(file, JSON.stringify(result, null, 1) + '\n');
console.log(`wrote ${file.replace('../', '')}`);
