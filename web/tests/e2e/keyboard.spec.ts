import { expect, test } from '@playwright/test';
import { demoTimes, openDemo, scenario } from './helpers';

test('keyboard-only run: scrub, change scenario, open a failure, provenance', async ({ page }) => {
  await openDemo(page);
  // reach the scrubber with Tab only
  let found = false;
  for (let i = 0; i < 30 && !found; i++) {
    await page.keyboard.press('Tab');
    found = await page.evaluate(() => document.activeElement?.getAttribute('data-testid') === 'scrubber');
  }
  expect(found).toBe(true);
  await page.keyboard.press('ArrowRight');
  await page.keyboard.press('ArrowRight');
  await page.keyboard.press('ArrowRight');
  await expect(page.getByTestId('utc')).toHaveText(demoTimes[3]);
  await page.keyboard.press('End');
  await expect(page.getByTestId('utc')).toHaveText(demoTimes[demoTimes.length - 1]);
  await page.keyboard.press('Home');

  // scenario via keyboard
  await page.getByTestId('scenario-select').focus();
  await page.keyboard.press('KeyM');
  await expect(page.getByTestId('scenario-select')).toHaveValue('mast10');

  // failure via Tab + Enter
  const f = scenario('mast10').failures[0];
  found = false;
  for (let i = 0; i < 60 && !found; i++) {
    await page.keyboard.press('Tab');
    found = await page.evaluate((id) => document.activeElement?.getAttribute('data-testid') === `failure-${id}`, f.id);
  }
  expect(found).toBe(true);
  await page.keyboard.press('Enter');
  await expect(page.getByTestId('cross-section')).toBeVisible();

  // provenance opens with keyboard and closes with Escape; focus is visible
  await page.getByTestId('open-provenance').focus();
  await page.keyboard.press('Enter');
  await expect(page.getByTestId('provenance')).toBeVisible();
  await expect(page.getByTestId('bundle-sha')).toHaveText(/^[0-9a-f]{64}$/);
  await page.keyboard.press('Escape');
  await expect(page.getByTestId('provenance')).toBeHidden();
});
