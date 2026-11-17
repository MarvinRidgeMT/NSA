import { expect, test, type Page } from '@playwright/test';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

/**
 * Gates (prompt §7, docs/v2/GATES.md): accessibility scan and 390 px mobile layout. Records numbers to
 * docs/v2/gates/{a11y,mobile}-<date>.json and FAILS when a gate fails (failures are listed for the web owner, T2;
 * this file does not change the UI). Views: story landing, Explore (+ globe open), Decision, Evidence.
 */
const here = dirname(fileURLToPath(import.meta.url));
const OUT = resolve(here, '../../../docs/v2/gates');
const day = new Date().toISOString().slice(0, 10);
const VIEWS: { id: string; url: string; globe?: boolean }[] = [
  { id: 'story', url: '/' },
  { id: 'explore', url: '/#sky' },
  { id: 'explore+globe', url: '/#sky', globe: true },
  { id: 'decision', url: '/#decision' },
  { id: 'evidence', url: '/#evidence' },
];

function axeSource(): { src: string; path: string; from: string } | null {
  const candidates: [string | undefined, string][] = [[process.env.AXE_CORE_PATH, 'AXE_CORE_PATH'], [resolve(here, '../../node_modules/axe-core/axe.min.js'), 'web/node_modules']];
  for (const [p, from] of candidates) if (p && existsSync(p)) return { src: readFileSync(p, 'utf8'), path: p, from };
  return null;
}

async function open(page: Page, v: { url: string; globe?: boolean }) {
  await page.goto(v.url);
  await page.waitForLoadState('networkidle').catch(() => {});
  if (v.url.includes('#sky')) await page.waitForSelector('[data-testid=scene3d]', { timeout: 60_000 }).catch(() => {});
  if (v.globe) {
    await page.click('[data-testid=globe-open]');
    await page.waitForSelector('[data-testid=global-moon]', { timeout: 60_000 });
  }
  await page.waitForTimeout(800);
}

/** Lite scan (used when axe-core is not available): WCAG 2.2 A/AA checks that need no rendering analysis. */
async function liteScan(page: Page) {
  return page.evaluate(() => {
    const vis = (el: Element) => { const s = getComputedStyle(el); const r = el.getBoundingClientRect(); return s.display !== 'none' && s.visibility !== 'hidden' && r.width > 0 && r.height > 0; };
    const desc = (el: Element) => `${el.tagName.toLowerCase()}${el.id ? '#' + el.id : ''}${(el as HTMLElement).dataset?.testid ? `[data-testid=${(el as HTMLElement).dataset.testid}]` : ''}`;
    const name = (el: Element) => {
      const lb = el.getAttribute('aria-labelledby');
      if (lb) return lb.split(/\s+/).map((i) => document.getElementById(i)?.textContent ?? '').join(' ').trim();
      if (el.getAttribute('aria-label')) return el.getAttribute('aria-label')!.trim();
      const id = el.id && document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
      if (id) return (id.textContent ?? '').trim();
      const wrap = el.closest('label');
      if (wrap && wrap !== el) return (wrap.textContent ?? '').trim();
      if (el instanceof HTMLImageElement) return el.alt;
      if (el instanceof HTMLInputElement && ['button', 'submit'].includes(el.type)) return el.value;
      return ((el.textContent ?? '').trim() || el.getAttribute('title') || '').trim();
    };
    const v: { rule: string; impact: string; nodes: string[] }[] = [];
    const add = (rule: string, impact: string, nodes: string[]) => { if (nodes.length) v.push({ rule, impact, nodes: nodes.slice(0, 12) }); };
    add('html-has-lang', 'serious', document.documentElement.lang ? [] : ['html']);
    add('document-title', 'serious', document.title.trim() ? [] : ['title']);
    add('image-alt', 'critical', [...document.querySelectorAll('img')].filter((i) => vis(i) && !i.hasAttribute('alt')).map(desc));
    add('button-name', 'critical', [...document.querySelectorAll('button,[role=button]')].filter((b) => vis(b) && !name(b)).map(desc));
    add('link-name', 'serious', [...document.querySelectorAll('a[href]')].filter((a) => vis(a) && !name(a)).map(desc));
    add('label', 'critical', [...document.querySelectorAll('input:not([type=hidden]),select,textarea')].filter((i) => vis(i) && !name(i)).map(desc));
    const ids = new Map<string, number>();
    document.querySelectorAll('[id]').forEach((e) => ids.set(e.id, (ids.get(e.id) ?? 0) + 1));
    add('duplicate-id', 'minor', [...ids].filter(([, n]) => n > 1).map(([i]) => `#${i}`));
    add('landmark-one-main', 'moderate', document.querySelectorAll('main,[role=main]').length === 1 ? [] : [`main x${document.querySelectorAll('main,[role=main]').length}`]);
    add('canvas-no-text-alternative', 'moderate', [...document.querySelectorAll('canvas')].filter((c) => vis(c) && !c.getAttribute('aria-label') && !c.closest('[aria-label],[role=img]') && !c.textContent?.trim()).map(desc));
    add('tabindex-positive', 'serious', [...document.querySelectorAll('[tabindex]')].filter((e) => Number(e.getAttribute('tabindex')) > 0).map(desc));
    return v;
  });
}

