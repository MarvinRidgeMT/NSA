import { expect, test } from '@playwright/test';

test('four-site Decision Lab is linked and switches every site without page errors', async ({ page }) => {
  const errors: Error[] = [];
  page.on('pageerror', (error) => errors.push(error));

  await page.goto('/#decision');
  await expect(page.getByTestId('decision-lab-link')).toHaveAttribute('href', './lab/index.html');

  await page.goto('/lab/index.html');
  const headline = page.locator('#headline');
  await expect(headline).not.toHaveText('Loading…');
  const sites = page.locator('#siteSeg button');
  await expect(sites).toHaveCount(4);
  for (let i = 0; i < 4; i += 1) {
    await sites.nth((i + 1) % 4).click();
    const before = await headline.textContent();
    await sites.nth(i).click();
    await expect(headline).not.toHaveText(before ?? '');
    await expect(headline).not.toHaveText('Loading…');
  }
  expect(errors.map((error) => error.message)).toEqual([]);
});
