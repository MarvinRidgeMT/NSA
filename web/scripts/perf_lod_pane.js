// 5D Phase 9.4: frame-time measurement of the near-field LOD layer INSIDE the Claude desktop app's browser pane.
// Usage: `npm run build && npx vite preview --port 4191`, open http://localhost:4191/?site=site04_roi3&lod=1#sky in the pane,
// wait for [data-testid=lod-panel] to report no pending tiles, then evaluate this file's contents in the page (the pane's
// JavaScript tool, or DevTools). It returns a JSON object; docs/perf/lod-pane-<date>.json holds the recorded runs.
// Method (same as scripts/perf_mac.mjs): requestAnimationFrame intervals over a fixed window; p95 = 95th percentile interval.
// Display-only measurement: it clicks camera views, drags the orbit control and steps time; it changes no bundle value.
(async () => {
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  const m = async (ms, during) => {
    const ts = [];
    let stop = false;
    const job = during ? during(() => stop) : null;
    await new Promise((res) => { const s = performance.now(); const f = (t) => { ts.push(t); if (t - s < ms) requestAnimationFrame(f); else res(); }; requestAnimationFrame(f); });
    stop = true;
    if (job) await job;
    const d = ts.slice(1).map((t, i) => t - ts[i]).sort((a, b) => a - b);
    if (!d.length) return { frames: 0, meanMs: null, p50Ms: null, p95Ms: Infinity, p99Ms: null, maxMs: performance.now() - ts[0], over16_7ms: 1 };
    const q = (p) => +d[Math.min(d.length - 1, Math.floor(d.length * p))].toFixed(2);
    return { frames: d.length, meanMs: +(d.reduce((a, b) => a + b, 0) / d.length).toFixed(2), p50Ms: q(0.5), p95Ms: q(0.95), p99Ms: q(0.99), maxMs: q(1), over16_7ms: d.filter((x) => x > 16.7).length };
  };
  const panel = () => document.querySelector('[data-testid=lod-panel]');
  const facts = () => ({ drawn: +panel().dataset.drawn, finestM: +panel().dataset.finest, pending: +panel().dataset.pending });
  const settle = async () => { for (let i = 0; i < 60 && facts().pending > 0; i++) await wait(250); await wait(500); };
  const canvas = document.querySelector('[data-testid=scene3d] canvas');
  const drag = (dxPerFrame) => async (stopped) => {
    const r = canvas.getBoundingClientRect();
    let x = r.left + r.width * 0.5;
    const y = r.top + r.height * 0.45;
    const ev = (type, xx) => canvas.dispatchEvent(new PointerEvent(type, { clientX: xx, clientY: y, pointerId: 1, pointerType: 'mouse', button: 0, buttons: type === 'pointerup' ? 0 : 1, bubbles: true }));
    ev('pointerdown', x);
    while (!stopped()) { x += dxPerFrame; ev('pointermove', x); await new Promise((r2) => requestAnimationFrame(r2)); }
    ev('pointerup', x);
  };
  const gl = canvas.getContext('webgl2');
  if (!document.querySelector('[data-testid=scene3d]')?.dataset.lod) throw new Error('no LOD layer on this page');
  const dbg = gl.getExtension('WEBGL_debug_renderer_info');
  const out = { schema: 'polaris-perf-lod-v1', measuredUTC: new Date().toISOString(), where: 'Claude desktop app browser pane', url: location.href,
    paneVisibility: document.visibilityState, renderer: dbg ? gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) : null, canvas: [gl.drawingBufferWidth, gl.drawingBufferHeight], devicePixelRatio, lod: document.querySelector('[data-testid=scene3d]').dataset.lod };
  const lt = [];
  try { new PerformanceObserver((l) => l.getEntries().forEach((e) => lt.push(Math.round(e.duration)))).observe({ type: 'longtask' }); } catch { /* unsupported */ }
  out.views = {};
  for (const id of ['approach', 'regional', 'overhead', 'mast', 'approach']) {
    const b = document.querySelector(`[data-testid=cam-${id}]`);
    if (!b) continue;
    b.click();
    const transition = await m(2500);
    await settle();
    out.views[`${id}${out.views[id] ? '_again' : ''}`] = { transition, idle: await m(3000), ...facts() };
  }
  out.orbitDrag = { ...(await m(5000, drag(6))), ...facts() };
  await settle();
  out.orbitDragFast = { ...(await m(5000, drag(18))), ...facts() };
  const next = [...document.querySelectorAll('.temporal button')].find((b) => b.textContent.trim() === '›');
  if (next) { const steps = []; for (let i = 0; i < 8; i++) { next.click(); steps.push(await m(500)); } out.timeSteps = { p95Ms: Math.max(...steps.map((s) => s.p95Ms)), maxMs: Math.max(...steps.map((s) => s.maxMs)) }; }
  out.longTasksMs = lt;
  const all = [...Object.values(out.views).flatMap((v) => [v.transition, v.idle]), out.orbitDrag, out.orbitDragFast];
  out.worstP95Ms = Math.max(...all.map((x) => x.p95Ms));
  out.jsHeapMB = performance.memory ? Math.round(performance.memory.usedJSHeapSize / 1048576) : null;
  return out;
})();
