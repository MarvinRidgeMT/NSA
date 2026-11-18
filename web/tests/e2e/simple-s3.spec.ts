import { test, expect, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { INTRO, LOAD_WEIGHTS, lightCaption } from '../../src/simple/introMath';

/**
 * S3 (17 Nov 2026): the opening sequence. It plays in the globe's own canvas while the bundle and the Moon model load, then
 * hands over to the S4 globe. Expected words and numbers are read here from the ROI bundle and from introMath, never typed in.
 * CI draws with software rendering (low tier: no post effects); how it looks and what it costs is measured on the Mac
 * (tmp/s3, the S3 report). The Moon model's response is held back here so the sequence can be looked at while it waits.
 */
test.use({ storageState: { cookies: [], origins: [] } });

const __dirname = dirname(fileURLToPath(import.meta.url));
const bundle = JSON.parse(readFileSync(resolve(__dirname, '../../../data/viewer/polaris-x5d-roi-2026-11-14-v2.json'), 'utf8')) as {
  datasets: { siteId: string; site: { name: string }; ephemeris: { samples: { time: string; sun: { az: number } }[] } }[];
};
const globeDir = resolve(__dirname, '../../public/globe');
const hasGlobe = existsSync(globeDir) && readdirSync(globeDir).some((f) => f.endsWith('.glb'));
test.skip(!hasGlobe, 'no Moon model in web/public/globe (git-ignored NASA asset): Simple mode opens on the terrain view, with no opening sequence');

const STORY = 'site04_roi3'; // the site Simple mode starts on (store/siteDefaults.ts)
const shell = (page: Page) => page.getByTestId('simple-mode');
const intro = (page: Page) => page.getByTestId('simple-intro');
const globeShown = (page: Page) => page.locator('[data-testid=simple-globe][data-shown=true]');

/** Hold the Moon model's response until `release()`; everything else loads as usual. */
async function holdMoon(page: Page) {
  let release!: () => void;
  const gate = new Promise<void>((r) => (release = r));
  await page.route('**/globe/*.glb', async (route) => {
    await gate;
    await route.continue().catch(() => undefined);
  });
  return release;
}
const camera = (page: Page) =>
  page.evaluate(() => {
    const g = (window as unknown as { __polarisGlobe?: { camera: { position: { x: number; y: number; z: number } } } }).__polarisGlobe;
    return g ? [g.camera.position.x, g.camera.position.y, g.camera.position.z] : null;
  });

test('the sequence plays on a visit to Simple mode: Skip, the progress line and "Sound: off" are there; the globe is not usable yet', async ({ page }) => {
  const release = await holdMoon(page);
  await page.goto('/');
  await expect(intro(page)).toBeVisible();
  await expect(shell(page)).toHaveAttribute('data-intro', 'play');
  await expect(page.getByTestId('intro-skip')).toBeVisible();
  await expect(page.getByTestId('intro-progress')).toBeVisible();
  // "Sound: off" keeps its S2 place in the top bar, and Expert mode stays one press away
  await expect(page.getByTestId('simple-sound')).toBeVisible();
  await expect(page.getByTestId('simple-sound')).toContainText('Sound: off');
  await expect(page.getByTestId('mode-expert')).toBeVisible();
  // the globe's Check-a-spot box (18 Nov layout: it took the side card's place), pins and credits wait unseen
  await expect(page.getByTestId('simple-globe')).toHaveAttribute('data-phase', 'intro');
  await expect(page.getByTestId('spot-box')).toBeHidden();
  await expect(page.getByTestId('simple-footer')).toBeHidden();
  await expect(globeShown(page)).toHaveCount(0);
  release();
  await expect(globeShown(page)).toBeVisible({ timeout: 45_000 });
  await expect(intro(page)).toHaveCount(0);
  await expect(shell(page)).not.toHaveAttribute('data-intro', /.+/);
  await expect(page.getByTestId('spot-box')).toBeVisible();
  await expect(page.getByTestId('simple-footer')).toBeVisible();
  await expect(page.getByTestId('simple-sound')).toBeVisible();
});

test('progress is the loaders\' own: it stops short while the Moon model is held back, and the sequence waits for it', async ({ page }) => {
  const release = await holdMoon(page);
  await page.goto('/');
  const bar = page.getByTestId('intro-progress');
  // bundle and sidecar read, no byte of the Moon yet: exactly their two shares of the line
  const without = Math.floor((LOAD_WEIGHTS.bundle + LOAD_WEIGHTS.sidecar) * 100);
  await expect(bar).toHaveAttribute('aria-valuenow', String(without), { timeout: 30_000 });
  await expect(page.getByTestId('intro-pct')).toHaveText(`${without} %`);
  await expect(intro(page)).toContainText('Loading the Moon');
  // well past the longest the sequence runs on its own, it is still waiting, and still says so
  await page.waitForTimeout(INTRO.OPEN_MS + INTRO.ARC_MS + 1000);
  await expect(bar).toHaveAttribute('aria-valuenow', String(without));
  await expect(shell(page)).toHaveAttribute('data-intro', 'play');
  await expect(globeShown(page)).toHaveCount(0);
  release();
  await expect(globeShown(page)).toBeVisible({ timeout: 45_000 });
});

test('the light line is the bundle\'s: time and Sun azimuth of the first sample at the opening site', async ({ page }) => {
  const release = await holdMoon(page);
  await page.goto('/');
  const d = bundle.datasets.find((x) => x.siteId === STORY)!;
  const s0 = d.ephemeris.samples[0];
  const line = page.getByTestId('intro-light');
  await expect(line).toHaveText(lightCaption(Date.parse(s0.time), s0.sun.az, d.site.name), { timeout: 30_000 });
  await expect(line).toContainText(`Sun azimuth ${s0.sun.az.toFixed(1)}° at ${d.site.name}`);
  release();
  await expect(globeShown(page)).toBeVisible({ timeout: 45_000 });
});

for (const how of ['Escape', 'Enter', 'click', 'Skip button'] as const) {
  test(`Skip by ${how}: the sequence ends at once when the data is in`, async ({ page }) => {
    await page.goto('/');
    // wait for the Moon to be in the scene, so only the sequence itself is left to wait for
    await expect(page.locator('[data-testid=simple-globe][data-state=ready]')).toBeAttached({ timeout: 45_000 });
    if ((await shell(page).getAttribute('data-intro')) !== 'play') test.skip(true, 'the sequence had already ended on its own');
    const t0 = Date.now();
    if (how === 'click') await page.mouse.click(720, 450);
    else if (how === 'Skip button') await page.getByTestId('intro-skip').click();
    else await page.keyboard.press(how);
    await expect(globeShown(page)).toBeVisible({ timeout: 10_000 });
    // far sooner than the move to the pole takes unskipped (frames are slow under software rendering, hence the margin)
    expect(Date.now() - t0).toBeLessThan(INTRO.ARC_MS);
    await expect(intro(page)).toHaveCount(0);
  });
}

test('Skip still works during the last of the camera move, after the interface has come in', async ({ page }) => {
  await page.goto('/');
  await expect(shell(page)).toHaveAttribute('data-intro', 'settle', { timeout: 45_000 });
  const t0 = Date.now();
  await page.keyboard.press('Escape');
  await expect(globeShown(page)).toBeVisible({ timeout: 10_000 });
  expect(Date.now() - t0).toBeLessThan(INTRO.SKIP_MS + 600);
});

test('Skip before the data is in: nothing is shown early; the globe comes as soon as the Moon has loaded', async ({ page }) => {
  const release = await holdMoon(page);
  await page.goto('/');
  await expect(page.getByTestId('intro-skip')).toBeVisible();
  await page.getByTestId('intro-skip').click();
  await page.waitForTimeout(800);
  await expect(globeShown(page)).toHaveCount(0);
  await expect(page.getByTestId('intro-progress')).toBeVisible();
  release();
  await expect(globeShown(page)).toBeVisible({ timeout: 45_000 });
});

test('the Skip button is reachable by keyboard and has a visible focus ring', async ({ page }) => {
  const release = await holdMoon(page);
  await page.goto('/');
  const skip = page.getByTestId('intro-skip');
  await expect(skip).toBeVisible();
  for (let i = 0; i < 8 && !(await skip.evaluate((el) => el === document.activeElement)); i++) await page.keyboard.press('Tab');
  await expect(skip).toBeFocused();
  expect(await skip.evaluate((el) => getComputedStyle(el).outlineStyle)).not.toBe('none');
  release();
  await page.keyboard.press('Enter');
  await expect(globeShown(page)).toBeVisible({ timeout: 45_000 });
  // after the hand-off, focus is on the globe: the pin of the site Simple mode opened on, not lost on <body>
  await expect(page.locator(`[data-testid=globe-pin-${STORY}] button`)).toBeFocused({ timeout: 5000 });
});

test('Esc during the sequence: after the hand-off, focus lands on a globe pin', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('[data-testid=simple-globe][data-state=ready]')).toBeAttached({ timeout: 45_000 });
  if ((await shell(page).getAttribute('data-intro')) !== 'play') test.skip(true, 'the sequence had already ended on its own');
  await page.keyboard.press('Escape');
  await expect(globeShown(page)).toBeVisible({ timeout: 10_000 });
  await expect(page.locator(`[data-testid=globe-pin-${STORY}] button`)).toBeFocused({ timeout: 5000 });
});

