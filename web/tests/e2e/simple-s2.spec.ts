import { test, expect, type Locator, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

/**
 * S2 (17 Nov 2026): the Simple-mode shell is light chrome over a full-screen 3D scene. Expected numbers are read from the
 * certainty sidecar file here, never typed in. Starts with empty storage, as a first-time visitor does.
 */
test.use({ storageState: { cookies: [], origins: [] } });

const __dirname = dirname(fileURLToPath(import.meta.url));
type Row = { mast_m: number; metric: string; min: number; max: number; n_clones: number };
type Site = { sampled_masts_m: number[]; certainty_curve: Row[]; all_maps_100pct_sun_mast_m: number | null };
const sidecar = JSON.parse(readFileSync(resolve(__dirname, '../../public/certainty/sidecar.json'), 'utf8')) as { sites: Record<string, Site> };
const SITE = 'site04_roi3'; // Simple mode opens on the story site (store/siteDefaults.ts STORY_SITE)
const site = sidecar.sites[SITE];
const row = (m: number, metric: string) => site.certainty_curve.find((r) => r.mast_m === m && r.metric === metric)!;
const range = (r: Row) => (r.min === r.max ? `${r.min.toFixed(1)} %` : `${r.min.toFixed(1)}–${r.max.toFixed(1)} %`);

async function openSimple(page: Page, q = '') {
  await page.goto(`/${q}`);
  await expect(page.getByTestId('simple-mode')).toBeVisible();
  await expect(page.getByTestId('plain-answer')).toBeVisible({ timeout: 30_000 });
}
const box = async (l: Locator) => (await l.boundingBox())!;
const apart = (a: { x: number; y: number; width: number; height: number }, b: { x: number; y: number; width: number; height: number }) =>
  a.x + a.width <= b.x || b.x + b.width <= a.x || a.y + a.height <= b.y || b.y + b.height <= a.y;

test('the scene fills the window and the panels leave the site (window centre) clear', async ({ page }) => {
  await openSimple(page);
  await expect(page.getByTestId('scene3d')).toBeVisible({ timeout: 30_000 });
  const vp = page.viewportSize()!;
  const scene = await box(page.getByTestId('scene3d'));
  expect(scene).toEqual({ x: 0, y: 0, width: vp.width, height: vp.height });
  const centre = { x: vp.width / 2 - 60, y: vp.height / 2 - 60, width: 120, height: 120 };
  for (const id of ['simple-answer', 'simple-stats', 'simple-banner', 'simple-footer', 'utc-input']) {
    const b = await box(page.getByTestId(id));
    expect(apart(b, centre), `${id} keeps clear of the window centre`).toBe(true);
    expect(b.x >= 0 && b.y >= 0 && b.x + b.width <= vp.width && b.y + b.height <= vp.height, `${id} is inside the window`).toBe(true);
  }
  expect(await page.evaluate(() => [document.documentElement.scrollWidth, document.documentElement.scrollHeight])).toEqual([vp.width, vp.height]);
});

test('top bar: wordmark, site selector, mast stepper, Sound: off, Expert mode; credits strip', async ({ page }) => {
  await openSimple(page);
  await expect(page.locator('.s-chrome .s-brand')).toHaveText('POLARIS X');
  // the selector lists the loaded bundle's sites; picking one renames the page
  const select = page.getByTestId('simple-site-select');
  const names = await select.locator('option').allTextContents();
  expect(names.length).toBeGreaterThan(0);
  await expect(page.getByTestId('simple-site')).toHaveText(await select.locator('option:checked').innerText());
  await expect(page.getByTestId('simple-sound')).toHaveText('Sound: off');
  await expect(page.getByTestId('simple-sound')).toHaveAttribute('aria-disabled', 'true');
  await expect(page.getByTestId('mode-expert')).toHaveText('Expert mode');
  await expect(page.getByTestId('simple-footer')).toContainText('Data: NASA LRO (PGDA), JPL Horizons');
  await expect(page.getByTestId('simple-footer')).toContainText('Not affiliated with NASA');
  await expect(page.getByTestId('simple-ai-disclosure')).toHaveText('AI disclosure');
  // the mission-clock slot holds the working clock
  await expect(page.locator('[data-slot="mission-clock"]').getByTestId('scrubber')).toBeVisible();
});

test('mast stepper walks the sidecar heights only, and the numbers follow', async ({ page }) => {
  test.slow(); // every step may switch the bundle scenario and redraw the scene
  await openSimple(page);
  const masts = site.sampled_masts_m;
  const current = page.getByTestId('simple-mast-current');
  const up = page.getByTestId('simple-mast-up');
  const down = page.getByTestId('simple-mast-down');
  // go to the lowest sampled height, then step up through every one
  await page.getByTestId(`simple-mast-${masts[0]}`).click();
  await expect(current).toHaveText(`${masts[0]} m`);
  await expect(down).toHaveAttribute('aria-disabled', 'true');
  for (const [i, m] of masts.entries()) {
    await expect(current).toHaveText(`${m} m`);
    await expect(page.getByTestId(`simple-mast-${m}`)).toHaveAttribute('aria-checked', 'true');
    await expect(page.getByTestId('simple-stat-sun')).toHaveText(range(row(m, 'sun_centre_pct')));
    await expect(page.getByTestId('simple-stat-both')).toHaveText(range(row(m, 'both_centre_pct')));
    if (i < masts.length - 1) await up.click();
  }
  await expect(up).toHaveAttribute('aria-disabled', 'true');
  await up.click({ force: true }); // at the top (aria-disabled): nothing beyond the sampled heights
  await expect(current).toHaveText(`${masts[masts.length - 1]} m`);
  await down.click();
  await expect(current).toHaveText(`${masts[masts.length - 2]} m`);
});

test('site selector switches site and keeps to that site\'s sampled heights', async ({ page }) => {
  await openSimple(page);
  await page.getByTestId(`simple-mast-${site.sampled_masts_m[1]}`).click();
  const select = page.getByTestId('simple-site-select');
  const count = await select.locator('option').count();
  for (let i = 0; i < count; i++) {
    await select.selectOption({ index: i });
    await expect(page.getByTestId('simple-site')).toHaveText(await select.locator('option').nth(i).innerText());
    // either the sidecar has this site (answer + picker) or the page says it has no rows; never a blank or borrowed answer
    await expect(page.getByTestId('plain-answer').or(page.getByTestId('simple-no-site'))).toBeVisible();
  }
});

test('demo-video note can be dismissed for the session', async ({ page }) => {
  await openSimple(page);
  await page.getByTestId('simple-banner-dismiss').click();
  await expect(page.getByTestId('simple-banner')).toHaveCount(0);
  await page.reload();
  await expect(page.getByTestId('plain-answer')).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId('simple-banner')).toHaveCount(0);
});