test('gate: accessibility scan', async ({ page }) => {
  const axe = axeSource();
  const views: Record<string, unknown> = {};
  let serious = 0;
  for (const v of VIEWS) {
    await open(page, v);
    if (axe) {
      await page.addScriptTag({ content: axe.src });
      const r = await page.evaluate(async () => {
        // @ts-expect-error axe is injected
        const res = await window.axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'] } });
        return { violations: res.violations.map((x: { id: string; impact: string; nodes: { target: string[] }[]; help: string }) => ({ rule: x.id, impact: x.impact, help: x.help, n: x.nodes.length, nodes: x.nodes.slice(0, 8).map((n) => n.target.join(' ')) })), passes: res.passes.length, incomplete: res.incomplete.length };
      });
      views[v.id] = r;
      serious += r.violations.filter((x) => x.impact === 'serious' || x.impact === 'critical').length;
    } else {
      const r = await liteScan(page);
      views[v.id] = { violations: r };
      serious += r.filter((x) => x.impact === 'serious' || x.impact === 'critical').length;
    }
  }
  mkdirSync(OUT, { recursive: true });
  const file = resolve(OUT, `a11y-${axe ? 'axe' : 'lite'}-${day}.json`);
  writeFileSync(file, JSON.stringify({ schema: 'polaris-gates-a11y-v1', measuredUTC: new Date().toISOString(), engine: axe ? `axe-core (${axe.from})` : 'lite scan (axe-core not in web/node_modules)', axeVersion: axe ? (axe.src.match(/axe v([\d.]+)/)?.[1] ?? null) : null, rule: 'pass = 0 serious/critical violations across views', seriousOrCritical: serious, views }, null, 2) + '\n');
  expect(serious, `serious/critical accessibility violations (see ${file})`).toBe(0);
});

