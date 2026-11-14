import { expect, test } from '@playwright/test';
import { demoTimes, goTo, openDemo, scenario, shots } from './helpers';

test.describe('displayed margins equal bundle values', () => {
  for (const idx of [3, 21, 40]) {
    test(`sample ${idx}: ${demoTimes[idx]}`, async ({ page }) => {
      await openDemo(page);
      await expect(page.getByTestId('demo-banner')).toBeVisible();
      await expect(page.getByTestId('status-badge')).toHaveAttribute('data-status', 'DEMO');
      await goTo(page, demoTimes[idx]);
      await expect(page.getByTestId('utc')).toHaveText(demoTimes[idx]);
      for (const sid of ['baseline', 'mast10', 'east100']) {
        await page.getByTestId('scenario-select').selectOption(sid);
        const sc = scenario(sid);
        for (const t of ['sun', 'earth'] as const) {
          const m = page.getByTestId(`${t}-margin`);
          await expect(m).toHaveAttribute('data-value', String(sc.samples[t].marginDeg[idx]));
          const shown = (await m.textContent())!.replace('−', '-').replace('°', '');
          expect(Number(shown)).toBeCloseTo(sc.samples[t].marginDeg[idx], 4);
          await expect(page.getByTestId(`${t}-state`)).toContainText(sc.samples[t].visible[idx] ? 'VISIBLE' : 'BLOCKED');
        }
        for (const mt of sc.metrics) {
          await expect(page.getByTestId(`metric-${mt.id}`).locator('td').first()).toHaveAttribute('data-value', String(mt.value));
        }
      }
    });
  }

  test('between samples is labelled interpolated; outside coverage is refused', async ({ page }) => {
    await openDemo(page);
    await goTo(page, '2026-11-14T15:30:00Z');
    await expect(page.getByTestId('sample-pos')).toContainText('between samples');
    await goTo(page, '2026-11-20T00:00:00Z');
    await expect(page.getByTestId('time-error')).toContainText('outside bundle coverage');
    await expect(page.getByTestId('utc')).toHaveText('2026-11-14T15:30:00Z');
  });

  test('clicking a failure opens its cross-section from bundle critical cells', async ({ page }) => {
    await openDemo(page);
    const f = scenario('baseline').failures[0];
    await page.getByTestId(`failure-${f.id}`).click();
    await expect(page.getByTestId('cross-section')).toBeVisible();
    await expect(page.getByTestId('cross-section')).toContainText(`cell [${f.firstHit.cell.join(', ')}]`);
    await expect(page.getByTestId('utc')).toHaveText(f.time);
    await page.waitForTimeout(800);
    await page.screenshot({ path: `${shots}/02-demo-failure-cross-section.png`, fullPage: true });
  });
});
