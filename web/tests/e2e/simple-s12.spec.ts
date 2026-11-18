import { test, expect, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

/**
 * S12 (18 Nov 2026): the Moon is moved by hand on the globe, and the site scene is clickable. Expected card values are read
 * here from the ROI bundle and the certainty sidecar, never typed in. CI draws with software rendering (low tier); how it
 * looks is checked on the Mac (web/scripts/s12_shots.mjs, tmp/s12).
 */
test.use({ storageState: { cookies: [], origins: [] } });

const __dirname = dirname(fileURLToPath(import.meta.url));
type Eph = { time: string; sun: { az: number; el: number }; earth: { az: number; el: number } };
type Series = { visible: (boolean | null)[]; horizonElDeg: number[]; marginDeg: number[] };
type RawRidge = { id: string; dist_range_km: [number, number]; az_span_deg: [number, number]; relief_m: number; sun_loss_h: number; earth_loss_h: number; of_record: boolean };
type RawDataset = {
  siteId: string;
  site: { name: string };
  dem: { validCoverageRadiusM: number };
  ephemeris: { samples: Eph[] };
  derived: { scenarios: { id: string; observer: { mastM: number }; samples?: { sun: Series; earth: Series } }[]; attribution: { ridges: RawRidge[] } };
};
const bundle = JSON.parse(readFileSync(resolve(__dirname, '../../../data/viewer/polaris-x5d-roi-2026-11-14-v2.json'), 'utf8')) as { datasets: RawDataset[] };
const sidecar = JSON.parse(readFileSync(resolve(__dirname, '../../public/certainty/sidecar.json'), 'utf8')) as { sites: Record<string, { sampled_masts_m: number[] }> };
const STORY = 'site04_roi3'; // the site Simple mode starts on (store/siteDefaults.ts)
const ds = bundle.datasets.find((d) => d.siteId === STORY)!;
const baseline = ds.derived.scenarios.find((s) => s.samples)!;
const ridges = ds.derived.attribution.ridges.filter((r) => r.of_record);
const signed = (x: number, unit = '°') => `${x > 0 ? '+' : x < 0 ? '−' : ''}${Math.abs(x).toFixed(2)}${unit}`;

const globeDir = resolve(__dirname, '../../public/globe');
const hasGlobe = existsSync(globeDir) && readdirSync(globeDir).some((f) => f.endsWith('.glb'));

type GlobeHook = { camera: { position: { x: number; y: number; z: number; length(): number } }; nav: { zoom: number; zoomNow: number; zoomMin: number; vx: number; vy: number; q: { toArray(): number[] } } };
type SceneHook = { camera: { position: { toArray(): number[] }; fov: number; view: { enabled: boolean } | null }; controls: { target: { toArray(): number[] } }; screen(id: string): { x: number; y: number; front: boolean } | null };

async function openGlobe(page: Page) {
  await page.goto('/');
  await expect(page.locator('[data-testid=simple-globe][data-shown=true]')).toBeVisible({ timeout: 45_000 });
  await expect(page.getByTestId('simple-mode')).not.toHaveAttribute('data-intro', /.+/, { timeout: 30_000 });
  await expect(page.getByTestId(`globe-pin-${STORY}`)).toBeVisible();
}
/** unit vector from the Moon's centre to the camera, and the camera's distance */
const camDir = (page: Page) =>
  page.evaluate(() => {
    const c = (window as unknown as { __polarisGlobe: GlobeHook }).__polarisGlobe.camera.position;
    const l = c.length();
    return [c.x / l, c.y / l, c.z / l, l];
  });
const nav = (page: Page) =>
  page.evaluate(() => {
    const n = (window as unknown as { __polarisGlobe: GlobeHook }).__polarisGlobe.nav;
    return { zoom: n.zoom, zoomNow: n.zoomNow, zoomMin: n.zoomMin, v: Math.hypot(n.vx, n.vy), q: n.q.toArray() };
  });
/** how far two orientations are apart (largest difference of a component): 0 = the same */
const turn = (a: number[], b: number[]) => Math.max(...a.map((x, i) => Math.abs(x - b[i])));
const STILL = 1e-12;
/** a point of the Moon's disc clear of the card and the pins */
async function moonPoint(page: Page) {
  const v = (await page.locator('.s-globe-view').boundingBox())!;
  const wide = page.viewportSize()!.width >= 1024;
  return { x: v.x + v.width * (wide ? 0.72 : 0.5), y: v.y + v.height * 0.3 };
}

test.describe('the globe, moved by hand', () => {
  test.skip(!hasGlobe, 'no Moon model in web/public/globe (git-ignored NASA asset)');

  test('a drag turns the Moon and does not fly anywhere; a plain click on a pin still flies', async ({ page }) => {
    await openGlobe(page);
    const home = await camDir(page);
    expect(home[1]).toBeCloseTo(-1, 6); // over the south pole
    const pinBox = (await page.getByTestId(`globe-pin-${STORY}`).getByRole('button').boundingBox())!;
    const end = { x: pinBox.x + pinBox.width / 2, y: pinBox.y + pinBox.height / 2 };
    await page.mouse.move(end.x + 170, end.y - 90);
    await page.mouse.down();
    await page.mouse.move(end.x + 80, end.y - 40, { steps: 6 });
    await expect(page.getByTestId('simple-globe')).toHaveAttribute('data-dragging', 'true');
    await page.mouse.move(end.x, end.y, { steps: 6 });
    await page.mouse.up();
    await expect(page.getByTestId('simple-globe')).not.toHaveAttribute('data-dragging', 'true');
    // the camera is no longer over the pole, and the visitor is still on the globe
    await expect.poll(async () => (await camDir(page))[1]).toBeGreaterThan(-0.9999);
    await page.waitForTimeout(600);
    await expect(page.getByTestId('simple-mode')).toHaveAttribute('data-place', 'globe');
    await expect(page.getByTestId('scene3d')).toHaveCount(0);
    // a plain click on a pin still flies
    await page.getByTestId('globe-home').click();
    await expect(page.getByTestId('simple-globe')).not.toHaveAttribute('data-moved', 'true', { timeout: 5000 });
    await page.getByTestId(`globe-pin-${STORY}`).getByRole('button').click();
    await expect(page.getByTestId('simple-mode')).toHaveAttribute('data-place', /in|site/, { timeout: 5000 });
  });

  test('a drag that starts on a pin and is let go over that pin turns the Moon and is not a press of it', async ({ page }) => {
    await openGlobe(page);
    const b = (await page.getByTestId(`globe-pin-${STORY}`).getByRole('button').boundingBox())!;
    await page.mouse.move(b.x + b.width / 2, b.y + b.height / 2);
    await page.mouse.down();
    await page.mouse.move(b.x + b.width / 2 + 60, b.y + b.height / 2 + 30, { steps: 8 });
    // the pin travels with the surface, so the pointer is still over it when it is let go
    const end = { x: b.x + b.width / 2 + 60, y: b.y + b.height / 2 + 30 };
    const now = (await page.getByTestId(`globe-pin-${STORY}`).getByRole('button').boundingBox())!;
    expect(end.x > now.x && end.x < now.x + now.width && end.y > now.y && end.y < now.y + now.height, 'released over the pin').toBe(true);
    await page.mouse.up();
    await page.waitForTimeout(500);
    await expect(page.getByTestId('simple-mode')).toHaveAttribute('data-place', 'globe');
    await expect(page.getByTestId('simple-globe')).toHaveAttribute('data-moved', 'true');
  });

  test('the wheel zooms between the whole Moon and the limit of the Moon image on screen', async ({ page }) => {
    await openGlobe(page);
    const p = await moonPoint(page);
    await page.mouse.move(p.x, p.y);
    const far = (await camDir(page))[3];
    for (let i = 0; i < 40; i++) await page.mouse.wheel(0, -200);
    const n = await nav(page);
    expect(n.zoomMin).toBeGreaterThan(0);
    expect(n.zoomMin).toBeLessThan(1);
    expect(n.zoom).toBe(n.zoomMin); // stopped at the model's limit, not beyond
    await expect.poll(async () => (await nav(page)).zoomNow).toBeCloseTo(n.zoomMin, 3);
    expect((await camDir(page))[3]).toBeLessThan(far);
    // the page itself did not zoom or scroll
    expect(await page.evaluate(() => [window.scrollY, window.visualViewport?.scale ?? 1])).toEqual([0, 1]);
    for (let i = 0; i < 60; i++) await page.mouse.wheel(0, 200);
    expect((await nav(page)).zoom).toBe(1); // never farther out than the whole Moon
    await expect.poll(async () => (await camDir(page))[3]).toBeCloseTo(far, 3);
  });

  test('"Back to south pole" appears once the view has moved and returns it to the sites', async ({ page }) => {
    await openGlobe(page);
    await expect(page.getByTestId('globe-home')).toHaveCount(0);
    await expect(page.getByTestId('globe-hint')).toBeVisible();
    const p = await moonPoint(page);
    await page.mouse.move(p.x, p.y);
    await page.mouse.down();
    await page.mouse.move(p.x - 240, p.y + 120, { steps: 10 });
    await page.mouse.up();
    await expect(page.getByTestId('globe-home')).toBeVisible();
    await expect(page.getByTestId('globe-home')).toHaveText('Back to south pole');
    await expect(page.getByTestId('globe-hint')).toHaveCount(0);
    await page.getByTestId('globe-home').click();
    await expect(page.getByTestId('globe-home')).toHaveCount(0, { timeout: 5000 });
    const back = await camDir(page);
    expect(back[1]).toBeLessThan(-0.99996); // within MOVED_DEG of the pole
    await expect.poll(async () => (await camDir(page))[1], { timeout: 5000 }).toBeCloseTo(-1, 6);
    await expect(page.getByTestId(`globe-pin-${STORY}`)).toBeVisible();
  });

  test('keyboard: the Moon takes focus with a visible ring; arrows turn it, + and − zoom, Home returns', async ({ page }) => {
    await openGlobe(page);
    const pad = page.getByTestId('globe-pad');
    await expect(pad).toHaveAccessibleName(/Arrow keys turn it, plus and minus zoom/);
    // reached by Tab, just before the site pins
    await page.getByTestId('globe-card').click({ position: { x: 5, y: 5 } });
    let reached = false;
    for (let i = 0; i < 12 && !reached; i++) {
      await page.keyboard.press('Tab');
      reached = await pad.evaluate((el) => el === document.activeElement);
    }
    expect(reached).toBe(true);
    expect(await pad.evaluate((el) => [getComputedStyle(el).outlineStyle, getComputedStyle(el).outlineWidth])).toEqual(['solid', '2px']);
    const start = await camDir(page);
    await page.keyboard.press('ArrowRight');
    await expect.poll(async () => Math.abs((await camDir(page))[1] - start[1])).toBeGreaterThan(1e-4);
    const turned = await camDir(page);
    await page.keyboard.press('ArrowUp');
    await expect.poll(async () => Math.hypot(...(await camDir(page)).slice(0, 3).map((x, i) => x - turned[i]))).toBeGreaterThan(1e-3);
    await page.keyboard.press('+');
    await expect.poll(async () => (await camDir(page))[3]).toBeLessThan(start[3] - 0.05);
    await page.keyboard.press('-');
    await expect.poll(async () => (await camDir(page))[3]).toBeCloseTo(start[3], 2);
    await expect(page.getByTestId('globe-home')).toBeVisible();
    // focus stays on the Moon through all of it
    await expect(pad).toBeFocused();
    await page.keyboard.press('Home');
    await expect(page.getByTestId('globe-home')).toHaveCount(0, { timeout: 5000 });
    await expect(pad).toBeFocused();
    // the button too is reachable, and hands focus back to the Moon when it goes
    await page.keyboard.press('ArrowLeft');
    await expect(page.getByTestId('globe-home')).toBeVisible();
    await page.getByTestId('globe-home').focus();
    await page.keyboard.press('Enter');
    await expect(page.getByTestId('globe-home')).toHaveCount(0, { timeout: 5000 });
    await expect(pad).toBeFocused();
  });

  test('the slow drift stops while the Moon is held and for a few seconds after, then resumes', async ({ page }) => {
    test.slow();
    await openGlobe(page);
    const p = await moonPoint(page);
    await page.mouse.move(p.x, p.y);
    await page.mouse.down();
    await page.mouse.move(p.x + 40, p.y + 10, { steps: 4 });
    // held still: nothing turns under the pointer (once the frame that applies the last of the drag has drawn)
    await page.waitForFunction(() => {
      const n = (window as unknown as { __polarisGlobe: { nav: { dx: number; dy: number; dragging: boolean } } }).__polarisGlobe.nav;
      return n.dragging && n.dx === 0 && n.dy === 0;
    });
    await page.waitForTimeout(400);
    const held = (await nav(page)).q;
    await page.waitForTimeout(700);
    expect(turn((await nav(page)).q, held)).toBeLessThan(STILL);
    await page.mouse.up();
    // released from rest: no glide, and no drift yet
    expect((await nav(page)).v).toBe(0);
    await page.waitForTimeout(1500);
    expect(turn((await nav(page)).q, held)).toBeLessThan(STILL);
    // a few seconds later the drift is back
    await expect.poll(async () => turn((await nav(page)).q, held), { timeout: 30_000, intervals: [500] }).toBeGreaterThan(1e-6);
  });

  test('a flick glides on after release; under reduced motion it stops where it was let go', async ({ page }) => {
    for (const reduce of [false, true]) {
      await page.emulateMedia({ reducedMotion: reduce ? 'reduce' : 'no-preference' });
      await openGlobe(page);
      const p = await moonPoint(page);
      await page.mouse.move(p.x, p.y);
      await page.mouse.down();
      // a quick, steady sweep, let go while moving. The events are made inside the page, 8 ms apart, so their times do not
      // depend on how fast the test harness delivers them (a real pointer's do not either).
      await page.mouse.up();
      await page.evaluate(([x0, y0]) => {
        const el = document.querySelector('.s-globe-view')!;
        const ev = (type: string, x: number, y: number) => el.dispatchEvent(new PointerEvent(type, { bubbles: true, pointerId: 77, pointerType: 'mouse', isPrimary: true, button: 0, buttons: type === 'pointerup' ? 0 : 1, clientX: x, clientY: y }));
        const wait = (ms: number) => {
          const t = performance.now();
          while (performance.now() - t < ms);
        };
        ev('pointerdown', x0, y0);
        for (let i = 1; i <= 8; i++) {
          wait(8);
          ev('pointermove', x0 - i * 22, y0 + i * 6);
        }
        ev('pointerup', x0 - 8 * 22, y0 + 8 * 6);
      }, [p.x, p.y]);
      // (once the frame after the release has drawn: the last of the drag is applied there)
      await page.waitForFunction(() => {
        const n = (window as unknown as { __polarisGlobe: { nav: { dx: number; dy: number } } }).__polarisGlobe.nav;
        return n.dx === 0 && n.dy === 0;
      });
      const at = (await nav(page)).q;
      if (reduce) {
        await page.waitForTimeout(500);
        const after = await nav(page);
        expect(after.v, 'no glide under reduced motion').toBe(0);
        expect(turn(after.q, at)).toBeLessThan(STILL);
        // "Back to south pole" is a cut
        await page.getByTestId('globe-home').click();
        await expect(page.getByTestId('globe-home')).toHaveCount(0, { timeout: 400 });
      } else {
        await expect.poll(async () => turn((await nav(page)).q, at), { timeout: 3000, intervals: [50] }).toBeGreaterThan(1e-6);
        // and it dies away
        await expect.poll(async () => (await nav(page)).v, { timeout: 8000 }).toBe(0);
      }
    }
  });

  test('axe: the globe with the view moved has no serious or critical issues', async ({ page }) => {
    await openGlobe(page);
    await page.getByTestId('globe-pad').focus();
    await page.keyboard.press('ArrowRight');
    await expect(page.getByTestId('globe-home')).toBeVisible();
    await page.waitForTimeout(500);
    const { violations } = await new AxeBuilder({ page }).analyze();
    expect(violations.filter((v) => v.impact === 'serious' || v.impact === 'critical').map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`)).toEqual([]);
  });

  test.describe('390 × 844', () => {
    test.use({ viewport: { width: 390, height: 844 } });
    test('axe: the globe with the view moved has no serious or critical issues on a phone', async ({ page }) => {
      await openGlobe(page);
      await page.getByTestId('globe-pad').focus();
      await page.keyboard.press('ArrowRight');
      await expect(page.getByTestId('globe-home')).toBeVisible();
      await page.waitForTimeout(500);
      const { violations } = await new AxeBuilder({ page }).analyze();
      expect(violations.filter((v) => v.impact === 'serious' || v.impact === 'critical').map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`)).toEqual([]);
    });
  });
});

