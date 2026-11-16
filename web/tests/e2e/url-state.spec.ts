import { expect, test } from '@playwright/test';

/** Shareable links: the URL carries site, UTC sample, scenario, camera and surface layer; opening it restores them. */
const LINK = '/?bundle=polaris-x5d-roi-2026-11-14-v2.json&site=site01_roi6&t=2026-11-20T06:00:00Z&cam=overhead&layer=elevation#sky';

test('opening a link restores site, time, camera and surface layer', async ({ page }) => {
  await page.goto(LINK);
  await expect(page.locator('.stage-title h1')).toContainText('Site01 ROI6');
  await expect(page.getByTestId('utc-input')).toHaveValue(/2026-11-20T06:00/);
  await expect(page.getByTestId('cam-overhead')).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByTestId('scene3d')).toHaveAttribute('data-context', 'loaded', { timeout: 30_000 });
  await expect(page.getByTestId('surface-layer')).toHaveValue('elevation');
});

test('changing time and camera updates the URL; reloading it gives the same view', async ({ page }) => {
  await page.goto('/?bundle=polaris-x5d-roi-2026-11-14-v2.json&site=site04_roi3#sky');
  await expect(page.getByTestId('scene3d')).toHaveAttribute('data-context', 'loaded', { timeout: 30_000 });
  const inp = page.getByTestId('utc-input');
  await inp.fill('2026-11-26T23:00:00Z');
  await inp.press('Enter');
  await page.getByTestId('cam-ridge').click();
  await expect(page).toHaveURL(/t=2026-11-26T23:00:00Z/);
  await expect(page).toHaveURL(/cam=ridge/);
  await expect(page).toHaveURL(/site=site04_roi3/);
  const url = page.url();
  await page.goto(url);
  await expect(page.getByTestId('utc-input')).toHaveValue(/2026-11-26T23:00/);
  await expect(page.getByTestId('cam-ridge')).toHaveAttribute('aria-pressed', 'true');
});

test('a time outside the bundle is refused, not extrapolated, and the link says so', async ({ page }) => {
  await page.goto('/?bundle=polaris-x5d-roi-2026-11-14-v2.json&site=site04_roi3&t=2027-01-01T00:00:00Z#sky');
  await expect(page.getByTestId('utc-input')).toHaveValue(/2026-11-14T00:00/);
  await expect(page.getByText('never extrapolates', { exact: false })).toBeVisible();
});
