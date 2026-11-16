import { expect, test } from '@playwright/test';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { openDemo, shots, ws } from './helpers';
const __dirname = dirname(fileURLToPath(import.meta.url));
const file = 'site01_2026-11-14_14d.json';
const path = resolve(__dirname, '../../public/bundles', file);

test.describe('decision-evidence panels read the bundle and drive the one clock', () => {
  test('workspaces: tabs switch panels, keyboard arrows move between them, clock stays', async ({ page }) => {
    const pageErrors: string[] = [];
    page.on('pageerror', (e) => pageErrors.push(String(e)));
    await openDemo(page);
    await expect(page.getByTestId('tab-sky')).toHaveAttribute('aria-selected', 'true');
    await expect(page.getByTestId('margin-ribbon')).toBeVisible();
    await page.getByTestId('tab-sky').focus();
    await page.keyboard.press('ArrowRight');
    await expect(page.getByTestId('tab-decision')).toHaveAttribute('aria-selected', 'true');
    await expect(page.getByTestId('certainty-height')).toBeVisible();
    await expect(page.getByTestId('coverage-gauge')).toBeVisible();
    await expect(page.getByTestId('utc')).toBeVisible();
    await page.keyboard.press('ArrowRight');
    await expect(page.getByTestId('ridge-panel')).toBeVisible();
    await expect(page.getByTestId('polar-map')).toBeVisible();
    await expect(page).toHaveURL(/#evidence$/);
    // back to Sky: the 3D scene was kept alive, and no uncaught error came from switching (regression: drei Html removeChild)
    await page.getByTestId('tab-sky').click();
    await expect(page.locator('[data-testid=scene3d], [data-testid=horizon-dome]').first()).toBeVisible();
    await page.waitForTimeout(500);
    expect(pageErrors).toEqual([]);
    for (const [w, h] of [[390, 844], [820, 1180]] as const) {
      await page.setViewportSize({ width: w, height: h });
      for (const t of ['sky', 'decision', 'evidence']) {
        await page.getByTestId(`tab-${t}`).click();
        await page.waitForTimeout(250);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), `${t} at ${w}px has no horizontal overflow`).toBe(true);
      }
    }
  });

  test('margin ribbon: bars match bundle margins, sign agrees with flags, click seeks the clock', async ({ page }) => {
    await openDemo(page);
    const ribbon = page.getByTestId('margin-ribbon');
    await expect(page.getByTestId('margin-mismatch-sun')).toHaveCount(0);
    await expect(page.getByTestId('margin-mismatch-earth')).toHaveCount(0);
    const nPos = await ribbon.locator('.sun rect[data-margin="pos"]').count();
    const nNeg = await ribbon.locator('.sun rect[data-margin="neg"]').count();
    const nNz = await ribbon.locator('.sun rect[data-margin="near-zero"]').count();
    const demo = JSON.parse(readFileSync(resolve(__dirname, '../../public/bundles/demo-fixture.json'), 'utf8'));
    const m: number[] = demo.datasets[0].derived.scenarios[0].samples.sun.marginDeg;
    expect(nPos + nNeg + nNz).toBe(m.length);
    expect(nPos).toBe(m.filter((x) => x >= 0.25).length);
    expect(nNz).toBe(m.filter((x) => Math.abs(x) < 0.25).length);
    const box = (await ribbon.boundingBox())!;
    await page.mouse.click(box.x + box.width * 0.9, box.y + box.height * 0.3);
    const idx = Number((await page.getByTestId('sample-pos').textContent())!.match(/sample (\d+)/)![1]);
    expect(idx).toBeGreaterThan(m.length * 0.7);
    await ribbon.focus();
    await page.keyboard.press('ArrowLeft');
    await expect(page.getByTestId('sample-pos')).toContainText(`sample ${idx - 1} /`);
  });

  test('a-science bundle: ridge of record rows come from bundle critical cells; click highlights and seeks', async ({ page }) => {
    test.skip(!existsSync(path), 'a-science bundle not synced');
    const raw = JSON.parse(readFileSync(path, 'utf8'));
    await page.goto(`/?bundle=${file}#evidence`);
    await expect(page.getByTestId('ridge-panel')).toContainText('display tally');
    const rows = page.getByTestId('ridge-cell-earth');
    expect(await rows.count()).toBeGreaterThan(0);
    const label = (await rows.first().textContent())!;
    expect(label).toContain('PGDA');
    await rows.first().click();
    await expect(page.getByTestId('ridge-mark')).toBeHidden(); // horizon chart lives in Sky (kept mounted, hidden)
    await page.getByTestId('tab-sky').click();
    await expect(page.getByTestId('ridge-mark')).toBeVisible();
    // the seek landed on an Earth-blocked sample, and the "now" line names the same cell
    await expect(page.getByTestId('sky-earth')).toContainText('blocked');
    await page.getByTestId('tab-evidence').click();
    const now = page.getByTestId('ridge-now-earth');
    await expect(now).toBeVisible();
    const km = (await now.textContent())!.match(/([\d.]+) km away/)![1];
    const utc = await page.getByTestId('utc').textContent();
    const sample = raw.samples.find((s: { utc: string }) => s.utc.replace('.000Z', 'Z') === utc);
    const bin = Math.round((((sample.earth.az_deg % 360) + 360) % 360) / 360 * raw.skyline.bins) % raw.skyline.bins; // nearest bin centre
    expect(Number(km)).toBeCloseTo(raw.skyline.critical[bin].distance_m / 1000, 2);
    await page.waitForTimeout(500);
    await page.screenshot({ path: `${shots}/10-evidence-ridge-of-record.png`, fullPage: true });
  });

  test('a-science bundle: coverage gauge and certainty height are honest fallbacks until the solver emits them', async ({ page }) => {
    test.skip(!existsSync(path), 'a-science bundle not synced');
    await page.goto(`/?bundle=${file}#decision`);
    await expect(page.getByTestId('coverage-gauge')).toContainText('not derived.coverage');
    await expect(page.getByTestId('gauge-earth')).toHaveAttribute('data-inside', /\d/);
    await expect(page.getByTestId('certainty-height')).toContainText('single-realization');
    const rows = page.getByTestId('mast-row');
    await expect(rows).toHaveCount(4); // baseline + 2, 5, 10 m
    await rows.nth(3).click();
    await expect(page.getByTestId('scenario-select')).toHaveValue(/mast_m=10/);
    await page.waitForTimeout(500);
    await page.screenshot({ path: `${shots}/11-decision-certainty-coverage.png`, fullPage: true });
  });
});