test('Decision and Evidence open in Expert mode for now', async ({ page }) => {
  await openSimple(page);
  await page.getByTestId('simple-open-decision').click();
  await expect(page.locator('#ws-decision')).toBeVisible({ timeout: 30_000 });
  await openSimple(page, '?mode=simple');
  await page.getByTestId('simple-open-evidence').click();
  await expect(page.locator('#ws-evidence')).toBeVisible({ timeout: 30_000 });
});

test('keyboard: logical tab order, and Esc closes the limits panel', async ({ page }) => {
  await openSimple(page);
  const order: string[] = [];
  for (let i = 0; i < 12; i++) {
    await page.keyboard.press('Tab');
    order.push(await page.evaluate(() => (document.activeElement as HTMLElement | null)?.dataset.testid ?? document.activeElement?.className ?? ''));
  }
  const picked = `simple-mast-${await page.getByTestId('simple-mast-picker').getByRole('radio', { checked: true }).innerText().then((t) => t.replace(' m', ''))}`;
  expect(order).toEqual([
    'skip',
    'simple-site-select',
    'simple-mast-down',
    'simple-mast-up',
    'simple-open-decision',
    'simple-open-evidence',
    'simple-sound',
    'mode-expert',
    'mode-expert-banner',
    'simple-banner-dismiss',
    picked,
    's-tag',
  ]);
  // every stop shows the 2 px amber ring
  await page.getByTestId('mode-expert').focus();
  await page.keyboard.press('Shift+Tab');
  await page.keyboard.press('Tab');
  const ring = await page.getByTestId('mode-expert').evaluate((el) => {
    const c = getComputedStyle(el);
    return [c.outlineStyle, c.outlineWidth];
  });
  expect(ring).toEqual(['solid', '2px']);

  const limits = page.getByTestId('simple-limits');
  await limits.locator('summary').click();
  await expect(limits.locator('li').first()).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(limits.locator('li').first()).toBeHidden();

  // two disclosures open: Esc closes one per press, the focused one first, and focus returns to its summary
  const about = page.locator('.simple-stage details.scene-note');
  await about.locator('summary').click();
  await limits.locator('summary').click();
  await expect(limits).toHaveAttribute('open', '');
  await expect(about).toHaveAttribute('open', '');
  await page.keyboard.press('Escape');
  await expect(limits).not.toHaveAttribute('open', '');
  await expect(about).toHaveAttribute('open', '');
  await expect(limits.locator('summary')).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(about).not.toHaveAttribute('open', '');
});