/* ---------- the clickable site scene ---------- */

async function openSite(page: Page) {
  await page.goto('/?view=terrain');
  await expect(page.getByTestId('plain-answer')).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId('scene3d')).toBeVisible({ timeout: 30_000 });
  await page.waitForFunction(() => !!(window as unknown as { __polarisScene?: unknown }).__polarisScene, null, { timeout: 30_000 });
  await expect(page.locator('[data-testid=scene3d]:is([data-context=loaded], [data-context=none])')).toBeVisible();
  // the view eases to its Approach framing on arrival: start once the camera is at rest
  await atRest(page);
}
const camera = (page: Page) =>
  page.evaluate(() => {
    const s = (window as unknown as { __polarisScene: SceneHook }).__polarisScene;
    return [...s.camera.position.toArray(), ...s.controls.target.toArray(), s.camera.fov, s.camera.view?.enabled ? 1 : 0];
  });
/** the same camera, to within float rounding: the orbit controls re-derive the position every frame, which can move the last bits */
const sameCamera = (a: number[], b: number[]) => Math.max(...a.map((x, i) => Math.abs(x - b[i])));
const EXACT = 1e-9; // metres (and degrees of lens): a billionth
/** waits until the camera has stopped (arrival ease, orbit damping) and returns it */
async function atRest(page: Page, tol = EXACT) {
  let last: number[] = [];
  let still = 0;
  // unchanged over four looks in a row (1.2 s): a pause before a move begins is shorter than that
  await expect
    .poll(async () => {
      const now = await camera(page);
      still = last.length > 0 && sameCamera(now, last) < tol ? still + 1 : 0;
      last = now;
      return still >= 3;
    }, { intervals: [400], timeout: 60_000 })
    .toBe(true);
  return last;
}
const settled = (page: Page) => expect(page.getByTestId('simple-mode')).not.toHaveAttribute('data-fly', /.+/, { timeout: 10_000 });
const fact = (page: Page, key: string) => page.locator(`[data-testid=scene-card] [data-fact="${key}"]`);
/** index of the bundle sample on the clock */
const sampleIdx = async (page: Page) => Number((await page.getByTestId('sample-pos').innerText()).match(/(\d+)\s*\/\s*\d+/)![1]) - 1;
/** where an object stands on the page, and what interface element (if any) lies over that point */
const whereIs = (page: Page, id: string) =>
  page.evaluate((i) => {
    const a = (window as unknown as { __polarisScene: SceneHook }).__polarisScene.screen(i)!;
    const st = document.querySelector('.simple-stage canvas')!.getBoundingClientRect();
    const p = { x: st.left + a.x, y: st.top + a.y };
    const over = [...document.querySelectorAll('.s-cardslot .s-objcard, .s-answerpanel, .s-statspanel, .s-dock, .s-bottom, .s-chrome')].filter((el) => {
      const r = el.getBoundingClientRect();
      return r.width > 0 && p.x >= r.left && p.x <= r.right && p.y >= r.top && p.y <= r.bottom;
    });
    return { ...p, front: a.front, covered: over.map((el) => el.className) };
  }, id);