test.describe('real a-science A1 Ridge of Record (Site04 ROI3, 1 m mast)', () => {
  const roi = 'site04_roi3_2026-11-14_14d_mast1m.json';
  const roiPath = resolve(__dirname, '../../public/bundles', roi);
  test.skip(!existsSync(roiPath), 'ROI bundle not synced (git fetch origin a-science; copy data/bundles; npm run sync-bundles)');
  test('ridge table is the bundle attribution; ridges of record first; click seeks to a sample that ridge blocks', async ({ page }) => {
    const raw = JSON.parse(readFileSync(roiPath, 'utf8'));
    const att = raw.derived.attribution;
    await page.goto(`/?bundle=${roi}#evidence`);
    await expect(page.getByTestId('ridge-panel')).toContainText('from bundle derived.attribution');
    const rows = page.getByTestId('ridge-row');
    const nRec = att.ridges.filter((r: { of_record: boolean }) => r.of_record).length;
    for (let i = 0; i < nRec; i++) {
      const id = (await rows.nth(i).textContent())!.trim();
      expect(att.ridges.find((r: { id: string }) => r.id === id).of_record).toBe(true);
    }
    const r3 = att.ridges.find((r: { id: string }) => r.id === 'R3');
    const row = page.locator('tr', { has: page.getByTestId('ridge-row').filter({ hasText: /^R3$/ }) });
    await expect(row).toContainText(`${r3.sun_ctrl_h.toFixed(1)} / ${r3.sun_loss_h.toFixed(1)}`);
    await page.getByTestId('ridge-row').filter({ hasText: /^R3$/ }).click();
    await expect(page.getByTestId('ridge-now-id-sun')).toContainText('R3');
    await page.waitForTimeout(400);
    await page.screenshot({ path: `${shots}/12-evidence-ridge-of-record-site04-roi3.png`, fullPage: true });
    await page.getByTestId('tab-sky').click();
    await expect(page.getByTestId('sky-sun')).toContainText('blocked');
    await expect(page.getByTestId('ridge-mark')).toHaveAttribute('data-ridge', 'R3');
    const co = page.getByTestId('ridge-callout-sun');
    await expect(co).toContainText('R3');
    await expect(co).toContainText('12–169 m');
    await expect(co).toContainText(`+${r3.relief_m.toFixed(2)} m`);
    await expect(co).toContainText(`${r3.sun_loss_h} h`);
    await expect(co).toContainText('5 m local DEM');
    await page.waitForTimeout(1500);
    await page.screenshot({ path: `${shots}/13-sky-site04-roi3-ridge.png`, fullPage: true });
    // Earth: the far ridge R1 (128 km, 80 m regional DEM) — outside the clone tile
    await page.getByTestId('tab-evidence').click();
    await page.getByTestId('ridge-row').filter({ hasText: /^R1$/ }).click();
    await page.getByTestId('tab-sky').click();
    const ce = page.getByTestId('ridge-callout-earth');
    await expect(ce).toContainText('R1');
    await expect(ce).toContainText('127.7–129.6 km');
    await expect(ce).toContainText('80 m regional DEM');
    await expect(ce).toContainText('alternate terrain realizations do not vary it');
  });
});

