import { expect, test, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));

/**
 * Final Apex P1 (15 Nov 2026): cold launch and production consistency.
 * Every failure of bundles/index.json or of the chosen bundle shows a specific message with Retry and never substitutes a demo
 * or another bundle; Retry recovers once the file is back; direct URLs and refresh keep the workspace.
 */
const INDEX = /\/bundles\/index\.json(\?.*)?$/;
const HERO = /\/bundles\/polaris-x5d-roi-[^/]*\.json(\?.*)?$/;

async function expectNoSubstitute(page: Page) {
  await expect(page.getByTestId('instrument')).toHaveCount(0);
  await expect(page.getByTestId('demo-banner')).toHaveCount(0);
}

test('missing bundles/index.json: clear error, Retry, no demo fallback; Retry recovers when the file is back', async ({ page }) => {
  let fail = true;
  await page.route(INDEX, (r) => (fail ? r.fulfill({ status: 404, contentType: 'text/html', body: 'Not found' }) : r.continue()));
  await page.goto('/#sky');
  await expect(page.getByTestId('load-fail')).toContainText('The viewer could not start');
  await expect(page.getByTestId('load-error')).toContainText('HTTP 404');
  await expect(page.getByTestId('load-fail')).toContainText('none is substituted');
  await expectNoSubstitute(page);
  fail = false;
  await page.getByTestId('load-retry').click();
  await expect(page.getByTestId('load-fail')).toHaveCount(0);
  await expect(page.getByTestId('instrument')).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId('demo-banner')).toHaveCount(0);
});

test('index answered with a web page (wrong folder / SPA fallback) is named as such', async ({ page }) => {
  await page.route(INDEX, (r) => r.fulfill({ status: 200, contentType: 'text/html', body: '<!DOCTYPE html><html><body>app</body></html>' }));
  await page.goto('/#sky');
  await expect(page.getByTestId('load-error')).toContainText('wrong folder');
  await expectNoSubstitute(page);
});

test('invalid or empty index: specific messages, still no substitute', async ({ page }) => {
  await page.route(INDEX, (r) => r.fulfill({ status: 200, contentType: 'application/json', body: '{"bundles": [' }));
  await page.goto('/#sky');
  await expect(page.getByTestId('load-error')).toContainText('not valid JSON');
  await expectNoSubstitute(page);
  await page.unroute(INDEX);
  await page.route(INDEX, (r) => r.fulfill({ status: 200, contentType: 'application/json', body: '{"bundles": []}' }));
  await page.getByTestId('load-retry').click();
  await expect(page.getByTestId('load-error')).toContainText('lists no bundles');
  await expectNoSubstitute(page);
});

test('missing bundle: the index is fine but the hero bundle 404s; Retry reloads the same bundle, not another one', async ({ page }) => {
  let fail = true;
  const asked: string[] = [];
  page.on('request', (q) => {
    if (/\/bundles\/[^/]+\.json/.test(q.url()) && !INDEX.test(q.url())) asked.push(q.url().split('/').pop()!.split('?')[0]);
  });
  await page.route(HERO, (r) => (fail ? r.fulfill({ status: 404, body: '' }) : r.continue()));
  await page.goto('/#sky');
  await expect(page.getByTestId('load-error')).toContainText('was not found (HTTP 404)');
  await expectNoSubstitute(page);
  expect(new Set(asked).size).toBe(1); // only the hero was requested: nothing else was tried in its place
  fail = false;
  await page.getByTestId('load-retry').click();
  await expect(page.getByTestId('instrument')).toBeVisible({ timeout: 30_000 });
  expect(new Set(asked).size).toBe(1);
});

test('direct URL to a workspace and a refresh keep the workspace and the same bundle', async ({ page }) => {
  await page.goto('/#decision');
  await expect(page.getByTestId('decision-card')).toBeVisible({ timeout: 30_000 });
  const before = await page.getByTestId('bundle-select').inputValue();
  await page.reload();
  await expect(page.getByTestId('decision-card')).toBeVisible({ timeout: 30_000 });
  expect(await page.getByTestId('bundle-select').inputValue()).toBe(before);
  await expect(page.getByTestId('load-fail')).toHaveCount(0);
});

test('the served build is the one on disk, and 127.0.0.1 and localhost reach the same server', async ({ page, request }) => {
  // Guards against a stale server left on the port (the old cold-launch symptom): the page must load the asset that dist/ holds now.
  const disk = readFileSync(resolve(here, '../../dist/index.html'), 'utf8').match(/assets\/index-[\w-]+\.js/)?.[0];
  expect(disk).toBeTruthy();
  for (const host of ['http://127.0.0.1:4173', 'http://localhost:4173']) {
    const html = await (await request.get(`${host}/`)).text();
    expect(html.match(/assets\/index-[\w-]+\.js/)?.[0], host).toBe(disk);
    const idx = await request.get(`${host}/bundles/index.json`);
    expect(idx.status(), host).toBe(200);
    expect(await idx.text()).toBe(readFileSync(resolve(here, '../../dist/bundles/index.json'), 'utf8'));
  }
  await page.goto('http://127.0.0.1:4173/#sky');
  await expect(page.getByTestId('instrument')).toBeVisible({ timeout: 30_000 });
});
