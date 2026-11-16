// One-off WCAG scan (axe-core 4.14, tags wcag2a/aa + wcag21aa) of the built POLARIS viewer at http://127.0.0.1:4173.
// Not part of the repo test suite (it would add a dependency). Writes axe_results.json.
import { chromium } from '/home/claude/rc/web/node_modules/playwright/index.mjs';
import { readFileSync, writeFileSync } from 'node:fs';
const AXE = readFileSync('/home/claude/axe/node_modules/axe-core/axe.min.js', 'utf8');
const B = 'polaris-x5d-roi-2026-11-14-v2.json';
const views = [
  ['cold launch (default)', '/', 1440, 900],
  ['decision Site04 ROI3', `/?bundle=${B}&site=site04_roi3#decision`, 1440, 900],
  ['decision Site01 ROI6', `/?bundle=${B}&site=site01_roi6#decision`, 1440, 900],
  ['explorer Site04 ROI3', `/?bundle=${B}&site=site04_roi3#sky`, 1440, 900],
  ['evidence Site04 ROI3', `/?bundle=${B}&site=site04_roi3#evidence`, 1440, 900],
  ['missing bundle error', '/?bundle=does_not_exist_2026.json#sky', 1440, 900],
  ['decision phone', `/?bundle=${B}&site=site04_roi3#decision`, 390, 844],
  ['explorer phone', `/?bundle=${B}&site=site04_roi3#sky`, 390, 844],
];
const browser = await chromium.launch({ executablePath: process.env.CHROME, args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'] });
const out = [];
for (const [name, path, w, h] of views) {
  const page = await browser.newPage({ viewport: { width: w, height: h } });
  await page.goto('http://127.0.0.1:4173' + path);
  await page.waitForTimeout(6000);
  await page.addScriptTag({ content: AXE });
  // open every <details> so collapsed text is scanned too
  await page.evaluate(() => document.querySelectorAll('details').forEach((d) => (d.open = true)));
  await page.waitForTimeout(500);
  const r = await page.evaluate(async () => {
    const res = await window.axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'] } });
    return { violations: res.violations.map((v) => ({ id: v.id, impact: v.impact, help: v.help, nodes: v.nodes.slice(0, 8).map((n) => ({ target: n.target.join(' '), summary: n.failureSummary?.slice(0, 300) })), n: v.nodes.length })),
      passes: res.passes.length, incomplete: res.incomplete.map((v) => ({ id: v.id, n: v.nodes.length })) };
  });
  out.push({ name, path, viewport: [w, h], ...r });
  console.log(name, '| violations', r.violations.map((v) => `${v.id}(${v.impact}) x${v.n}`).join(', ') || 'none', '| incomplete', r.incomplete.map((v) => `${v.id} x${v.n}`).join(', '));
  await page.close();
}
await browser.close();
writeFileSync('/home/claude/axe/axe_results.json', JSON.stringify(out, null, 1));