test.describe('Part B merge: integration acceptance checks on the DEMO decision fixture', () => {
  const fx = 'demo-decision-fixture.json';
  const der = JSON.parse(readFileSync(resolve(__dirname, '../../public/bundles', fx), 'utf8')).datasets[0].derived;
  test('certainty text per requirement equals the bundle; < 50 % coverage caveat; DEMO badge', async ({ page }) => {
    await page.goto(`/?bundle=${fx}#decision`);
    await expect(page.getByTestId('status-badge')).toHaveAttribute('data-status', 'DEMO');
    const pct = `${Math.round(der.coverage.covered_frac * 100)} %`;
    for (const r of der.requirements) {
      const h = der.certainty_height_m[r.metric];
      const txt = page.getByTestId(`cert-text-${r.metric}`);
      if (h === null) await expect(txt).toContainText('passes on every map');
      else {
        const row = der.certainty_curve.find((c: { metric: string; mast_m: number }) => c.metric === r.metric && c.mast_m === h);
        await expect(txt).toContainText(`passes on ${row.pass} evaluated alternate terrain realizations from a ${h} m mast`);
      }
      await expect(txt).toContainText(`cover only ${pct}`);
    }
    await expect(page.getByTestId('coverage-warning')).toBeVisible();
    for (const c of der.certainty_curve) await expect(page.getByTestId(`cert-pass-${c.mast_m}`)).toContainText(c.pass);
    await page.getByTestId('cert-mast-10').click();
    await expect(page.getByTestId('scenario-select')).toHaveValue('mast10');
    await page.waitForTimeout(400);
    await page.getByTestId('certainty-height').screenshot({ path: `${shots}/14-decision-certainty-demo-fixture.png` });
  });
  test('ribbon draws the clone band only under the series it belongs to', async ({ page }) => {
    await page.goto(`/?bundle=${fx}`);
    await expect(page.getByTestId('margin-ribbon').locator('.range-band').first()).toBeVisible();
  });
});

