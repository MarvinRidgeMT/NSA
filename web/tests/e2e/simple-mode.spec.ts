import { test, expect, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

/**
 * Simple mode (16 Nov): the front door at a bare "/". These tests start with empty storage (playwright.config.ts remembers
 * Expert mode for every other spec) so "/" resolves exactly as it does for a first-time visitor.
 */
test.use({ storageState: { cookies: [], origins: [] } });

const __dirname = dirname(fileURLToPath(import.meta.url));
type Row = { mast_m: number; metric: string; min: number; max: number; n_clones: number };
type Site = { sampled_masts_m: number[]; certainty_curve: Row[]; all_maps_100pct_sun_mast_m: number | null };
const sidecar = JSON.parse(readFileSync(resolve(__dirname, '../../public/certainty/sidecar.json'), 'utf8')) as { sites: Record<string, Site> };
// Simple mode opens on the story site of the ROI export (store/siteDefaults.ts STORY_SITE)
const SITE = 'site04_roi3';
const site = sidecar.sites[SITE];
const row = (m: number, metric: string) => site.certainty_curve.find((r) => r.mast_m === m && r.metric === metric)!;
const range = (r: Row) => (r.min === r.max ? `${r.min.toFixed(1)} %` : `${r.min.toFixed(1)}–${r.max.toFixed(1)} %`);
const short = (x: number) => `${Math.round(x * 10) / 10}`.replace(/\.0$/, '');

async function openSimple(page: Page) {
  await page.goto('/');
  await expect(page.getByTestId('simple-mode')).toBeVisible();
  await expect(page.getByTestId('plain-answer')).toBeVisible({ timeout: 30_000 });
}

test('bare / opens Simple mode with the answer, 3D hero, clock, limits and footer', async ({ page }) => {
  await openSimple(page);
  await expect(page.getByTestId('simple-banner')).toContainText('The demo video shows Expert mode — switch anytime.');
  await expect(page.getByText('Does a lander here keep the Sun?')).toBeVisible();
  await expect(page.getByTestId('simple-site')).not.toBeEmpty();
  await expect(page.getByTestId('scene3d')).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId('utc-input')).toBeVisible();
  await expect(page.getByTestId('plain-answer')).toContainText('Sun now');
  await expect(page.getByTestId('plain-answer')).toContainText('Earth now');
  await expect(page.getByTestId('simple-limits')).toContainText('geometric line of sight only');
  await expect(page.getByTestId('simple-limits')).toContainText('not validated');
  await expect(page.getByTestId('simple-footer')).toContainText('Not affiliated with NASA');
  await expect(page.locator('.s-tag')).toHaveCount(3);
  for (const t of await page.locator('.s-tag').all()) {
    await expect(t).toHaveText('SOURCE-BASED · UNVALIDATED');
    await expect(t).toHaveAttribute('href', /#evidence$/);
  }
  // Expert-only chrome is not on the Simple page
  await expect(page.getByTestId('workspaces')).toHaveCount(0);
});

test('Simple mode numbers equal the certainty sidecar at every sampled mast', async ({ page }) => {
  await openSimple(page);
  const chips = page.getByTestId('simple-mast-picker').getByRole('radio');
  await expect(chips).toHaveCount(site.sampled_masts_m.length);
  const cert = site.all_maps_100pct_sun_mast_m;
  for (const m of site.sampled_masts_m) {
    await page.getByTestId(`simple-mast-${m}`).click();
    await expect(page.getByTestId(`simple-mast-${m}`)).toHaveAttribute('aria-checked', 'true');
    const s = row(m, 'sun_centre_pct');
    const b = row(m, 'both_centre_pct');
    await expect(page.getByTestId('simple-stat-sun')).toHaveText(range(s));
    await expect(page.getByTestId('simple-stat-both')).toHaveText(range(b));
    await expect(page.getByTestId('simple-stat-cert')).toHaveText(cert === null ? '—' : `${cert} m`);
    const verdict = s.min >= 100 ? 'Yes.' : s.min >= 70 ? 'Mostly.' : 'Not reliably.';
    const answer = page.getByTestId('plain-answer');
    await expect(answer.locator('.pa-verdict strong')).toHaveText(verdict);
    await expect(answer).toContainText(`With a ${m} m mast`);
    await expect(answer).toContainText(`${s.n_clones} terrain variants`);
    if (s.min < 100) {
      await expect(answer).toContainText(s.min === s.max ? `${short(s.min)} %` : `${short(s.min)}–${short(s.max)} %`);
      if (cert !== null && cert !== m) await expect(answer.locator('.pa-hint')).toContainText(`Raise the mast to ${cert} m for 100 % in every variant`);
    }
  }
});

test('mast picker is keyboard operable', async ({ page }) => {
  await openSimple(page);
  const first = site.sampled_masts_m[0];
  const second = site.sampled_masts_m[1];
  await page.getByTestId(`simple-mast-${first}`).click();
  await page.keyboard.press('ArrowRight');
  await expect(page.getByTestId(`simple-mast-${second}`)).toHaveAttribute('aria-checked', 'true');
  await expect(page.getByTestId(`simple-mast-${second}`)).toBeFocused();
  await expect(page.getByTestId('simple-stat-sun')).toHaveText(range(row(second, 'sun_centre_pct')));
});

test('mode switch round-trips and is remembered', async ({ page }) => {
  await openSimple(page);
  await page.getByTestId('mode-expert').click();
  await expect(page).toHaveURL(/[?&]mode=expert/);
  await expect(page.getByTestId('mode-simple')).toBeVisible();
  await expect(page.getByTestId('workspaces')).toBeVisible();
  await expect(page.getByTestId('simple-mode')).toHaveCount(0);
  expect(await page.evaluate(() => localStorage.getItem('polaris-x.mode'))).toBe('expert');

  // the choice is remembered: a bare "/" now opens Expert
  await page.goto('/');
  await expect(page.getByTestId('workspaces')).toBeVisible();
  await expect(page.getByTestId('simple-mode')).toHaveCount(0);

  await page.getByTestId('mode-simple').click();
  await expect(page.getByTestId('simple-mode')).toBeVisible();
  expect(new URL(page.url()).search).toBe('');
  expect(await page.evaluate(() => localStorage.getItem('polaris-x.mode'))).toBe('simple');
  await page.reload();
  await expect(page.getByTestId('simple-mode')).toBeVisible();
});

test('expert routes and the source tag open Expert mode', async ({ page }) => {
  await page.goto('/#decision');
  await expect(page.locator('#ws-decision')).toBeVisible({ timeout: 30_000 });
  await page.goto('/?mode=expert');
  await expect(page.getByTestId('workspaces')).toBeVisible();
  await openSimple(page);
  await page.locator('.s-tag').first().click();
  await expect(page.locator('#ws-evidence')).toBeVisible({ timeout: 30_000 });
});
