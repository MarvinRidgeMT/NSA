import { expect, test } from '@playwright/test';

/**
 * NASA GSFC shape-from-shading display relief (session A, 15 Nov 2026). The relief is DISPLAY ONLY: it changes the picture,
 * never a number. Site01 ROI6 is fully covered by the SfS region; Site04 ROI3 only on its west side.
 */
const at = (site: string) => `/?bundle=polaris-x5d-roi-2026-11-14-v2.json&site=${site}#sky`;

test('Site01 ROI6: SfS relief is on by default, labelled display-only with its source; switching it off changes no number', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  await page.goto(at('site01_roi6'));
  await expect(page.getByTestId('scene3d')).toHaveAttribute('data-context', 'loaded', { timeout: 60_000 });
  const toggle = page.getByTestId('surface-detail');
  await expect(toggle).toHaveAttribute('aria-pressed', 'true', { timeout: 30_000 });
  const label = page.getByTestId('surface-detail-label');
  await expect(label).toContainText('shape-from-shading');
  await expect(label).toContainText('DISPLAY ONLY');
  await expect(label).toContainText('whole crop');
  await expect(label).toContainText('synthetic');
  const before = await page.getByTestId('instrument').innerText();
  await toggle.click();
  await expect(toggle).toHaveAttribute('aria-pressed', 'false');
  await expect(label).toContainText("LOLA 5 m crop (the solver's surface)");
  await expect(toggle).toContainText('off');
  expect(await page.getByTestId('instrument').innerText()).toBe(before);
  await toggle.click();
  await expect(label).toContainText('shape-from-shading');
  expect(await page.getByTestId('instrument').innerText()).toBe(before);
  expect(errors).toEqual([]);
});

test('Site04 ROI3: partial SfS coverage is stated as a percentage', async ({ page }) => {
  await page.goto(at('site04_roi3'));
  await expect(page.getByTestId('scene3d')).toHaveAttribute('data-context', 'loaded', { timeout: 60_000 });
  await expect(page.getByTestId('surface-detail-label')).toContainText('34 % of crop', { timeout: 30_000 });
});