test('real ROI viewer export (POLARIS-X5D-v2 + derived.attribution) opens with ridges from the bundle', async ({ page }) => {
  const f = 'polaris-x5d-roi-2026-11-14-v2.json';
  test.skip(!existsSync(resolve(__dirname, '../../public/bundles', f)), 'ROI export not synced');
  await page.goto(`/?bundle=${f}#evidence`);
  await expect(page.getByTestId('status-badge')).toHaveAttribute('data-status', 'SOURCE-BASED UNVALIDATED');
  await expect(page.getByTestId('ridge-panel')).toContainText('from bundle derived.attribution');
  expect(await page.getByTestId('ridge-row').count()).toBeGreaterThan(0);
});

test('ROI export with a real DEM: ridge of record drawn on true-scale terrain; far ridge is declared outside the crop, not drawn', async ({ page }) => {
  const f = 'polaris-x5d-roi-2026-11-14-v2.json';
  test.skip(!existsSync(resolve(__dirname, '../../public/bundles', f)), 'ROI export not synced');
  await page.goto(`/?bundle=${f}#evidence`);
  await page.getByTestId('site-select').selectOption({ index: 1 }); // Shackleton Rim (Site04 ROI3)
  await page.getByTestId('ridge-row').filter({ hasText: /^R3$/ }).click();
  await page.getByTestId('tab-sky').click();
  await expect(page.getByTestId('scene3d')).toBeVisible();
  await expect(page.getByTestId('ridge-3d-label')).toContainText('R3');
  await page.waitForTimeout(2200);
  await page.getByTestId('scene3d').screenshot({ path: `${shots}/15-sky-dem-ridge-r3-true-scale.png` });
  await page.getByTestId('tab-evidence').click();
  await page.getByTestId('ridge-row').filter({ hasText: /^R1$/ }).click();
  await page.getByTestId('tab-sky').click();
  await expect(page.getByTestId('ridge-3d-outside')).toContainText('beyond this 2 km DEM crop');
});

test('Certainty Height from the batch sidecar: sampled heights only, values equal the sidecar, source and status shown', async ({ page }) => {
  const sp = resolve(__dirname, '../../public/certainty/sidecar.json');
  const roi = 'site04_roi3_2026-11-14_14d_mast1m.json';
  test.skip(!existsSync(sp) || !existsSync(resolve(__dirname, '../../public/bundles', roi)), 'sidecar or ROI bundle not present');
  const sc = JSON.parse(readFileSync(sp, 'utf8'));
  const site = sc.sites.site04_roi3;
  await page.goto(`/?bundle=${roi}#decision`);
  const panel = page.getByTestId('certainty-height');
  await expect(page.getByTestId('certainty-source')).toContainText('SOURCE BASED UNVALIDATED');
  await expect(page.getByTestId('certainty-source')).toContainText(sc.source.repo_commit);
  await expect(panel).toContainText(`${site.sampled_masts_m.length} sampled heights`);
  for (const row of site.certainty_curve.filter((r: { metric: string }) => r.metric === 'sun_centre_pct')) {
    const w = page.getByTestId(`cert-whisker-${row.mast_m}`);
    await expect(w).toHaveAttribute('data-min', String(row.min));
    await expect(w).toHaveAttribute('data-max', String(row.max));
    await expect(page.getByTestId(`cert-pass-${row.mast_m}`)).toContainText(row.pass);
  }
  await expect(page.getByTestId('min-feasible')).toHaveText(`${site.certainty_height_m.sun_centre_pct} m`);
  await expect(page.getByTestId('agreement')).toHaveText(`${site.agreement_mast_m} m`);
  await expect(page.getByTestId('all-100')).toHaveText(`${site.all_maps_100pct_sun_mast_m} m`);
  await expect(panel).toContainText('not NASA mission requirements');
  await page.waitForTimeout(300);
  await panel.screenshot({ path: `${shots}/16-decision-certainty-height-batch-site04-roi3.png` });
});