test('every clickable object is also a button with a name; Tab moves along them', async ({ page }) => {
  await openSite(page);
  const list = page.getByTestId('scene-objects');
  await expect(list).toHaveAccessibleName('Things to look at in this view');
  const ids = ['site', 'sun', 'earth', ...ridges.map((r) => `ridge:${r.id}`)];
  await expect(list.getByRole('button')).toHaveCount(ids.length);
  await expect(page.getByTestId('scene-object-site')).toHaveAccessibleName(/^Landing site and mast\./);
  await expect(page.getByTestId('scene-object-sun')).toHaveAccessibleName(/^Sun\. Fly to it/);
  await expect(page.getByTestId('scene-object-earth')).toHaveAccessibleName(/^Earth\. Fly to it/);
  for (const r of ridges) {
    const what = [r.sun_loss_h > 0 ? 'the Sun' : null, r.earth_loss_h > 0 ? 'the Earth' : null].filter(Boolean).join(' and ');
    await expect(page.getByTestId(`scene-object-ridge:${r.id}`)).toHaveAccessibleName(`Ridge ${r.id}, which blocks ${what}. Fly to it and open its details.`);
  }
  await page.getByTestId('scene-object-site').focus();
  for (const id of ids.slice(1)) {
    await page.keyboard.press('Tab');
    await expect(page.getByTestId(`scene-object-${id}`)).toBeFocused();
  }
  expect(await page.getByTestId(`scene-object-${ids[ids.length - 1]}`).evaluate((el) => [getComputedStyle(el).outlineStyle, getComputedStyle(el).outlineWidth])).toEqual(['solid', '2px']);
});