test('during the sequence, Tab never reaches the unseen globe pins; the fading Skip leaves the tab order', async ({ page }) => {
  const release = await holdMoon(page);
  await page.goto('/');
  await expect(page.getByTestId('intro-light')).toBeVisible({ timeout: 30_000 });
  await expect(page.locator('.s-globe-pins[inert]')).toHaveCount(1);
  for (let i = 0; i < 25; i++) {
    await page.keyboard.press('Tab');
    expect(await page.evaluate(() => !!document.activeElement?.closest('.s-globe-pins'))).toBe(false);
  }
  release();
  await expect(shell(page)).toHaveAttribute('data-intro', 'settle', { timeout: 45_000 });
  await expect(intro(page)).toHaveAttribute('inert', '');
  await expect(globeShown(page)).toBeVisible({ timeout: 45_000 });
  await expect(page.locator('.s-globe-pins[inert]')).toHaveCount(0);
});

test('the card\'s site rows take no presses until the globe is live', async ({ page }) => {
  await page.goto('/');
  await expect(shell(page)).toHaveAttribute('data-intro', 'settle', { timeout: 45_000 });
  expect(await page.getByTestId(`globe-row-${STORY}`).evaluate((el) => getComputedStyle(el).pointerEvents)).toBe('none');
  await expect(globeShown(page)).toBeVisible({ timeout: 45_000 });
  await expect(shell(page)).not.toHaveAttribute('data-intro', /.+/, { timeout: 5000 });
  expect(await page.getByTestId(`globe-row-${STORY}`).evaluate((el) => getComputedStyle(el).pointerEvents)).not.toBe('none');
});

