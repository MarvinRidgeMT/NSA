import { test, expect, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

/**
 * S1 (Simple-mode design system): the hidden token sheet at ?mode=simple&sheet=1 shows the certainty sidecar's values, and
 * the Simple page and the sheet have no serious or critical axe issues. Expected values are read from the sidecar file here,
 * never typed in.
 */
test.use({ storageState: { cookies: [], origins: [] } });

const __dirname = dirname(fileURLToPath(import.meta.url));
type Row = { mast_m: number; metric: string; min: number; max: number; nominal: number; n_clones: number };
type Site = { sampled_masts_m: number[]; certainty_curve: Row[]; all_maps_100pct_sun_mast_m: number | null };
const sidecar = JSON.parse(readFileSync(resolve(__dirname, '../../public/certainty/sidecar.json'), 'utf8')) as { sites: Record<string, Site> };
const gallery = JSON.parse(readFileSync(resolve(__dirname, '../../public/showcase/gallery.json'), 'utf8')) as { items: { site: string; siteName: string }[] };
const nameOf = (id: string) => gallery.items.find((g) => g.site === id)?.siteName ?? id;
const row = (s: Site, m: number, metric: string) => s.certainty_curve.find((r) => r.mast_m === m && r.metric === metric);
const range = (r: Row) => (r.min === r.max ? `${r.min.toFixed(1)} %` : `${r.min.toFixed(1)}–${r.max.toFixed(1)} %`);
const spread = (r: Row) => Number((r.max - r.min).toFixed(1));

const SHEET = '/?mode=simple&sheet=1';
async function openSheet(page: Page) {
  await page.goto(SHEET);
  await expect(page.getByTestId('simple-sheet')).toBeVisible();
  await expect(page.locator('.s-objcard .s-facts')).toBeVisible({ timeout: 30_000 });
}

/** Every (site, mast) pin the sheet should draw: the first sampled mast and the all-maps-100 %-Sun mast, from the file. */
const expectedPins = Object.entries(sidecar.sites).flatMap(([id, s]) =>
  [...new Set([s.sampled_masts_m[0], s.all_maps_100pct_sun_mast_m].filter((m): m is number => typeof m === 'number'))].map((m) => ({
    id,
    mast: m,
    sun: row(s, m, 'sun_centre_pct')!,
  })),
);

test('token sheet: sample card and pins equal the certainty sidecar', async ({ page }) => {
  await openSheet(page);

  // the card shows the site whose variants disagree most at its first sampled mast
  const lead = [...expectedPins].sort((a, b) => spread(b.sun) - spread(a.sun))[0];
  const site = sidecar.sites[lead.id];
  const sun = row(site, lead.mast, 'sun_centre_pct')!;
  const both = row(site, lead.mast, 'both_centre_pct')!;
  const card = page.locator('.s-objcard');
  await expect(card.locator('.s-objcard-title')).toHaveText(nameOf(lead.id));
  await expect(card).toContainText(`mast ${lead.mast} m`);
  const facts = card.locator('.s-fact');
  await expect(facts.nth(0).locator('.s-fact-value')).toHaveText(range(sun));
  await expect(facts.nth(0).locator('.s-fact-sub')).toHaveText(`nominal ${sun.nominal.toFixed(1)} %`);
  await expect(facts.nth(1).locator('.s-fact-value')).toHaveText(range(both));
  await expect(facts.nth(1).locator('.s-fact-sub')).toHaveText(`nominal ${both.nominal.toFixed(1)} %`);
  await expect(facts.nth(2).locator('.s-fact-value')).toHaveText(site.all_maps_100pct_sun_mast_m === null ? '—' : `${site.all_maps_100pct_sun_mast_m} m`);
  await expect(card).toContainText(`across ${sun.n_clones} terrain variants`);

  // two pins (shimmer + static ring) per (site, mast); the drawn spread is the sidecar's max − min
  const pins = page.locator('.sheet-pin');
  await expect(pins).toHaveCount(expectedPins.length * 2);
  for (const [i, p] of expectedPins.entries()) {
    for (const k of [0, 1]) {
      const el = pins.nth(i * 2 + k);
      await expect(el.locator('b')).toHaveText(`${spread(p.sun).toFixed(1)}-point spread`);
      await expect(el).toContainText(`${nameOf(p.id)} · ${p.mast} m`);
      const btn = el.locator('.s-pin');
      expect(Number(await btn.evaluate((b) => (b as HTMLElement).style.getPropertyValue('--spread')))).toBe(spread(p.sun));
      if (spread(p.sun) === 0) await expect(btn).toHaveAttribute('data-zero', 'true');
      else await expect(btn).not.toHaveAttribute('data-zero', /.*/);
    }
  }

  // the site select lists exactly the sidecar's sites
  await expect(page.locator('#sh-site option')).toHaveText(Object.keys(sidecar.sites).map(nameOf));
});

test('token sheet: no horizontal scroll at 390 px', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await openSheet(page);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});