for (const key of ['sun', 'earth'] as const) {
  test(`${key} card: azimuth, elevation, margin and visible or blocked equal the bundle sample; Esc returns the camera exactly`, async ({ page }) => {
    await openSite(page);
    const i = await sampleIdx(page);
    const e = ds.ephemeris.samples[i][key];
    const s = baseline.samples![key];
    const home = await camera(page);
    await page.getByTestId(`scene-object-${key}`).focus();
    await page.keyboard.press('Enter');
    const card = page.getByTestId('scene-card');
    await expect(card).toBeVisible();
    await expect(card.getByRole('heading', { level: 1 })).toHaveText(key === 'sun' ? 'Sun' : 'Earth');
    await expect(card).toContainText(`Seen from the top of the ${baseline.observer.mastM} m mast`);
    await expect(fact(page, 'azimuth').locator('.s-fact-value')).toHaveText(`${e.az.toFixed(1)}°`);
    await expect(fact(page, 'elevation').locator('.s-fact-value')).toHaveText(signed(e.el));
    await expect(fact(page, 'margin').locator('.s-fact-value')).toHaveText(signed(s.marginDeg[i]));
    await expect(fact(page, 'margin').locator('.s-fact-sub')).toHaveText(`skyline at ${signed(s.horizonElDeg[i])}`);
    await expect(fact(page, 'state').locator('.s-fact-value')).toHaveText(s.visible[i] ? 'In view' : 'Blocked');
    await expect(fact(page, 'time').locator('.s-fact-value')).toHaveText(ds.ephemeris.samples[i].time.replace('T', ' ').replace(/:00\.000Z$/, ' UTC'));
    await expect(fact(page, 'time').locator('.s-fact-sub')).toHaveText('a bundle sample');
    await expect(card).toContainText('SOURCE-BASED · UNVALIDATED');
    await expect(card).toContainText(key === 'sun' ? 'Not solar power.' : 'Not a radio link.');
    // read out: the name and every value
    const said = await page.getByTestId('scene-announce').innerText();
    for (const t of [key === 'sun' ? 'Sun.' : 'Earth.', `${e.az.toFixed(1)}°`, signed(e.el), signed(s.marginDeg[i])]) expect(said).toContain(t);
    // keyboard: focus came into the card
    await expect(page.getByTestId('scene-card-back')).toBeFocused();
    await settled(page);
    expect(sameCamera((await camera(page)).slice(0, 6), home.slice(0, 6)), 'the camera itself moved').toBeGreaterThan(1);
    // the object is in the picture and not under a panel or its own card
    const at = await whereIs(page, key);
    expect(at.front).toBe(true);
    expect(at.covered, `${key} is clear of the interface`).toEqual([]);
    const vp = page.viewportSize()!;
    expect(at.x > 0 && at.x < vp.width && at.y > 0 && at.y < vp.height).toBe(true);
    await page.keyboard.press('Escape');
    await expect(card).toHaveCount(0);
    await settled(page);
    expect(sameCamera(await camera(page), home), 'the camera is back on the numbers it left').toBeLessThan(EXACT);
    await expect(page.getByTestId('simple-mode')).toHaveAttribute('data-place', 'site'); // Esc closed the card, it did not leave the site
    await expect(page.getByTestId(`scene-object-${key}`)).toBeFocused();
  });
}