test('a Moon model that fails to load is never called "Loaded"', async ({ page }) => {
  await page.route('**/globe/*.glb', (route) => route.abort());
  await page.goto('/');
  await expect(intro(page)).toContainText('The Moon model could not be loaded', { timeout: 30_000 });
  await expect(intro(page)).not.toContainText('Loaded');
});

test('hand-off: the sequence ends on the globe view itself (camera over the south pole), and nothing in the layout moves', async ({ page }) => {
  const release = await holdMoon(page);
  await page.goto('/');
  await expect(page.getByTestId('intro-skip')).toBeVisible();
  const boxes = () =>
    page.evaluate(() =>
      ['.s-chrome', '.s-banner', '.s-globe-view', '.s-spot-box', '.s-main > .s-credits', '[data-testid=simple-sound]'].map((q) => {
        // layout boxes (offset*), which a transform does not change: the card's short rise as it fades in is not a layout shift
        const el = document.querySelector<HTMLElement>(q)!;
        return [q, el.offsetLeft, el.offsetTop, el.offsetWidth, el.offsetHeight];
      }),
    );
  await expect(page.locator('.s-globe-view canvas').first()).toBeAttached({ timeout: 30_000 });
  // measured once the bundle and the sidecar are in (the card, unseen, has its rows by then); only the Moon is still to come
  await expect(page.getByTestId('intro-progress')).toHaveAttribute('aria-valuenow', String(Math.floor((LOAD_WEIGHTS.bundle + LOAD_WEIGHTS.sidecar) * 100)), { timeout: 30_000 });
  const during = await boxes();
  release();
  await expect(globeShown(page)).toBeVisible({ timeout: 45_000 });
  const p = (await camera(page))!;
  const len = Math.hypot(p[0], p[1], p[2]);
  expect(p[1] / len).toBeLessThan(-0.99999); // straight over the south pole: the S4 view
  await expect(shell(page)).not.toHaveAttribute('data-intro', /.+/, { timeout: 5000 });
  expect(await boxes()).toEqual(during);
});