test.describe('1024 × 768', () => {
  test.use({ viewport: { width: 1024, height: 768 } });
  test('the known overlaps are gone', async ({ page }) => {
    await openSimple(page);
    await expect(page.locator('[data-testid=scene3d][data-context=loaded]')).toBeVisible({ timeout: 45_000 });
    // "Vertical" no longer sits on "About this view"
    expect(apart(await box(page.locator('.simple-stage .exag-pick')), await box(page.locator('.simple-stage details.scene-note')))).toBe(true);
    // "Go to UTC" no longer runs into Play
    const goto = await box(page.locator('.s-clock .goto'));
    for (const b of await page.locator('.s-clock .scrub > *').all()) expect(apart(await box(b), goto)).toBe(true);
    // the Earth label is whole: inside the window and not under either panel
    const earth = page.getByTestId('sight-earth');
    await expect(earth).toBeVisible();
    const e = await box(earth);
    expect(e.x).toBeGreaterThanOrEqual(0);
    expect(e.x + e.width).toBeLessThanOrEqual(1024);
    for (const p of ['.s-answerpanel', '.s-statspanel']) expect(apart(e, await box(page.locator(p))), `Earth label clear of ${p}`).toBe(true);
    // with "About this view" open, every number keeps its SOURCE-BASED tag on screen and the two boxes do not overlap
    await page.locator('.simple-stage details.scene-note summary').click();
    await expect(page.getByTestId('quality-note')).toBeVisible();
    for (const t of await page.locator('.s-statspanel .s-tag').all()) await expect(t).toBeInViewport({ ratio: 1 });
    const stats = await box(page.locator('.s-statspanel'));
    for (const t of await page.locator('.s-statspanel .s-tag').all()) expect((await box(t)).y + (await box(t)).height).toBeLessThanOrEqual(stats.y + stats.height);
    expect(apart(stats, await box(page.locator('.simple-stage details.scene-note')))).toBe(true);
    await page.keyboard.press('Escape');
    // the panels fit without covering the clock
    expect(apart(await box(page.locator('.s-answerpanel')), await box(page.locator('.s-bottom')))).toBe(true);
    expect(apart(await box(page.locator('.s-statspanel')), await box(page.locator('.s-bottom')))).toBe(true);
  });
});

test.describe('phone, 390 × 844', () => {
  test.use({ viewport: { width: 390, height: 844 } });
  test('top row plus a bottom sheet; no horizontal scroll; Esc closes the sheet and the menu', async ({ page }) => {
    await openSimple(page);
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
    for (const id of ['simple-site-select', 'simple-mast-stepper', 'simple-menu', 'simple-sheet-handle', 'scrubber'])
      expect((await box(page.getByTestId(id))).x + (await box(page.getByTestId(id))).width, `${id} fits the width`).toBeLessThanOrEqual(390);

    // collapsed: the verdict shows, the numbers are below the fold
    const shell = page.getByTestId('simple-mode');
    await expect(shell).toHaveAttribute('data-sheet', 'closed');
    await expect(page.locator('.pa-verdict')).toBeInViewport({ ratio: 1 });
    await expect(page.getByTestId('simple-stat-sun')).not.toBeInViewport();
    await page.getByTestId('simple-sheet-handle').click();
    await expect(shell).toHaveAttribute('data-sheet', 'open');
    await expect(page.getByTestId('simple-stat-sun')).toBeInViewport();
    await page.keyboard.press('Escape');
    await expect(shell).toHaveAttribute('data-sheet', 'closed');
    await expect(page.getByTestId('simple-sheet-handle')).toBeFocused();

    // scrolled to the end while open, then collapsed: the verdict is back in view, not scrolled off
    await page.getByTestId('simple-sheet-handle').click();
    await expect(shell).toHaveAttribute('data-sheet', 'open');
    await page.locator('.s-dock').evaluate((el) => (el.scrollTop = el.scrollHeight));
    expect(await page.locator('.s-dock').evaluate((el) => el.scrollTop)).toBeGreaterThan(0);
    await page.keyboard.press('Escape'); // not a click: clicking the handle would scroll it, and the sheet, back into view
    await expect(shell).toHaveAttribute('data-sheet', 'closed');
    expect(await page.locator('.s-dock').evaluate((el) => el.scrollTop)).toBe(0);
    await expect(page.locator('.pa-verdict')).toBeInViewport({ ratio: 1 });

    // the rest of the chrome is in the menu
    await expect(page.getByTestId('mode-expert')).toBeHidden();
    await page.getByTestId('simple-menu').click();
    await expect(page.getByTestId('mode-expert')).toBeVisible();
    await expect(page.getByTestId('simple-open-evidence')).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(page.getByTestId('mode-expert')).toBeHidden();
    await expect(page.getByTestId('simple-menu')).toBeFocused();
  });
});

