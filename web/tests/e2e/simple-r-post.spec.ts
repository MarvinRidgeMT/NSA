import { test, expect, type Page } from '@playwright/test';

/**
 * Section R: Simple-mode post effects and quality tiers. CI runs on software rendering (SwiftShader), which gets the low tier
 * (post off): that is the path a first test covers. ?quality=high forces the post chain on, so the chain itself is exercised here
 * too (it must mount, draw and raise no error); how it looks and what it costs is measured on the Mac (scripts/post_compare.mjs).
 */
test.use({ storageState: { cookies: [], origins: [] } });

async function openSimple(page: Page, q = '') {
  // S4 (17 Nov): a bare "/" now opens on the south-pole globe; ?view=terrain opens the terrain view these tests are about.
  await page.goto(`/?mode=simple&view=terrain${q}`);
  await expect(page.getByTestId('simple-mode')).toBeVisible();
  await expect(page.locator('[data-testid=scene3d][data-context=loaded]')).toBeVisible({ timeout: 45_000 });
}
const hasPost = (page: Page) => page.evaluate(() => '__polarisPost' in window);

test('software rendering gets the low tier: post off, and About this view says so', async ({ page }) => {
  await openSimple(page);
  await expect(page.getByTestId('scene3d')).toHaveAttribute('data-quality', 'low');
  expect(await hasPost(page)).toBe(false);
  await page.locator('.simple-stage details.scene-note summary').click();
  const note = page.getByTestId('quality-note');
  await expect(note).toContainText('Quality: low');
  await expect(note).toContainText('Sun glow: camera effect, display only; lens flare and starburst are in the opening sequence only');
});

test('?quality=high mounts the post chain, draws the scene and raises no error', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('console', (m) => {
    if (m.type() === 'error' && !/favicon/.test(m.text())) errors.push(m.text());
  });
  await openSimple(page, '&quality=high&cam=mast');
  await expect(page.getByTestId('scene3d')).toHaveAttribute('data-quality', 'high');
  await expect.poll(() => hasPost(page), { timeout: 20_000 }).toBe(true);
  await page.locator('.simple-stage details.scene-note summary').click();
  await expect(page.getByTestId('quality-note')).toContainText('Quality: high');
  await expect(page.getByTestId('quality-note')).toContainText('Sun glow: camera effect, display only; lens flare and starburst are in the opening sequence only');
  // the canvas is not blank: a picture of terrain under a black sky does not compress to a few hundred bytes
  await page.waitForTimeout(1500);
  const png = await page.locator('[data-testid=scene3d] canvas').screenshot();
  expect(png.byteLength).toBeGreaterThan(20_000);
  // the answer beside the scene is unchanged by the tier: it reads the bundle and the sidecar, not the renderer
  await expect(page.getByTestId('plain-answer')).toContainText('Sun now');
  expect(errors).toEqual([]);
});

test('the tier does not change any number or state on the page', async ({ page }) => {
  const read = async (q: string) => {
    await openSimple(page, q);
    await expect(page.getByTestId('plain-answer')).toBeVisible();
    return { answer: await page.getByTestId('plain-answer').innerText(), stats: await page.getByTestId('simple-stats').innerText(), light: await page.getByTestId('light-tag').innerText() };
  };
  const low = await read('&quality=low');
  expect(await read('&quality=high')).toEqual(low);
  expect(await read('&quality=medium')).toEqual(low);
});

test('Expert mode never loads the post chain and shows no quality line', async ({ page }) => {
  const requested: string[] = [];
  page.on('request', (r) => requested.push(r.url()));
  await page.goto('/?mode=expert&quality=high#sky');
  await expect(page.locator('[data-testid=scene3d][data-context=loaded]')).toBeVisible({ timeout: 45_000 });
  await expect(page.getByTestId('scene3d')).not.toHaveAttribute('data-quality', /.+/);
  await expect(page.getByTestId('quality-note')).toHaveCount(0);
  expect(await hasPost(page)).toBe(false);
  expect(requested.filter((u) => /SimplePost/.test(u))).toEqual([]);
});

// Two bundle samples of site04_roi3 (the ones scripts/post_compare.mjs uses): the bundle flags the Sun in sight at the first and
// blocked at the second. The starburst and the HDR disc follow the bundle flag, never the picture.
const SITE = 'site04_roi3';
const SUN_IN_SIGHT = '2026-11-18T21:00:00Z';
const SUN_BLOCKED = '2026-11-27T02:00:00Z';
const flare = (page: Page) => page.evaluate(() => (window as unknown as { __polarisPost?: { final: { uniforms: { uFlare: { value: number } } } } }).__polarisPost?.final.uniforms.uFlare.value ?? null);

test('glow and starburst follow the bundle: on when the Sun is in sight, off when the bundle says blocked', async ({ page }) => {
  await openSimple(page, `&quality=high&cam=mast&site=${SITE}&t=${SUN_IN_SIGHT}`);
  await expect.poll(() => hasPost(page), { timeout: 20_000 }).toBe(true);
  await expect(page.getByTestId('plain-answer')).toContainText('Sun now in view');
  await expect.poll(() => flare(page), { timeout: 10_000 }).toBeGreaterThan(0);
  await openSimple(page, `&quality=high&cam=mast&site=${SITE}&t=${SUN_BLOCKED}`);
  await expect.poll(() => hasPost(page), { timeout: 20_000 }).toBe(true);
  // the bundle's own flag, as the answer beside the scene states it
  await expect(page.getByTestId('plain-answer')).toContainText('Sun now blocked');
  await page.waitForTimeout(1000);
  expect(await flare(page)).toBe(0);
});

test.describe('reduced motion', () => {
  test.use({ reducedMotion: 'reduce' });
  test('film grain holds one fixed pattern', async ({ page }) => {
    await openSimple(page, '&quality=high');
    await expect.poll(() => hasPost(page), { timeout: 20_000 }).toBe(true);
    const seed = () => page.evaluate(() => {
      const p = (window as unknown as { __polarisPost: { last: { uniforms: { uSeed: { value: { x: number; y: number } } } } } }).__polarisPost;
      const s = p.last.uniforms.uSeed.value;
      return [s.x, s.y];
    });
    const a = await seed();
    await page.waitForTimeout(800);
    expect(await seed()).toEqual(a);
  });
});

test('Expert mode keeps its own canvas settings (multisampled, no composer) even with ?quality=high', async ({ page }) => {
  await page.goto('/?mode=expert&quality=high#sky');
  await expect(page.locator('[data-testid=scene3d][data-context=loaded]')).toBeVisible({ timeout: 45_000 });
  const attrs = await page.locator('[data-testid=scene3d] canvas').evaluate((c) => {
    const gl = (c as HTMLCanvasElement).getContext('webgl2');
    return gl?.getContextAttributes() ?? null;
  });
  expect(attrs?.antialias).toBe(true);
  expect(await hasPost(page)).toBe(false);
});
