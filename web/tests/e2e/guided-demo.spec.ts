import { expect, test, type Page } from '@playwright/test';

// Ten scene changes with a software (SwiftShader) GPU take well over the default 60 s; real hardware is far faster.
test.describe.configure({ timeout: 240_000 });

/**
 * Final Apex P2 (15 Nov 2026): the guided demo is deterministic and leaves no trace.
 * Each scene sets its whole state (route, site, scenario, mast, exact sample, camera), so it reads the same from a fresh launch,
 * by Back/dots, or after the user switched site and mast. Exit / Esc / Finish restore exactly what was there before.
 */
type Sig = { url: string; utc: string; site: string; scenario: string; view: string | null; mast: string | null };
async function sig(page: Page): Promise<Sig> {
  return {
    url: new URL(page.url()).hash,
    utc: (await page.getByTestId('utc').first().textContent()) ?? '',
    site: await page.getByTestId('site-select').inputValue(),
    scenario: await page.getByTestId('scenario-select').inputValue(),
    view: await page.getByTestId('stage-view').getAttribute('data-view'),
    mast: await page.locator('[data-testid^="mast-"][aria-checked="true"]').first().getAttribute('data-testid').catch(() => null),
  };
}
async function scene(page: Page, n: number) {
  await expect(page.getByTestId('guide')).toContainText(`${n} / 5`);
  await page.waitForTimeout(700); // the scene action runs once its data is present; let the store settle
  return sig(page);
}

test('fresh launch: every scene has a fixed state, and stepping Back reproduces it exactly', async ({ page }) => {
  await page.goto('/');
  await page.getByTestId('story-guide').click();
  const fwd: Sig[] = [await scene(page, 1)];
  for (let i = 2; i <= 5; i++) {
    await page.getByTestId('guide-next').click();
    fwd.push(await scene(page, i));
  }
  expect(fwd[0].url).toBe('#sky');
  expect(fwd[4].url).toBe('#decision');
  expect(fwd[1].view).toBe('ridge');
  expect(fwd[2].view).toBe('mast');
  expect(fwd[1].utc).toBe(fwd[2].utc); // Certainty Height is shown at the same blocked hour as the Ridge of Record
  expect(fwd[0].utc).not.toBe(fwd[1].utc);
  for (let i = 4; i >= 1; i--) {
    await page.getByTestId('guide-back').click();
    const b = await scene(page, i);
    expect(b).toEqual(fwd[i - 1]);
  }
});

test('after switching site and mast, the demo still shows the same scenes; Esc restores the user state exactly', async ({ page }) => {
  await page.goto('/');
  await page.getByTestId('story-guide').click();
  const ref = [await scene(page, 1)];
  await page.getByTestId('guide-next').click();
  ref.push(await scene(page, 2));
  await page.keyboard.press('Escape');
  await expect(page.getByTestId('guide')).toHaveCount(0);

  // the user moves elsewhere: another site, the 10 m scenario, another time, the Decision workspace
  await page.goto('/#sky');
  await expect(page.getByTestId('instrument')).toBeVisible({ timeout: 30_000 });
  const sites = await page.getByTestId('site-select').locator('option').count();
  const heroSite = await page.getByTestId('site-select').inputValue();
  if (sites > 1) await page.getByTestId('site-select').selectOption({ index: heroSite === '0' ? 1 : 0 });
  const opts = await page.getByTestId('scenario-select').locator('option').allTextContents();
  const tenIdx = opts.findIndex((o) => /10 m/.test(o));
  if (tenIdx >= 0) await page.getByTestId('scenario-select').selectOption({ index: tenIdx });
  await page.getByTestId('tab-decision').click();
  await expect(page).toHaveURL(/#decision$/);
  const user = await page.evaluate(() => ({ hash: location.hash }));
  const before = { site: await page.getByTestId('site-select').inputValue(), scenario: await page.getByTestId('scenario-select').inputValue(), utc: (await page.getByTestId('utc').first().textContent()) ?? '' };

  await page.getByTestId('guide-start').click();
  const again = [await scene(page, 1)];
  await page.getByTestId('guide-next').click();
  again.push(await scene(page, 2));
  expect(again).toEqual(ref);

  await page.keyboard.press('Escape');
  await expect(page.getByTestId('guide')).toHaveCount(0);
  await expect(page).toHaveURL(new RegExp(`${user.hash}$`));
  await expect.poll(() => page.getByTestId('site-select').inputValue()).toBe(before.site);
  await expect.poll(() => page.getByTestId('scenario-select').inputValue()).toBe(before.scenario);
  await expect(page.getByTestId('utc').first()).toHaveText(before.utc);
  await expect(page.getByTestId('guide-start')).toBeFocused();
});

test('Play advances on its own, Pause holds; the last scene links to the Evidence and keeps the demo state', async ({ page }) => {
  test.setTimeout(120_000); // one 12 s scene + a 13 s pause check on software GL
  await page.goto('/');
  await page.getByTestId('story-guide').click();
  await scene(page, 1);
  await page.getByTestId('guide-play').click();
  await expect(page.getByTestId('guide-play')).toHaveAttribute('aria-pressed', 'true');
  // 12 s scene (GUIDE_DWELL_MS). Tests render with software GL (SwiftShader), where the busy main thread delays the timer by ~4.5 s
  // (measured 15 Nov: 16.5 s per scene in the cloud), so allow 25 s. Same assertion: Play advances by itself.
  await expect(page.getByTestId('guide')).toContainText('2 / 5', { timeout: 25_000 });
  await page.getByTestId('guide-play').click();
  await expect(page.getByTestId('guide-play')).toHaveText('Play');
  await page.waitForTimeout(13_000);
  await expect(page.getByTestId('guide')).toContainText('2 / 5');
  for (let i = 3; i <= 5; i++) await page.getByTestId('guide-next').click();
  await scene(page, 5);
  const site = await page.getByTestId('site-select').inputValue();
  await page.getByTestId('guide-evidence').click();
  await expect(page.getByTestId('guide')).toHaveCount(0);
  await expect(page).toHaveURL(/#evidence$/);
  expect(await page.getByTestId('site-select').inputValue()).toBe(site);
});

test('reduced motion: the demo runs end to end and Exit restores', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/#decision');
  await expect(page.getByTestId('decision-card')).toBeVisible({ timeout: 30_000 });
  await page.getByTestId('guide-start').click();
  for (let i = 1; i < 5; i++) {
    await scene(page, i);
    await page.getByTestId('guide-next').click();
  }
  await scene(page, 5);
  await page.getByTestId('guide-exit').click();
  await expect(page).toHaveURL(/#decision$/);
  await expect(page.getByTestId('guide')).toHaveCount(0);
});