/** axe at the three review sizes: no serious or critical issue, nothing waived. On the phone, also with the menu and the sheet open. */
async function axeSeriousOrCritical(page: Page) {
  const { violations } = await new AxeBuilder({ page }).analyze();
  return violations
    .filter((v) => v.impact === 'serious' || v.impact === 'critical')
    .map((v) => `${v.impact} ${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`);
}
for (const [w, h] of [
  [1440, 900],
  [1024, 768],
  [390, 844],
] as const) {
  test.describe(`axe ${w} × ${h}`, () => {
    test.use({ viewport: { width: w, height: h } });
    test('the shell has no serious or critical issues', async ({ page }) => {
      await openSimple(page);
      // the panels fade in on arrival; contrast is judged once they have settled, not mid-fade
      await page.waitForFunction(() =>
        ['.s-answerpanel', '.s-statspanel', '.s-bottom'].every((s) => {
          const el = document.querySelector(s);
          return el && getComputedStyle(el).opacity === '1';
        }),
      );
      expect(await axeSeriousOrCritical(page)).toEqual([]);
      if (w < 640) {
        await page.getByTestId('simple-menu').click();
        expect(await axeSeriousOrCritical(page)).toEqual([]);
        await page.keyboard.press('Escape');
        await page.getByTestId('simple-sheet-handle').click();
        await expect(page.getByTestId('simple-mode')).toHaveAttribute('data-sheet', 'open');
        expect(await axeSeriousOrCritical(page)).toEqual([]);
      }
    });
  });
}

test.describe('phone, 390 × 844, a site the sidecar has no rows for', () => {
  test.use({ viewport: { width: 390, height: 844 } });
  test('the collapsed sheet shows the whole "no rows" note, as it shows the verdict for other sites', async ({ page }) => {
    await openSimple(page);
    const select = page.getByTestId('simple-site-select');
    const values = await select.locator('option').evaluateAll((os) => os.map((o) => (o as HTMLOptionElement).value));
    let found = false;
    for (const v of values) {
      await select.selectOption(v);
      await expect(page.getByTestId('plain-answer').or(page.getByTestId('simple-no-site'))).toBeVisible();
      if (await page.getByTestId('simple-no-site').count()) {
        found = true;
        break;
      }
    }
    expect(found, 'the bundle offers at least one site the sidecar has no rows for').toBe(true);
    await expect(page.getByTestId('simple-mode')).toHaveAttribute('data-sheet', 'closed');
    // the sheet re-measures after the site switch, then slides: judge it once the peek and the slide have settled
    let last = '';
    await expect
      .poll(async () => {
        const now = await page.evaluate(() => `${document.querySelector<HTMLElement>('.s-shell')!.style.getPropertyValue('--s-peek')}|${document.querySelector('.s-dock')!.getBoundingClientRect().top}`);
        const same = now === last;
        last = now;
        return same;
      }, { intervals: [500] })
      .toBe(true);
    const fits = await page.getByTestId('simple-no-site').evaluate((el) => el.getBoundingClientRect().bottom <= innerHeight);
    expect(fits, 'the whole note is above the bottom of the screen').toBe(true);
  });
});
