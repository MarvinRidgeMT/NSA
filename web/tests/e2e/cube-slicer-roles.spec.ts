import { expect, test } from '@playwright/test';
import { existsSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { ws } from './helpers';

const __dirname = dirname(fileURLToPath(import.meta.url));
const dir = resolve(__dirname, '../../public/cubes/site04_roi3');
const has = existsSync(resolve(dir, 'centre_mast_schedule.json.gz')) && existsSync(resolve(dir, 'link.json.gz'));

/** v2 roles (docs/v2/6D_MODEL.md): the slicer groups controls by axis role; every old test id still works. */
test.describe('scenario cube slicer · 6D role groups', () => {
  test.skip(!has, 'cubes not built');

  test('centre cube: T under "What we don\'t know", mast and start under "What we choose", R preset as a requirement', async ({ page }) => {
    await page.goto('/?bundle=site04_roi3_2026-11-14_14d_mast1m.json');
    await ws(page, 'decision');
    const slicer = page.getByTestId('cube-slicer');
    await slicer.scrollIntoViewIfNeeded();
    await expect(page.getByTestId('cube-card-value')).toBeVisible({ timeout: 30_000 });

    const x = page.getByTestId('cube-group-uncertainty');
    const l = page.getByTestId('cube-group-decision');
    const r = page.getByTestId('cube-group-requirement');
    await expect(x.locator('legend')).toContainText("What we don't know");
    await expect(l.locator('legend')).toContainText('What we choose');
    await expect(x.getByTestId('cube-ctl-T')).toBeVisible();
    await expect(l.getByTestId('cube-ctl-D_mast')).toBeVisible();
    await expect(l.getByTestId('cube-ctl-S')).toBeVisible();
    await expect(r.getByTestId('cube-ctl-R')).toBeVisible();
    await expect(page.getByTestId('cube-group-context')).toHaveCount(0);
    // the groups are inside the traced cube panel
    await expect(slicer).toHaveAttribute('data-source', /scenario cube/);
  });

  test('link cube: margin is a requirement, link target is context', async ({ page }) => {
    await page.goto('/?bundle=site04_roi3_2026-11-14_14d_mast1m.json');
    await ws(page, 'decision');
    const slicer = page.getByTestId('cube-slicer');
    await slicer.scrollIntoViewIfNeeded();
    await expect(page.getByTestId('cube-card-value')).toBeVisible({ timeout: 30_000 });
    const file = page.getByTestId('cube-file');
    const opt = await file.locator('option').evaluateAll((os) => (os as HTMLOptionElement[]).map((o) => o.value));
    expect(opt).toContain('link.json.gz');
    await file.selectOption('link.json.gz');
    await expect(page.getByTestId('cube-group-requirement').getByTestId('cube-ctl-R_margin')).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId('cube-group-context').getByTestId('cube-ctl-target')).toBeVisible();
    await expect(page.getByTestId('cube-group-uncertainty').getByTestId('cube-ctl-T')).toBeVisible();
    await expect(page.getByTestId('cube-group-decision').getByTestId('cube-ctl-D_mast')).toBeVisible();
  });
});