test('ridge cards: ID, distance, bearing range, height against the site and hours blocked equal the bundle attribution; Back returns the camera exactly', async ({ page }) => {
  test.slow();
  await openSite(page);
  expect(ridges.length).toBeGreaterThan(0);
  const home = await camera(page);
  for (const r of ridges) {
    const [d0, d1] = r.dist_range_km.map((x) => x * 1000);
    const far = d0 > ds.dem.validCoverageRadiusM;
    await page.getByTestId(`scene-object-ridge:${r.id}`).click();
    const card = page.getByTestId('scene-card');
    await expect(card.getByRole('heading', { level: 1 })).toHaveText(`Ridge ${r.id}`);
    const dist = d1 >= 1000 ? `${(d0 / 1000).toFixed(d1 >= 10000 ? 1 : 2)}–${(d1 / 1000).toFixed(d1 >= 10000 ? 1 : 2)} km` : d0 === d1 ? `${d0.toFixed(0)} m` : `${d0.toFixed(0)}–${d1.toFixed(0)} m`;
    await expect(fact(page, 'distance').locator('.s-fact-value')).toHaveText(dist);
    await expect(fact(page, 'bearing').locator('.s-fact-value')).toHaveText(`${r.az_span_deg[0].toFixed(1)}–${r.az_span_deg[1].toFixed(1)}°`);
    const abs = Math.abs(r.relief_m) < 100 ? Math.abs(r.relief_m).toFixed(2) : Math.round(Math.abs(r.relief_m)).toLocaleString('en-US');
    await expect(fact(page, 'height').locator('.s-fact-value')).toHaveText(`${r.relief_m > 0 ? '+' : r.relief_m < 0 ? '−' : ''}${abs} m`);
    await expect(fact(page, 'sun-hours').locator('.s-fact-value')).toHaveText(`${r.sun_loss_h} h`);
    await expect(fact(page, 'earth-hours').locator('.s-fact-value')).toHaveText(`${r.earth_loss_h} h`);
    await expect(fact(page, 'sun-hours').locator('.s-fact-sub')).toHaveText(`of the window's ${ds.ephemeris.samples.length} hourly samples`);
    // a ridge beyond the terrain crop is described, and says it is not drawn
    await expect(card).toContainText(far ? 'beyond the terrain drawn here' : 'on the terrain drawn here');
    if (far) await expect(card).toContainText('the ridge itself is not drawn');
    await settled(page);
    const at = await whereIs(page, `ridge:${r.id}`);
    expect(at.covered, `ridge ${r.id} is clear of the interface`).toEqual([]);
    // going from one ridge to the next keeps the first framing as the one to return to
  }
  await page.getByTestId('scene-card-back').click();
  await expect(page.getByTestId('scene-card')).toHaveCount(0);
  await settled(page);
  expect(sameCamera(await camera(page), home), 'the camera is back on the numbers it left').toBeLessThan(EXACT);
});

