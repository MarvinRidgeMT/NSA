import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
const __dirname = dirname(fileURLToPath(import.meta.url));
const meta = JSON.parse(readFileSync(resolve(__dirname, '../../public/layers/pgda69/pgda69.json'), 'utf8'));
const shots = resolve(__dirname, '../../docs/screenshots');

test('South Pole map: NASA PGDA 69 layer, regions and zoom', async ({ page }) => {
  await page.goto('/?bundle=demo-fixture.json');
  const map = page.getByTestId('polar-map');
  await map.scrollIntoViewIfNeeded();
  await expect(page.getByTestId('pgda69-badge')).toContainText('NASA PGDA 69');
  const roi6 = meta.rois.find((r: { id: string }) => r.id === 'Site01-ROI6');
  await expect(page.getByTestId('roi-row-Site01-ROI6').locator('td').first()).toHaveAttribute('data-value', String(roi6.sun.mean));
  await page.waitForTimeout(800);
  await map.screenshot({ path: `${shots}/06-polar-map-overview.png` });
  // keyboard: focus the Site01 pin and press Enter
  await page.getByTestId('pin-Site01').focus();
  await page.keyboard.press('Enter');
  await expect(page.getByTestId('polar-area')).toHaveValue('Site01');
  await page.getByTestId('roi-Site01-ROI6').click();
  await expect(page.getByTestId('roi-detail')).toContainText(`${roi6.sun.mean.toFixed(1)} %`);
  await page.getByTestId('layer-earth').check({ force: true });
  await page.waitForTimeout(600);
  await map.screenshot({ path: `${shots}/07-polar-map-site01-earth.png` });
});
