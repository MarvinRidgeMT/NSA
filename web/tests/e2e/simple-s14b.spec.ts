import { test, expect, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { GLOBE_8K, GLOBE_FULL, GLOBE_LITE, GLOBE_V2, MODEL_YAW_RAD, cubeFaceTexel, manifestEntry, moonDir, toModelAxes, yawFromAxes, type GlobeManifestEntry, type Vec3 } from '../../src/simple/globeMath';

/**
 * S14 Part B (19 Nov 2026): the S4 globe can draw the POLARIS v2 globe (Anish Meruva) or either NASA SVS model, picked by
 * ?globe=v2 | 8k | svs; with no choice it draws the v2 globe on desktops and phones (Sid's decision, 19 Nov 2026) and the light
 * SVS model on software rendering. Pins, the dropped marker, typed coordinates and the
 * light must land in the same places whichever model is on screen. Expected values come from the files: the manifest, the
 * bundle's site coordinates, and each model's own mesh as the page loaded it.
 */
test.use({ storageState: { cookies: [], origins: [] } });
test.describe.configure({ mode: 'serial' });

const __dirname = dirname(fileURLToPath(import.meta.url));
const globeDir = resolve(__dirname, '../../public/globe');
const has = (f: string) => existsSync(resolve(globeDir, f));
const manifest = has('globe_manifest.json') ? (JSON.parse(readFileSync(resolve(globeDir, 'globe_manifest.json'), 'utf8')) as { globes: GlobeManifestEntry[] }) : null;
const entry = manifestEntry(manifest, GLOBE_V2);
const hasV2 = has(GLOBE_V2) && !!entry;
const bundle = JSON.parse(readFileSync(resolve(__dirname, '../../../data/viewer/polaris-x5d-roi-2026-11-14-v2.json'), 'utf8')) as {
  datasets: { siteId: string; site: { name: string; latitudePlanetocentricDeg: number; longitudeEastDeg: number } }[];
};
const sites = bundle.datasets.map((d) => ({ id: d.siteId, lat: d.site.latitudePlanetocentricDeg, lon: d.site.longitudeEastDeg }));
/** typed points: near the pole (the Check-a-spot placeholder first), mid-latitudes, the equator, the far side, the north */
const typed: [number, number][] = [[-89.5, -137.4], [-85, 45], [-45, 170], [0, 0], [10, 20], [0, 90], [45, -120], [88, 10]];
const points: [number, number][] = [...sites.map((s) => [s.lat, s.lon] as [number, number]), ...typed];
const DEG = 180 / Math.PI;
const sev = (v: { impact?: string | null; id: string; nodes: { target: unknown[] }[] }[]) => v.filter((x) => x.impact === 'serious' || x.impact === 'critical').map((x) => `${x.id}: ${x.nodes.map((n) => n.target.join(' ')).join(', ')}`);

/** the headless test browser renders in software, so the app is on its low tier: what each choice must put on screen there */
const MODELS = [
  { pick: 'v2', file: GLOBE_V2, yaw: () => yawFromAxes(entry!.axes)!, there: hasV2 },
  { pick: '8k', file: GLOBE_8K, yaw: () => MODEL_YAW_RAD[GLOBE_8K], there: has(GLOBE_8K) },
  { pick: 'svs', file: has(GLOBE_LITE) ? GLOBE_LITE : GLOBE_FULL, yaw: () => 0, there: has(GLOBE_FULL) || has(GLOBE_LITE) },
] as const;

async function openGlobe(page: Page, query = '') {
  await page.goto(`/${query}`);
  await expect(page.locator('[data-testid=simple-globe][data-shown=true]')).toBeVisible({ timeout: 60_000 });
  await expect(page.getByTestId('simple-mode')).not.toHaveAttribute('data-intro', /.+/, { timeout: 30_000 });
  await expect(page.getByTestId('spot-box')).toBeVisible();
}
/** hold the slow drift and stand exactly pole-on, so every model is seen from the same place */
const rest = (page: Page) =>
  page.evaluate(() => {
    const n = (window as any).__polarisGlobe.nav;
    n.quietUntil = Number.MAX_VALUE;
    n.vx = n.vy = 0;
    n.home = null;
    n.q.set(0, 0, 0, 1);
    n.zoom = n.zoomNow = 1;
  });

/** a few drawn frames: the software renderer of the test browser can take a while over one, and the page places things per frame */
const frames = (page: Page) => page.evaluate(() => new Promise<void>((r) => requestAnimationFrame(() => requestAnimationFrame(() => requestAnimationFrame(() => requestAnimationFrame(() => r()))))));

interface Hit {
  mesh: number;
  material: string;
  uv: [number, number];
  own: Vec3;
  size: [number, number];
}
/**
 * In the page: for each direction of the app's frame, the point of the Moon model on screen that a ray from the Moon's centre
 * meets (the model as loaded, with the turn, scale and centring the app gave it): which mesh, its texture coordinates there,
 * and that direction in the mesh's own axes.
 */
const probe = (page: Page, dirs: Vec3[]) =>
  page.evaluate((dirs) => {
    const h = (window as any).__polarisGlobe;
    h.scene.updateMatrixWorld(true);
    const meshes: any[] = [];
    h.scene.traverse((o: any) => {
      let shown = true;
      for (let p = o; p; p = p.parent) shown = shown && p.visible;
      if (o.isMesh && shown && o.material?.map && o.geometry.getAttribute('uv')) meshes.push(o);
    });
    const V = h.camera.position.clone();
    const M = meshes[0].matrixWorld.clone();
    return dirs.map((d) => {
      for (let mi = 0; mi < meshes.length; mi++) {
        const o = meshes[mi];
        M.copy(o.matrixWorld).invert();
        const org = V.set(0, 0, 0).applyMatrix4(M).toArray();
        const dir = V.set(d[0], d[1], d[2]).transformDirection(M).toArray();
        const pos = o.geometry.getAttribute('position').array;
        const uv = o.geometry.getAttribute('uv').array;
        const idx = o.geometry.index.array;
        for (let t = 0; t < idx.length; t += 3) {
          const a = idx[t] * 3;
          const ax = pos[a] - org[0];
          const ay = pos[a + 1] - org[1];
          const az = pos[a + 2] - org[2];
          if (ax * dir[0] + ay * dir[1] + az * dir[2] < 0.97 * Math.hypot(ax, ay, az)) continue;
          const b = idx[t + 1] * 3;
          const c = idx[t + 2] * 3;
          const e1 = [pos[b] - pos[a], pos[b + 1] - pos[a + 1], pos[b + 2] - pos[a + 2]];
          const e2 = [pos[c] - pos[a], pos[c + 1] - pos[a + 1], pos[c + 2] - pos[a + 2]];
          const hh = [dir[1] * e2[2] - dir[2] * e2[1], dir[2] * e2[0] - dir[0] * e2[2], dir[0] * e2[1] - dir[1] * e2[0]];
          const det = e1[0] * hh[0] + e1[1] * hh[1] + e1[2] * hh[2];
          if (Math.abs(det) < 1e-18) continue;
          const s = [-ax, -ay, -az];
          const u = (s[0] * hh[0] + s[1] * hh[1] + s[2] * hh[2]) / det;
          if (u < -1e-7 || u > 1 + 1e-7) continue;
          const q = [s[1] * e1[2] - s[2] * e1[1], s[2] * e1[0] - s[0] * e1[2], s[0] * e1[1] - s[1] * e1[0]];
          const v = (dir[0] * q[0] + dir[1] * q[1] + dir[2] * q[2]) / det;
          if (v < -1e-7 || u + v > 1 + 1e-7) continue;
          if ((e2[0] * q[0] + e2[1] * q[1] + e2[2] * q[2]) / det <= 0) continue;
          const w = 1 - u - v;
          const [ia, ib, ic] = [idx[t] * 2, idx[t + 1] * 2, idx[t + 2] * 2];
          const img = o.material.map.image;
          return { mesh: mi, material: o.material.name || o.name, uv: [w * uv[ia] + u * uv[ib] + v * uv[ic], w * uv[ia + 1] + u * uv[ib + 1] + v * uv[ic + 1]], own: dir, size: [img.width, img.height] };
        }
      }
      return null;
    });
  }, dirs) as Promise<(Hit | null)[]>;

/** what the page shows for one model, to be compared across the models once all have been seen */
interface Seen {
  anchors: { x: number; y: number }[];
  marks: string[];
  dropped: { lat: number; lon: number }[];
  lights: number[][];
}
const seen: Record<string, Seen> = {};
/** screen positions clicked on the Moon (CSS px in the 1440 × 900 window): three places on the lit side of the pole-on view */
const CLICKS: [number, number][] = [[560, 420], [640, 560], [500, 640]];

for (const m of MODELS) {
  test(`?globe=${m.pick}: that model is drawn, turned to the app's axes; pins, a dropped point and typed points are recorded`, async ({ page }) => {
    test.skip(!m.there, `${m.pick}: the model is not in web/public/globe on this machine`);
    test.setTimeout(240_000);
    await openGlobe(page, `?globe=${m.pick}`);
    const globe = page.getByTestId('simple-globe');
    if (m.pick === '8k') await expect(globe).toHaveAttribute('data-upgrade-state', 'shown', { timeout: 180_000 });
    await expect(globe).toHaveAttribute('data-asset', m.file);
    await rest(page);
    await frames(page);

    // the model itself: a ray from the centre toward each point meets the mesh at that point of the model's own frame
    const hits = await probe(page, points.map(([la, lo]) => moonDir(la, lo)));
    const yaw = m.yaw();
    let worst = 0;
    points.forEach(([lat, lon], i) => {
      const hit = hits[i];
      expect(hit, `${lat}, ${lon}: on the mesh`).not.toBeNull();
      const want = toModelAxes(moonDir(lat, lon), yaw);
      // the direction in the mesh's own axes is the one its frame gives this latitude and longitude (to 0.0001°)
      const off = Math.acos(Math.min(1, hit!.own[0] * want[0] + hit!.own[1] * want[1] + hit!.own[2] * want[2])) * DEG;
      expect(off, `${lat}, ${lon}: ${off}° off in the model's own axes`).toBeLessThan(1e-4);
      if (m.pick === 'v2') {
        // and the image pixel there is the one the builder gave that latitude and longitude, within one pixel
        const t = cubeFaceTexel(lat, lon, hit!.size[0]);
        expect(hit!.size[0]).toBe(hit!.size[1]);
        expect(hit!.mesh, `${lat}, ${lon}: cube face`).toBe(t.face);
        const err = Math.hypot(hit!.uv[0] * hit!.size[0] - t.x, hit!.uv[1] * hit!.size[1] - t.y);
        worst = Math.max(worst, err);
        expect(err, `${lat}, ${lon}: ${err.toFixed(3)} px from the builder's pixel`).toBeLessThan(1);
      }
    });
    if (m.pick === 'v2') console.log(`v2 globe in the page: worst distance from the builder's pixel = ${worst.toFixed(3)} px`);

    // what the visitor sees, for the comparison below
    const s: Seen = { anchors: [], marks: [], dropped: [], lights: [] };
    s.anchors = await page.evaluate(() => [...document.querySelectorAll('.s-globe-leaders circle')].map((c) => ({ x: Number(c.getAttribute('cx')), y: Number(c.getAttribute('cy')) })));
    s.lights = await page.evaluate(() => {
      const out: number[][] = [];
      (window as any).__polarisGlobe.scene.traverse((o: any) => o.isDirectionalLight && out.push(o.position.toArray().map((v: number) => +v.toFixed(9))));
      return out;
    });
    for (const [x, y] of CLICKS) {
      await page.mouse.click(x, y);
      const a = page.getByTestId('spot-answer');
      await expect(a).toBeAttached({ timeout: 30_000 });
      s.dropped.push({ lat: Number(await a.getAttribute('data-lat')), lon: Number(await a.getAttribute('data-lon')) });
      await page.getByTestId('spot-close').click();
      await expect(page.getByTestId('spot-card')).toHaveCount(0);
    }
    for (const [lat, lon] of typed.slice(0, 3)) {
      await page.getByTestId('spot-lat').fill(String(lat));
      await page.getByTestId('spot-lon').fill(String(lon));
      await page.getByTestId('spot-lon').press('Enter');
      await expect(page.getByTestId('spot-answer')).toHaveAttribute('data-lat', String(lat), { timeout: 30_000 });
      await expect(page.getByTestId('spot-answer')).toHaveAttribute('data-lon', String(lon));
      await rest(page);
      await frames(page);
      s.marks.push(await page.getByTestId('spot-mark').evaluate((el) => `${(el as HTMLElement).style.visibility}|${(el as HTMLElement).style.transform}`));
      await page.getByTestId('spot-close').click();
      await expect(page.getByTestId('spot-card')).toHaveCount(0);
    }
    expect(s.anchors).toHaveLength(sites.length);
    seen[m.pick] = s;
  });
}

test('pins, the dropped marker, typed coordinates and the light are in the same places on every model', () => {
  const picks = Object.keys(seen);
  test.skip(picks.length < 2, 'fewer than two models on this machine');
  const base = seen[picks[0]];
  for (const p of picks.slice(1)) {
    const s = seen[p];
    // pin lines end at the same screen point (the page writes them to a tenth of a pixel)
    s.anchors.forEach((a, i) => {
      expect(a.x, `${p}: pin ${i} x`).toBe(base.anchors[i].x);
      expect(a.y, `${p}: pin ${i} y`).toBe(base.anchors[i].y);
    });
    // a click at the same screen position drops the same latitude and longitude
    expect(s.dropped).toEqual(base.dropped);
    // typed coordinates put the marker at the same screen position
    expect(s.marks).toEqual(base.marks);
    // the Sun and earthshine lights (the terminator) come from the same directions
    expect(s.lights).toEqual(base.lights);
  }
  expect(base.lights.length).toBeGreaterThan(0);
  for (const m of base.marks) expect(m).toMatch(/^\|translate\(/);
});

test('About this view: with the v2 globe on screen, its labels and credit are the manifest’s own words', async ({ page }) => {
  test.skip(!hasV2, 'the v2 globe is not in web/public/globe on this machine');
  await openGlobe(page, '?globe=v2');
  await expect(page.getByTestId('simple-globe')).toHaveAttribute('data-asset', GLOBE_V2);
  await page.getByTestId('globe-about').locator('summary').click();
  const about = page.getByTestId('globe-about');
  await expect(about).toContainText('Globe: POLARIS v2 (Anish Meruva)');
  await expect(about).toContainText(`built by ${entry!.builder}`);
  await expect(about).toContainText(`Heights: ${entry!.labels!.heights}`);
  expect(entry!.labels!.heights).toContain('SOURCE-BASED · UNVALIDATED');
  await expect(about).toContainText(entry!.labels!.webBaseColour);
  expect(entry!.labels!.webBaseColour).toMatch(/^VISUAL base colour/);
  await expect(about).toContainText(`Credit: ${entry!.textureCredit}`);
  expect(entry!.textureCredit).toContain('LROC WAC');
  // the light is still the bundle's Sun, and the baked shadows are named as not ours
  await expect(about).toContainText('Light: the Sun direction in the bundle at');
  await expect(about).toContainText('they are not cast by the Sun shown here');
  await expect(about).not.toContainText('NASA SVS');
  await page.waitForTimeout(300);
  expect(sev((await new AxeBuilder({ page }).analyze()).violations)).toEqual([]);
});

/**
 * The test browser renders in software (SwiftShader), where the light SVS model stays the default. To see what a desktop or
 * a phone with a GPU gets, the page is told a GPU's name (WEBGL_debug_renderer_info only; the drawing is still SwiftShader)
 * and ?quality=low keeps the post chain off, as on a phone.
 */
const asGpu = (page: Page, name: string) =>
  page.addInitScript((name) => {
    for (const C of [WebGLRenderingContext, WebGL2RenderingContext]) {
      const get = C.prototype.getParameter;
      C.prototype.getParameter = function (p: number) {
        return p === 0x9246 ? name : get.call(this, p); // UNMASKED_RENDERER_WEBGL
      };
    }
  }, name);

for (const [label, w, h, gpu] of [
  ['desktop', 1440, 900, 'ANGLE (Apple, ANGLE Metal Renderer: Apple M4 Pro, Unspecified Version)'],
  ['phone', 390, 844, 'Apple GPU'],
] as const) {
  test(`with no ?globe= a ${label} with a GPU draws the v2 globe, nothing after it, About is the manifest’s, and no 8k bytes are fetched`, async ({ page }) => {
    test.skip(!hasV2, 'the v2 globe is not in web/public/globe on this machine');
    test.setTimeout(120_000);
    const asked: string[] = [];
    page.on('request', (r) => asked.push(new URL(r.url()).pathname));
    await asGpu(page, gpu);
    await page.setViewportSize({ width: w, height: h });
    await openGlobe(page, '?quality=low');
    const g = page.getByTestId('simple-globe');
    await expect(g).toHaveAttribute('data-asset', GLOBE_V2);
    await expect(g).not.toHaveAttribute('data-upgrade', /.+/);
    expect(await g.getAttribute('data-upgrade-state')).toBeNull();
    await page.getByTestId('globe-about').locator('summary').click();
    await expect(page.getByTestId('globe-about')).toContainText('Globe: POLARIS v2 (Anish Meruva)');
    await expect(page.getByTestId('globe-about')).toContainText('Quality: low (camera effects off)');
    await expect(page.getByTestId('globe-about')).not.toContainText('lighter Moon image');
    await page.waitForTimeout(300);
    expect(sev((await new AxeBuilder({ page }).analyze()).violations)).toEqual([]);
    await page.waitForTimeout(1500);
    expect(asked.filter((p) => p.endsWith('.glb'))).toEqual([`/globe/${GLOBE_V2}`]);
    expect(asked.some((p) => p.includes(GLOBE_8K))).toBe(false);
  });
}

test('software rendering (the test browser, no GPU) keeps the light SVS model by default and never fetches the v2 or 8k model', async ({ page }) => {
  const asked: string[] = [];
  page.on('request', (r) => asked.push(new URL(r.url()).pathname));
  await openGlobe(page);
  const want = has(GLOBE_LITE) ? GLOBE_LITE : GLOBE_FULL;
  await expect(page.getByTestId('simple-globe')).toHaveAttribute('data-asset', want);
  await page.getByTestId('globe-about').locator('summary').click();
  await expect(page.getByTestId('globe-about')).toContainText('Moon: NASA SVS / LRO compact model (SVS 14959)');
  await expect(page.getByTestId('globe-about')).not.toContainText('Globe: POLARIS v2');
  await page.waitForTimeout(1500);
  expect(asked.filter((p) => p.endsWith('.glb'))).toEqual([`/globe/${want}`]);
  expect(asked.some((p) => p.includes('/draco/'))).toBe(false);
});

test('if the default v2 globe cannot be loaded, the light SVS model takes its place (no empty view, no 8k download)', async ({ page }) => {
  test.skip(!hasV2, 'the v2 globe is not in web/public/globe on this machine');
  const asked: string[] = [];
  page.on('request', (r) => asked.push(new URL(r.url()).pathname));
  await page.route(`**/globe/${GLOBE_V2}`, (route) => route.abort());
  await asGpu(page, 'ANGLE (Apple, ANGLE Metal Renderer: Apple M4 Pro, Unspecified Version)');
  await openGlobe(page, '?quality=low');
  const g = page.getByTestId('simple-globe');
  const want = has(GLOBE_LITE) ? GLOBE_LITE : GLOBE_FULL;
  await expect(g).toHaveAttribute('data-asset', want);
  await expect(g).toHaveAttribute('data-state', 'ready');
  await expect(g).toHaveAttribute('data-fallback-from', GLOBE_V2);
  await page.getByTestId('globe-about').locator('summary').click();
  await expect(page.getByTestId('globe-about')).toContainText('Moon: NASA SVS / LRO compact model (SVS 14959)');
  expect(asked.some((p) => p.includes(GLOBE_8K))).toBe(false);
});

test('a ?globe= value that names no model changes nothing: the default for the device', async ({ page }) => {
  test.skip(!hasV2, 'the v2 globe is not in web/public/globe on this machine');
  await asGpu(page, 'ANGLE (Apple, ANGLE Metal Renderer: Apple M4 Pro, Unspecified Version)');
  await openGlobe(page, '?quality=low&globe=nonsense');
  await expect(page.getByTestId('simple-globe')).toHaveAttribute('data-asset', GLOBE_V2);
});