test('hover: the mast gets a pointer cursor and a one-line label; a click flies there and opens the answer; a drag does not', async ({ page }) => {
  test.slow();
  await openSite(page);
  const home = await camera(page);
  const at = await whereIs(page, 'site');
  expect(at.covered).toEqual([]);
  const canvas = page.locator('.simple-stage canvas').first();
  const label = page.getByTestId('scene-hover-label').locator('.s-hoverlabel');
  await expect(label).toHaveAttribute('data-visible', 'false');
  await page.mouse.move(at.x - 4, at.y - 4);
  await page.mouse.move(at.x, at.y, { steps: 3 });
  await expect(label).toHaveAttribute('data-visible', 'true');
  await expect(label).toHaveText('Landing site and mastClick for the answer');
  await expect(canvas).toHaveCSS('cursor', 'pointer');
  // the label stands beside the pointer, not on it
  const lb = (await label.boundingBox())!;
  expect(lb.x > at.x || lb.x + lb.width < at.x).toBe(true);
  // off the object the label and the cursor go
  await page.mouse.move(at.x + 90, at.y - 220);
  await expect(label).toHaveAttribute('data-visible', 'false');
  await expect(canvas).not.toHaveCSS('cursor', 'pointer');
  // The visitor's own framing is the one to come back to, not a preset. (Set here directly rather than by an orbit drag:
  // the orbit controls glide on for many seconds at software-rendering speed, and this must start from rest.)
  await page.evaluate(() => {
    const sc = (window as unknown as { __polarisScene: { camera: { position: { x: number; y: number } }; controls: { update(): void } } }).__polarisScene;
    sc.camera.position.x += 35;
    sc.camera.position.y += 20;
    sc.controls.update();
  });
  const own = await atRest(page, 1e-3);
  expect(sameCamera(own, home)).toBeGreaterThan(5);
  const mast = await whereIs(page, 'site');
  await page.mouse.click(mast.x, mast.y);
  await expect(page.getByTestId('simple-mode')).toHaveAttribute('data-focus', 'site');
  await expect(page.getByTestId('site-card')).toHaveAttribute('data-flown', 'true');
  await expect(page.getByTestId('plain-answer')).toBeVisible();
  await settled(page);
  await page.getByTestId('site-card-back').click();
  await settled(page);
  const back = await camera(page);
  expect(sameCamera(back, own), 'back to the framing the visitor had made').toBeLessThan(0.05);
  expect(sameCamera(back, home), 'not to a preset').toBeGreaterThan(5);
  // a drag that starts on the mast orbits the view and opens nothing
  const here = await whereIs(page, 'site');
  await page.mouse.move(here.x, here.y);
  await page.mouse.down();
  await page.mouse.move(here.x + 90, here.y + 10, { steps: 6 });
  await page.mouse.up();
  await expect(page.getByTestId('simple-mode')).not.toHaveAttribute('data-focus', /.+/);
  // off the object the label and the cursor go
  await page.mouse.move(here.x + 90, here.y - 220);
  await expect(label).toHaveAttribute('data-visible', 'false');
  await expect(canvas).not.toHaveCSS('cursor', 'pointer');
});

