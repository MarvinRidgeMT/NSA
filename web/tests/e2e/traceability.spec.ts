import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const index = JSON.parse(readFileSync(resolve(__dirname, '../../public/bundles/index.json'), 'utf8')) as {
  bundles: { file: string; status: string }[];
};
const reportOnly = process.env.TRACEABILITY_REPORT_ONLY === '1';

type LabelValue = 'SOURCE-BASED' | 'VALIDATED' | 'SCENARIO' | 'DEMO';
type Failure = { tag: string; text: string; trace: string | null; labels: string[] };
type ScanResult = {
  scanned: number;
  items: Failure[];
  labelCounts: Record<LabelValue, number>;
  sourceCounts: Record<string, number>;
  demoMislabels: Failure[];
};

test('all rendered main-workspace numbers with units carry honest source and classification traceability', async ({ page }) => {
  const failures: { bundle: string; items: Failure[] }[] = [];
  const demoMislabels: { bundle: string; items: Failure[] }[] = [];
  const labelCounts: Record<LabelValue, number> = { 'SOURCE-BASED': 0, VALIDATED: 0, SCENARIO: 0, DEMO: 0 };
  const sourceCounts = new Map<string, number>();
  let scanned = 0;

  for (const entry of index.bundles) {
    await page.goto(`/?bundle=${encodeURIComponent(entry.file)}`);
    await expect(page.getByTestId('bundle-select')).toHaveValue(entry.file);
    const result = await page.locator('main').evaluate((main): ScanResult => {
      const pattern = /(?:^|[\s(≥≤+−–/:])[-+−]?\d+(?:\.\d+)?(?:\s*[–-]\s*[-+−]?\d+(?:\.\d+)?)?\s*(?:%|h|m|°)(?=$|[\s,.;)·/])/u;
      const classify = (value: string): LabelValue | null => {
        const normalized = value.toUpperCase();
        if (normalized.includes('DEMO')) return 'DEMO';
        if (normalized.includes('SCENARIO')) return 'SCENARIO';
        if (normalized.includes('SOURCE-BASED') || normalized.includes('SOURCE_BASED')) return 'SOURCE-BASED';
        if (normalized === 'VALIDATED' || normalized.includes('VALIDATED_NASA_JPL')) return 'VALIDATED';
        return null;
      };
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
      const badDemo: Failure[] = [];
      const counts: Record<LabelValue, number> = { 'SOURCE-BASED': 0, VALIDATED: 0, SCENARIO: 0, DEMO: 0 };
      const sources: Record<string, number> = {};
      const bundleIsDemo = classify(main.getAttribute('data-classification') ?? '') === 'DEMO';

      for (const element of candidates) {
        let node: Element | null = element;
        let trace: string | null = null;
        let source: string | null = null;
        let classification: LabelValue | null = null;
        const labels: string[] = [];
        while (node && node !== main.parentElement) {
          if (!trace) trace = node.getAttribute('data-result-id') ?? node.getAttribute('data-source');
          if (!source) source = node.getAttribute('data-source');
          for (const name of ['data-label', 'data-classification']) {
            const value = node.getAttribute(name);
            if (value) {
              labels.push(value);
              if (!classification) classification = classify(value);
            }
          }
          node = node.parentElement;
        }
        const failure = {
          tag: element.tagName.toLowerCase(),
          text: (element.textContent ?? '').replace(/\s+/g, ' ').trim().slice(0, 180),
          trace,
          labels: Array.from(new Set(labels)),
        };
        if (!trace || !classification) items.push(failure);
        if (classification) counts[classification] += 1;
        if (source) sources[source] = (sources[source] ?? 0) + 1;

        // A synthetic fixture may have a local SCENARIO marker, but it must never
        // acquire a source-backed or validated claim anywhere in its ancestry.
        if (
          bundleIsDemo &&
          labels.some((label) => {
            const value = classify(label);
            return value === 'SOURCE-BASED' || value === 'VALIDATED';
          })
        ) {
          badDemo.push(failure);
        }
      }
      return { scanned: candidates.length, items, labelCounts: counts, sourceCounts: sources, demoMislabels: badDemo };
    });
    scanned += result.scanned;
    for (const label of Object.keys(labelCounts) as LabelValue[]) labelCounts[label] += result.labelCounts[label];
    for (const [source, count] of Object.entries(result.sourceCounts)) sourceCounts.set(source, (sourceCounts.get(source) ?? 0) + count);
    if (result.items.length) failures.push({ bundle: entry.file, items: result.items });
    if (result.demoMislabels.length) demoMislabels.push({ bundle: entry.file, items: result.demoMislabels });
  }

  const failed = failures.reduce((total, bundle) => total + bundle.items.length, 0);
  const topSources = Array.from(sourceCounts, ([source, count]) => ({ source, count }))
    .sort((a, b) => b.count - a.count || a.source.localeCompare(b.source))
    .slice(0, 10);
  console.log(`TRACEABILITY_SCAN scanned=${scanned} failed=${failed} bundles=${index.bundles.length}`);
  console.table(Object.entries(labelCounts).map(([label, count]) => ({ label, count })));
  console.table(topSources);
  if (failures.length) console.log(JSON.stringify(failures, null, 2));
  if (demoMislabels.length) console.log(JSON.stringify(demoMislabels, null, 2));
  if (!reportOnly) {
    expect(failures).toEqual([]);
    expect(demoMislabels).toEqual([]);
  }
});

test('DEMO fixture numbers are never labelled SOURCE-BASED or VALIDATED', async ({ page }) => {
  await page.goto('/?bundle=demo-fixture.json');
  await expect(page.getByTestId('bundle-select')).toHaveValue('demo-fixture.json');
  const main = page.locator('main');
  await expect(main).toHaveAttribute('data-classification', 'DEMO');
  const forbidden = main.locator(
    '[data-label*="SOURCE-BASED"], [data-label="VALIDATED"], [data-classification*="SOURCE-BASED"], [data-classification="VALIDATED"]',
  );
  await expect(forbidden).toHaveCount(0);
  await expect(main.getByText(/\d+(?:\.\d+)?\s*(?:%|h|m|°)/).first()).toBeVisible();
});
