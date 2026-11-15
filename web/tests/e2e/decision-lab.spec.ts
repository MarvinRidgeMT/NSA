import { expect, test } from '@playwright/test';

test('Decision Lab is linked and finishes loading without page errors', async ({ page }) => {
  const errors: Error[] = [];
  page.on('pageerror', (error) => errors.push(error));

  await page.goto('/');
  await expect(page.getByTestId('decision-lab-link')).toHaveAttribute('href', './lab/index.html');

  await page.goto('/lab/index.html');
  await expect(page.locator('#headline')).not.toHaveText('Loading…');
  expect(errors.map((error) => error.message)).toEqual([]);
});