test('gate: mobile layout at 390 px', async ({ browser }) => {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 3, isMobile: true, hasTouch: true });
  const page = await ctx.newPage();
  const views: Record<string, unknown> = {};
  let failures = 0;
  for (const v of VIEWS) {
    await open(page, v);
    const r = await page.evaluate(() => {
      const W = window.innerWidth;
      const vis = (el: Element) => { const s = getComputedStyle(el); const b = el.getBoundingClientRect(); return s.display !== 'none' && s.visibility !== 'hidden' && b.width > 0 && b.height > 0; };
      const desc = (el: Element) => `${el.tagName.toLowerCase()}${(el as HTMLElement).dataset?.testid ? `[data-testid=${(el as HTMLElement).dataset.testid}]` : ''}${el.className && typeof el.className === 'string' ? '.' + el.className.split(' ')[0] : ''}`;
      const scrollW = document.scrollingElement!.scrollWidth;
      const interactive = [...document.querySelectorAll('button,a[href],input,select,textarea,[role=tab],[role=button]')].filter(vis);
      // clipped = sticks out of the viewport horizontally and no scrollable ancestor can bring it into view
      const scrollableX = (el: Element) => { for (let p = el.parentElement; p; p = p.parentElement) { const s = getComputedStyle(p); if (/(auto|scroll)/.test(s.overflowX) && p.scrollWidth > p.clientWidth) return true; } return false; };
      const out = (e: Element) => { const b = e.getBoundingClientRect(); return (b.right > W + 1 || b.left < -1) && !scrollableX(e); };
      // a skip link is off-screen by design until focused: re-test every off-screen control after focusing it
      const offscreen = interactive.filter((e) => { if (!out(e)) return false; (e as HTMLElement).focus?.(); const still = out(e); (e as HTMLElement).blur?.(); return still; }).map(desc);
      // squeezed layout: a visible h1/h2 laid out in less than half the viewport width while wrapping onto 3+ lines
      const squeezed = [...document.querySelectorAll('main h1, main h2')].filter((h) => { if (!vis(h)) return false; const b = h.getBoundingClientRect(); const lh = parseFloat(getComputedStyle(h).lineHeight) || parseFloat(getComputedStyle(h).fontSize) * 1.2; return b.width < W * 0.5 && b.height > 2.5 * lh; }).map((h) => `${desc(h)} ${Math.round(h.getBoundingClientRect().width)}px wide: ${(h.textContent ?? '').trim().slice(0, 40)}`);
      const small = interactive.filter((e) => { const b = e.getBoundingClientRect(); return (b.width < 24 || b.height < 24) && !(e instanceof HTMLInputElement && ['checkbox', 'radio'].includes(e.type)); }).map((e) => { const b = e.getBoundingClientRect(); return `${desc(e)} ${Math.round(b.width)}x${Math.round(b.height)}`; });
      const tinyText = [...document.querySelectorAll('body *')].filter((e) => vis(e) && e.childNodes.length && [...e.childNodes].some((n) => n.nodeType === 3 && n.textContent!.trim()) && parseFloat(getComputedStyle(e).fontSize) < 11).map(desc);
      return { squeezedHeadings: squeezed, innerWidth: W, scrollWidth: scrollW, horizontalScroll: scrollW > W + 1, nInteractive: interactive.length, offscreenInteractive: offscreen.slice(0, 15), nOffscreen: offscreen.length, targetsUnder24px: small.slice(0, 15), nTargetsUnder24px: small.length, textUnder11px: [...new Set(tinyText)].slice(0, 15), nTextUnder11px: tinyText.length };
    });
    const checks = { noHorizontalScroll: !r.horizontalScroll, interactiveReachable: r.nOffscreen === 0, noSqueezedHeadings: r.squeezedHeadings.length === 0, targets24px: r.nTargetsUnder24px === 0, text11px: r.nTextUnder11px === 0 };
    const fail = Object.values(checks).filter((x) => !x).length;
    failures += checks.noHorizontalScroll && checks.interactiveReachable && checks.noSqueezedHeadings ? 0 : 1;   // gate = layout usable; target/text sizes recorded
    views[v.id] = { ...r, checks };
    mkdirSync(OUT, { recursive: true });
    await page.screenshot({ path: resolve(OUT, `mobile-390-${v.id.replace('+', '-')}.png`) });
    if (fail) console.log(`mobile ${v.id}:`, JSON.stringify(checks));
  }
  writeFileSync(resolve(OUT, `mobile-${day}.json`), JSON.stringify({ schema: 'polaris-gates-mobile-v1', measuredUTC: new Date().toISOString(), viewport: [390, 844], deviceScaleFactor: 3, rule: 'pass = no horizontal page scroll and every visible control inside the viewport (or inside a horizontally scrollable container, or brought into view by focus) and no h1/h2 squeezed below half the width onto 3+ lines, in every view; 24 px targets (WCAG 2.2 AA 2.5.8) and >= 11 px text are recorded', views }, null, 2) + '\n');
  await ctx.close();
  expect(failures, 'views failing the 390 px layout gate (see docs/v2/gates/mobile-*.json)').toBe(0);
});
