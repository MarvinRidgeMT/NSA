import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const index = JSON.parse(readFileSync(resolve(__dirname, '../../public/bundles/index.json'), 'utf8')) as {
  bundles: { file: string }[];
};
const reportOnly = process.env.TRACEABILITY_REPORT_ONLY === '1';

type Failure = { tag: string; text: string; trace: string | null; labels: string[] };

test('all rendered main-workspace numbers with units carry source and classification traceability', async ({ page }) => {
  const failures: { bundle: string; items: Failure[] }[] = [];
  let scanned = 0;

  for (const entry of index.bundles) {
    await page.goto(`/?bundle=${encodeURIComponent(entry.file)}`);
    await expect(page.getByTestId('bundle-select')).toHaveValue(entry.file);
    const result = await page.locator('main').evaluate((main) => {
      const pattern = /(?:^|[\s(≥≤+−–/:])[-+−]?\d+(?:\.\d+)?(?:\s*[–-]\s*[-+−]?\d+(?:\.\d+)?)?\s*(?:%|h|m|°)(?=$|[\s,.;)·/])/u;
      const allowed = new Set(['SOURCE-BASED', 'VALIDATED', 'SCENARIO', 'DEMO']);
      const visible = (element: Element) => {
        const style = getComputedStyle(element);
        const rect = element.getBoundingClientRect();
        return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
      };
      const matches = (element: Element) => pattern.test((element.textContent ?? '').replace(/\s+/g, ' ').trim());
      const candidates = Array.from(main.querySelectorAll('*')).filter(
        (element) => visible(element) && matches(element) && !Array.from(element.children).some(matches),
      );
      const items: Failure[] = [];
      for (const element of candidates) {
        let node: Element | null = element;
        let trace: string | null = null;
        const labels: string[] = [];
        while (node && node !== main.parentElement) {
          if (!trace) trace = node.getAttribute('data-result-id') ?? node.getAttribute('data-source');
          for (const name of ['data-label', 'data-classification']) {
            const value = node.getAttribute(name);
            if (value) labels.push(value);
          }
          node = node.parentElement;
        }
        const classified = labels.some((label) =>
          Array.from(allowed).some((allowedLabel) => label === allowedLabel || label.includes(allowedLabel)),
        );
        if (!trace || !classified) {
          items.push({
            tag: element.tagName.toLowerCase(),
            text: (element.textContent ?? '').replace(/\s+/g, ' ').trim().slice(0, 180),
            trace,
            labels: Array.from(new Set(labels)),
          });
        }
      }
      return { scanned: candidates.length, items };
    });
    scanned += result.scanned;
    if (result.items.length) failures.push({ bundle: entry.file, items: result.items });
  }

  const failed = failures.reduce((total, bundle) => total + bundle.items.length, 0);
  console.log(`TRACEABILITY_SCAN scanned=${scanned} failed=${failed} bundles=${index.bundles.length}`);
  if (failures.length) console.log(JSON.stringify(failures, null, 2));
  if (!reportOnly) expect(failures).toEqual([]);
});
