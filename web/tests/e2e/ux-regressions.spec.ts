import { expect, test } from '@playwright/test';
import { existsSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
const __dirname = dirname(fileURLToPath(import.meta.url));
const sci = existsSync(resolve(__dirname, '../../public/bundles/site01_2026-11-14_14d.json'));
const url = sci ? '/?bundle=site01_2026-11-14_14d.json' : '/?bundle=demo-fixture.json';

test('mouse wheel over the 3D view scrolls the page instead of zooming the scene', async ({ page }) => {
  await page.goto(url);
  const scene = page.locator('[data-testid=horizon-dome], [data-testid=scene3d]').first();
  await scene.scrollIntoViewIfNeeded();
  await page.waitForTimeout(800);
  const box = (await scene.boundingBox())!;
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 3);
  const before = await page.evaluate(() => window.scrollY);
  await page.mouse.wheel(0, 400);
  await page.waitForTimeout(400);
  const after = await page.evaluate(() => window.scrollY);
  expect(after).toBeGreaterThan(before + 100);
});

test('no duplicate-key React errors when loading the default bundle', async ({ page }) => {
  const errs: string[] = [];
  page.on('console', (m) => m.type() === 'error' && errs.push(m.text()));
  await page.goto(url);
  await page.getByTestId('open-provenance').click();
  await page.waitForTimeout(800);
  expect(errs.filter((e) => /same key/.test(e))).toEqual([]);
});

test('South Pole map labels do not overlap', async ({ page }) => {
  await page.goto(`${url}#evidence`);
  await page.getByTestId('status-badge').waitFor();
  const map = page.getByTestId('polar-map');
  await map.scrollIntoViewIfNeeded();
  await page.waitForTimeout(800);
  const boxes = await page.$$eval('.polar-overlay .site-pin text, .polar-overlay .bundle-site text', (els) =>
    els.map((e) => {
      const r = e.getBoundingClientRect();
      return [r.left, r.top, r.right, r.bottom];
    }),
  );
  expect(boxes.length).toBeGreaterThanOrEqual(4);
  for (let i = 0; i < boxes.length; i++)
    for (let j = i + 1; j < boxes.length; j++) {
      const [a, b] = [boxes[i], boxes[j]];
      const overlap = a[0] < b[2] && a[2] > b[0] && a[1] < b[3] && a[3] > b[1];
      expect(overlap, `labels ${i} and ${j} overlap`).toBe(false);
    }
  await map.screenshot({ path: resolve(__dirname, '../../docs/screenshots/06-polar-map-overview.png') });
});