test('Expert mode never shows the sequence (?mode=expert, an Expert route, and Expert remembered)', async ({ page }) => {
  for (const url of ['/?mode=expert', '/#decision']) {
    await page.goto(url);
    await expect(page.getByTestId('simple-mode')).toHaveCount(0);
    await expect(page.locator('.s-intro')).toHaveCount(0);
  }
  await page.evaluate(() => localStorage.setItem('polaris-x.mode', 'expert'));
  await page.goto('/');
  await expect(page.getByTestId('simple-mode')).toHaveCount(0);
  await expect(page.locator('.s-intro')).toHaveCount(0);
});

test('a link that opens a site\'s terrain directly has no sequence in front of it', async ({ page }) => {
  await page.goto('/?view=terrain');
  await expect(shell(page)).toHaveAttribute('data-place', 'site');
  await expect(page.locator('.s-intro')).toHaveCount(0);
  await expect(shell(page)).not.toHaveAttribute('data-intro', /.+/);
});

test.describe('prefers-reduced-motion', () => {
  test.use({ reducedMotion: 'reduce' });
  test('one still frame and a progress line, then a cross-fade to the globe', async ({ page }) => {
    const release = await holdMoon(page);
    await page.goto('/');
    await expect(page.getByTestId('intro-progress')).toBeVisible();
    await expect(page.getByTestId('simple-globe')).toHaveAttribute('data-still', 'true');
    await expect.poll(() => camera(page), { timeout: 30_000 }).not.toBeNull();
    // still: the camera does not move while the sequence waits
    await page.waitForTimeout(400);
    const a = await camera(page);
    await page.waitForTimeout(900);
    expect(await camera(page)).toEqual(a);
    await expect(shell(page)).toHaveAttribute('data-intro', 'play');
    release();
    await expect(globeShown(page)).toBeVisible({ timeout: 45_000 });
    // the still frame was copied and laid over the globe view, then faded away (opacity only)
    const still = page.locator('.s-intro-still');
    await expect(still).toHaveAttribute('data-on', /true|done/);
    await expect(still).toHaveAttribute('data-on', 'done', { timeout: 10_000 });
    expect(Number(await still.evaluate((el) => getComputedStyle(el).opacity))).toBe(0);
    const p = (await camera(page))!;
    expect(p[1] / Math.hypot(p[0], p[1], p[2])).toBeLessThan(-0.99999);
  });
});

test('axe: the sequence has no serious or critical issues (1440 x 900 and 390 x 844)', async ({ page }) => {
  for (const size of [
    { width: 1440, height: 900 },
    { width: 390, height: 844 },
  ]) {
    await page.setViewportSize(size);
    const release = await holdMoon(page);
    await page.goto('/');
    await expect(page.getByTestId('intro-light')).toBeVisible({ timeout: 30_000 });
    const { violations } = await new AxeBuilder({ page }).analyze();
    expect(violations.filter((v) => v.impact === 'serious' || v.impact === 'critical').map((v) => `${v.impact} ${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`)).toEqual([]);
    release();
    await expect(globeShown(page)).toBeVisible({ timeout: 45_000 });
    await page.unroute('**/globe/*.glb');
  }
});