test('one mast control at a time, both on one state: the card\'s heights while it is open, the top-bar stepper when it is closed', async ({ page }) => {
  await openSite(page);
  const masts = sidecar.sites[STORY].sampled_masts_m;
  const stepper = page.getByTestId('simple-mast-stepper');
  const picker = page.getByTestId('simple-mast-picker');
  await expect(picker).toBeVisible();
  await expect(stepper).toBeHidden();
  await page.getByTestId(`simple-mast-${masts[2]}`).click();
  await expect(page.getByTestId(`simple-mast-${masts[2]}`)).toHaveAttribute('aria-checked', 'true');
  // close the card: the stepper takes over, on the height just picked
  await page.getByTestId('site-card-close').click();
  await expect(picker).toHaveCount(0);
  await expect(stepper).toBeVisible();
  await expect(page.getByTestId('simple-mast-current')).toHaveText(`${masts[2]} m`);
  await page.getByTestId('simple-mast-up').click();
  await expect(page.getByTestId('simple-mast-current')).toHaveText(`${masts[3]} m`);
  // open it again: the card shows the stepper's height, and the stepper is gone
  await page.getByTestId('simple-show-answer').click();
  await expect(page.getByTestId(`simple-mast-${masts[3]}`)).toHaveAttribute('aria-checked', 'true');
  await expect(stepper).toBeHidden();
  // with the Sun's card in the slot, the stepper is the one control
  await page.getByTestId('scene-object-sun').click();
  await expect(page.getByTestId('scene-card')).toBeVisible();
  await expect(picker).toHaveCount(0);
  await expect(stepper).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(picker).toBeVisible();
  await expect(stepper).toBeHidden();
});

test('the mast: only sampled heights are offered, and a height with no bundle series is drawn as an outline that grows to it', async ({ page }) => {
  await openSite(page);
  const masts = sidecar.sites[STORY].sampled_masts_m;
  await page.getByTestId('scene-object-site').click();
  await expect(page.getByTestId('site-card')).toHaveAttribute('data-flown', 'true');
  const chips = page.getByTestId('simple-mast-picker').getByRole('radio');
  await expect(chips).toHaveCount(masts.length);
  expect(await chips.allInnerTexts()).toEqual(masts.map((m) => `${m} m`));
  const withSeries = new Set(ds.derived.scenarios.filter((s) => s.samples).map((s) => s.observer.mastM));
  const ghost = masts.find((m) => !withSeries.has(m))!;
  await page.getByTestId(`simple-mast-${ghost}`).click();
  await expect(page.getByTestId('ghost-mast')).toContainText(`${ghost} m`);
  await expect(page.getByTestId('simple-series-note')).toContainText(`no time series at ${ghost} m`);
  await settled(page);
  // the mast flown to is still in the picture and clear of the card
  expect((await whereIs(page, 'site')).covered).toEqual([]);
});

test('at a mast height with its own bundle series the ridges are not offered, and the page says why', async ({ page }) => {
  await openSite(page);
  const other = ds.derived.scenarios.find((s) => s.samples && s.observer.mastM !== baseline.observer.mastM && sidecar.sites[STORY].sampled_masts_m.includes(s.observer.mastM))!;
  await expect(page.getByTestId('scene-ridges-note')).toHaveCount(0);
  await expect(page.getByTestId(`scene-object-ridge:${ridges[0].id}`)).toBeVisible();
  await page.getByTestId(`simple-mast-${other.observer.mastM}`).click();
  await expect(page.getByTestId(`scene-object-ridge:${ridges[0].id}`)).toHaveCount(0);
  await expect(page.getByTestId('scene-ridges-note')).toHaveText(`No ridges here: the bundle names its blocking ridges for the ${baseline.observer.mastM} m mast series only, not for ${other.observer.mastM} m.`);
  await page.getByTestId(`simple-mast-${baseline.observer.mastM}`).click();
  await expect(page.getByTestId('scene-ridges-note')).toHaveCount(0);
  await expect(page.getByTestId(`scene-object-ridge:${ridges[0].id}`)).toBeVisible();
});

test('reduced motion: opening a card and going back are cuts', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await openSite(page);
  const home = await camera(page);
  await page.getByTestId('scene-object-earth').click();
  await expect(page.getByTestId('scene-card')).toBeVisible();
  await expect(page.getByTestId('simple-mode')).not.toHaveAttribute('data-fly', /.+/);
  const there = await camera(page);
  expect(there.slice(0, 6)).not.toEqual(home.slice(0, 6));
  await page.waitForTimeout(300);
  expect(sameCamera((await camera(page)).slice(0, 7), there.slice(0, 7)), 'already there: nothing is still moving').toBeLessThan(EXACT);
  await page.getByTestId('scene-card-back').click();
  await expect(page.getByTestId('scene-card')).toHaveCount(0);
  await expect.poll(async () => sameCamera(await camera(page), home), { timeout: 1000 }).toBeLessThan(EXACT);
});

test('with a card open: Esc closes the card first, then goes back to the Moon; the site card can be put away and brought back', async ({ page }) => {
  await openSite(page);
  await page.getByTestId('scene-object-sun').click();
  await expect(page.getByTestId('scene-card')).toBeVisible();
  await expect(page.getByTestId('site-card')).toHaveCount(0); // one card at a time in the slot
  await page.getByTestId('scene-card').getByRole('button', { name: 'Close card' }).click();
  await expect(page.getByTestId('scene-card')).toHaveCount(0);
  await expect(page.getByTestId('site-card')).toBeVisible();
  await page.getByTestId('site-card-close').click();
  await expect(page.getByTestId('site-card')).toHaveCount(0);
  await expect(page.getByTestId('simple-show-answer')).toBeVisible();
  await page.getByTestId('simple-show-answer').click();
  await expect(page.getByTestId('plain-answer')).toBeVisible();
});