/**
 * The one node axe cannot judge: ash text on a glass panel laid over full white. axe ignores backdrop-filter, so it scores
 * the tint over raw white; the panel's brightness(--glass-dim) is what makes it pass. That node's colour-contrast result is
 * waived here and checked on rendered pixels instead (next test). Nothing else is waived.
 */
const GLASS_ON_WHITE = '.sheet-ground[data-ground="white"] > .s-panel > .s-meta';

async function axeSeriousOrCritical(page: Page) {
  const { violations } = await new AxeBuilder({ page }).analyze();
  return violations
    .filter((v) => v.impact === 'serious' || v.impact === 'critical')
    .map((v) => ({ ...v, nodes: v.nodes.filter((n) => !(v.id === 'color-contrast' && n.target.join(' ') === GLASS_ON_WHITE)) }))
    .filter((v) => v.nodes.length)
    .map((v) => `${v.impact} ${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`);
}

test('glass panel over full white: rendered ash text keeps 4.5:1', async ({ page }) => {
  await openSheet(page);
  const panel = page.locator('.sheet-ground[data-ground="white"] > .s-panel');
  await panel.scrollIntoViewIfNeeded();
  const box = (await panel.boundingBox())!;
  // a patch of the panel's own background (inside the border, above the text)
  const png = await page.screenshot({ clip: { x: box.x + 4, y: box.y + 4, width: 2, height: 2 } });
  const bg = await page.evaluate(async (b64) => {
    const img = new Image();
    img.src = `data:image/png;base64,${b64}`;
    await img.decode();
    const c = document.createElement('canvas');
    c.width = img.width;
    c.height = img.height;
    const ctx = c.getContext('2d')!;
    ctx.drawImage(img, 0, 0);
    return [...ctx.getImageData(0, 0, 1, 1).data].slice(0, 3);
  }, png.toString('base64'));
  const fg = await panel.locator('> .s-meta').evaluate((el) => getComputedStyle(el).color.match(/\d+/g)!.slice(0, 3).map(Number));
  const lum = (c: number[]) =>
    c.reduce((s, v, i) => {
      const x = v / 255;
      return s + [0.2126, 0.7152, 0.0722][i] * (x <= 0.04045 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4);
    }, 0);
  const [hi, lo] = [lum(fg), lum(bg)].sort((a, b) => b - a);
  expect((hi + 0.05) / (lo + 0.05)).toBeGreaterThanOrEqual(4.5);
});

test('axe: Simple page has no serious or critical issues', async ({ page }) => {
  // S4 (17 Nov): a bare "/" now opens on the south-pole globe; ?view=terrain opens the terrain view these tests are about.
  await page.goto('/?view=terrain');
  await expect(page.getByTestId('simple-mode')).toBeVisible();
  await expect(page.getByTestId('plain-answer')).toBeVisible({ timeout: 30_000 });
  expect(await axeSeriousOrCritical(page)).toEqual([]);
});

test('axe: token sheet has no serious or critical issues', async ({ page }) => {
  await openSheet(page);
  expect(await axeSeriousOrCritical(page)).toEqual([]);
});
