import { expect, test } from '@playwright/test';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { ws } from './helpers';

const __dirname = dirname(fileURLToPath(import.meta.url));
const file = (s: string) => resolve(__dirname, `../../public/cubes/${s}/decision6d.json`);
const has = existsSync(file('site04_roi3'));

test.describe('6D decision panels (robust choice, regret, VoI, landing search, Pareto)', () => {
  test.skip(!has, 'decision6d.json not built');

  for (const [site, bundle] of [
    ['site04_roi3', 'site04_roi3_2026-11-14_14d_mast1m.json'],
    ['site01_roi6', 'site01_roi6_2026-11-14_14d_mast1m.json'],
  ] as const) {
    test(`${site}: every question shows the stored robust and nominal choice`, async ({ page }) => {
      const c = JSON.parse(readFileSync(file(site), 'utf8'));
      const qs: { id: string; kind: string }[] = JSON.parse(c.dims[0].note);
      await page.goto(`/?bundle=${bundle}`);
      await ws(page, 'decision');
      const panel = page.getByTestId('decision6d');
      await panel.scrollIntoViewIfNeeded();
      await expect(panel).toHaveAttribute('data-label', /SOURCE-BASED/);
      await expect(page.getByTestId('d6-not-prob')).toHaveText('k of N maps is not a probability.');
      for (const [qi, q] of qs.entries()) {
        await page.getByTestId('d6-question').selectOption(String(qi));
        const labels: string[] = c.derived[`q__${q.id}__by_choice`].dims[0].value_labels;
        const rob = c.metrics.robust_choice_index.values[qi];
        const nom = c.metrics.nominal_choice_index.values[qi];
        await expect(page.getByTestId('d6-robust')).toHaveAttribute('data-index', String(rob));
        await expect(page.getByTestId('d6-robust')).toContainText(labels[rob]);
        await expect(page.getByTestId('d6-nominal')).toContainText(labels[nom]);
        await expect(page.getByTestId('d6-kchange')).toContainText('not a probability');
        await expect(page.getByTestId('d6-voi')).toBeVisible();
        if (q.kind === 'landing') {
          const cb = `landing__${q.id.replace('landing_', '')}__candidates`;
          const sol: number[] = c.derived[cb].metrics.solver_sun_pct.values;
          await expect(page.getByTestId('d6-land-sol-0')).toHaveText(`${sol[0].toFixed(2)} %`);
          await expect(page.getByTestId('d6-land-mae')).toContainText('pct points');
        }
      }
      await expect(page.locator('main')).not.toContainText(/probability of success/i);
    });
  }

  test('Pareto front count and axis labels come from the file', async ({ page }) => {
    const c = JSON.parse(readFileSync(file('site04_roi3'), 'utf8'));
    test.skip(!c.derived.pareto__positions, 'Pareto run not in decision6d.json');
    const m = c.derived.pareto__positions.metrics;
    await page.goto('/?bundle=site04_roi3_2026-11-14_14d_mast1m.json');
    await ws(page, 'decision');
    const p = page.getByTestId('d6-pareto');
    await p.scrollIntoViewIfNeeded();
    await expect(page.getByTestId('d6-pareto-count')).toHaveAttribute('data-value', String(m.on_front_robust.values.filter(Boolean).length));
    await page.getByTestId('d6-pareto-robust').uncheck();
    await expect(page.getByTestId('d6-pareto-count')).toHaveAttribute('data-value', String(m.on_front_nominal.values.filter(Boolean).length));
    await expect(page.getByTestId('d6-pareto-axes')).toContainText('ENGINEERING ASSUMPTION');
    await expect(page.getByTestId('d6-pareto-ice')).toContainText('not shown');
  });

  test('a site without decision6d shows "not computed"', async ({ page }) => {
    await page.goto('/?bundle=demo-fixture.json');
    await ws(page, 'decision');
    await expect(page.getByTestId('decision6d-missing')).toBeVisible();
  });
});