for (const [w, h] of [
  [1440, 900],
  [390, 844],
] as const) {
  test.describe(`${w} × ${h}`, () => {
    test.use({ viewport: { width: w, height: h } });
    test('a card open: the object stays clear of it, nothing scrolls sideways, and axe finds no serious or critical issue', async ({ page }) => {
      await openSite(page);
      const b = page.getByTestId('scene-object-earth');
      await b.scrollIntoViewIfNeeded();
      await b.click();
      await expect(page.getByTestId('scene-card')).toBeAttached();
      await settled(page);
      // the picture's centre eases to the free space after the move: judge once it has stopped
      let last = '';
      await expect
        .poll(async () => {
          const now = JSON.stringify(await whereIs(page, 'earth'));
          const same = now === last;
          last = now;
          return same;
        }, { intervals: [400], timeout: 10_000 })
        .toBe(true);
      const at = await whereIs(page, 'earth');
      expect(at.covered, 'Earth is clear of the interface').toEqual([]);
      expect(at.x > 0 && at.x < w && at.y > 0 && at.y < h).toBe(true);
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(w);
      if (w < 640) await expect(page.getByTestId('scene-card').getByRole('heading', { level: 1 })).toBeInViewport({ ratio: 1 });
      const { violations } = await new AxeBuilder({ page }).analyze();
      expect(violations.filter((v) => v.impact === 'serious' || v.impact === 'critical').map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`)).toEqual([]);
    });

    // Sid, 18 Nov 2026: the SUN and EARTH sight labels were drawn over each other on the phone
    test('the Sun and Earth sight labels never overlap, on the arrival view and on every card view', async ({ page }) => {
      test.slow();
      await openSite(page);
      const labels = () =>
        page.evaluate(() =>
          ['sun', 'earth'].map((id) => {
            const el = document.querySelector(`[data-testid=sight-${id}]`) as HTMLElement | null;
            if (!el || getComputedStyle(el).display === 'none') return null;
            const r = el.getBoundingClientRect();
            return { l: r.left, t: r.top, r: r.right, b: r.bottom };
          }),
        );
      const apart = async (where: string) => {
        // the driver re-reads label sizes every 250 ms: judge after it has
        await page.waitForTimeout(400);
        const [s, e] = await labels();
        if (!s || !e) return; // one of them is off the picture: nothing to collide
        const overlap = s.l < e.r && e.l < s.r && s.t < e.b && e.t < s.b;
        expect(overlap, `${where}: sun ${JSON.stringify(s)} earth ${JSON.stringify(e)}`).toBe(false);
        // and neither runs into the stage's bottom controls (light tag, exaggeration, About this view)
        const ctl = await page.evaluate(() =>
          [...document.querySelectorAll('.simple-stage .light-tag, .simple-stage .exag-pick, .simple-stage details.scene-note')]
            .map((el) => el.getBoundingClientRect())
            .filter((r) => r.width > 0)
            .map((r) => ({ l: r.left, t: r.top, r: r.right, b: r.bottom })),
        );
        for (const c of ctl)
          for (const [n, x] of [['sun', s], ['earth', e]] as const) {
            const hit = x.l < c.r && c.l < x.r && x.t < c.b && c.t < x.b;
            expect(hit, `${where}: ${n} label ${JSON.stringify(x)} runs into a bottom control ${JSON.stringify(c)}`).toBe(false);
          }
      };
      await apart('arrival');
      for (const id of ['site', 'sun', 'earth', ...ridges.map((r) => `ridge:${r.id}`)]) {
        const b = page.getByTestId(`scene-object-${id}`);
        await b.click();
        await settled(page);
        await apart(id);
        await page.keyboard.press('Escape');
        await settled(page);
      }
    });

    // Sid, 18 Nov 2026: on the phone the "Look at" row was cut off at the right edge
    test('every "Look at" button is wholly on screen, with no sideways scroll', async ({ page }) => {
      await openSite(page);
      const list = page.getByTestId('scene-objects');
      for (const b of await list.getByRole('button').all()) {
        const r = (await b.boundingBox())!;
        expect(r.x, await b.innerText()).toBeGreaterThanOrEqual(0);
        expect(r.x + r.width, await b.innerText()).toBeLessThanOrEqual(w);
      }
      expect(await list.evaluate((el) => el.scrollWidth <= el.clientWidth)).toBe(true);
    });
  });
}

// Sid, 18 Nov 2026 (light table): lens flare and starburst are opening-sequence only; after the hand-off the Sun keeps only
// its soft bloom. The spikes are drawn only while uIntro > 0, and the site scene never sets uIntro.
test('the site scene draws no starburst: the intro strength is 0 there and the spikes need it', async ({ page }) => {
  await page.goto(`/?view=terrain&quality=high&cam=mast&site=${STORY}&t=2026-11-18T21:00:00Z`);
  await expect(page.getByTestId('plain-answer')).toContainText('Sun now in view', { timeout: 30_000 });
  await page.waitForFunction(() => !!(window as unknown as { __polarisPost?: unknown }).__polarisPost, null, { timeout: 30_000 });
  const post = () =>
    page.evaluate(() => {
      const f = (window as unknown as { __polarisPost: { final: { uniforms: Record<string, { value: number }>; material: { fragmentShader: string } } } }).__polarisPost.final;
      return { intro: f.uniforms.uIntro.value, frag: f.material.fragmentShader };
    });
  await page.waitForTimeout(1000);
  const p = await post();
  expect(p.intro).toBe(0);
  expect(p.frag).toContain('if (vVis > 0.0 && uIntro > 0.0)');
});
