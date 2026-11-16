import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
const __dirname = dirname(fileURLToPath(import.meta.url));
import type { Page } from '@playwright/test';

export const demo = JSON.parse(readFileSync(resolve(__dirname, '../../public/bundles/demo-fixture.json'), 'utf8'));
export const demoTimes: string[] = demo.datasets[0].ephemeris.samples.map((s: { time: string }) => s.time);
export const scenario = (id: string) => demo.datasets[0].derived.scenarios.find((s: { id: string }) => s.id === id);
export const shots = resolve(__dirname, '../../docs/screenshots');

export async function openDemo(page: Page) {
  await page.goto('/?bundle=demo-fixture.json');
  await page.getByTestId('status-badge').waitFor();
}

/** switch workspace (Sky / Decision / Evidence); the clock and selectors stay above the tabs */
export async function ws(page: Page, id: 'sky' | 'decision' | 'evidence') {
  await page.getByTestId(`tab-${id}`).click();
  await page.locator(`#ws-${id}`).waitFor();
}

export async function goTo(page: Page, iso: string) {
  const inp = page.getByTestId('utc-input');
  await inp.fill(iso);
  await inp.press('Enter');
}
