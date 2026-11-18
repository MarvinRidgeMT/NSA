// S12: screenshots in Google Chrome on this Mac (GPU via ANGLE/Metal) into ../tmp/s12 (git-ignored), with the checks that
// need a real GPU logged beside them. Display check only.
//   cd web && npm run dev
//   node scripts/s12_shots.mjs [base URL, default http://127.0.0.1:5174/]
import { existsSync, mkdirSync } from 'node:fs';
import { chromium } from '@playwright/test';

const base = process.argv[2] ?? 'http://127.0.0.1:5174/';
const only = process.argv[3] ?? '';
const out = '../tmp/s12';
mkdirSync(out, { recursive: true });
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const browser = await chromium.launch({ headless: false, executablePath: existsSync(CHROME) ? CHROME : undefined, args: ['--use-angle=metal', '--ignore-gpu-blocklist'] });
const cases = [
  ['1440x900', { viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 }],
  ['reduced-1440x900', { viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2, reducedMotion: 'reduce' }],
  ['390x844', { viewport: { width: 390, height: 844 }, deviceScaleFactor: 3, hasTouch: true, isMobile: true }],
].filter(([n]) => !only || n.includes(only));
const camDir = (page) => page.evaluate(() => { const c = window.__polarisGlobe.camera.position; const l = c.length(); return [c.x / l, c.y / l, c.z / l, l].map((x) => +x.toFixed(4)); });
const cam = (page) => page.evaluate(() => { const s = window.__polarisScene; return [...s.camera.position.toArray(), ...s.controls.target.toArray(), s.camera.fov, s.camera.view?.enabled ? 1 : 0]; });
for (const [name, opts] of cases) {
  const ctx = await browser.newContext(opts);
  const page = await ctx.newPage();
  page.on('pageerror', (e) => console.log(name, 'PAGE ERROR', e.message));
  page.on('console', (m) => m.type() === 'error' && console.log(name, 'console error', m.text().slice(0, 200)));
  const shot = (what) => page.screenshot({ path: `${out}/${what}-${name}.png` });
  const touch = !!opts.hasTouch;
  await page.goto(`${base}?mode=simple`);
  await page.waitForSelector('[data-testid=simple-globe][data-shown=true][data-first-frame-ms]', { timeout: 60_000 });
  await page.waitForSelector('[data-testid=simple-mode]:not([data-intro])', { timeout: 60_000 });
  await page.waitForSelector('[data-testid=simple-globe]:not([data-upgrade])', { timeout: 90_000 }).catch(() => console.log(name, 'upgrade still pending'));
  await page.waitForTimeout(1500);
  const globe = page.getByTestId('simple-globe');
  const vb = await page.locator('.s-globe-view').boundingBox();
  const cx = vb.x + vb.width / 2 + (opts.viewport.width >= 1024 ? 60 : 0);
  const cy = vb.y + vb.height / 2;
  console.log(name, 'asset', await globe.getAttribute('data-asset'), 'home', await camDir(page), 'zoomMin', await page.evaluate(() => +window.__polarisGlobe.nav.zoomMin.toFixed(3)));
  await shot('globe-rest');
  if (!touch) {
    // drag: the Moon follows the pointer; held mid-drag for the picture
    await page.mouse.move(cx, cy);
    await page.mouse.down();
    await page.mouse.move(cx + 190, cy - 70, { steps: 12 });
    await page.waitForTimeout(120);
    console.log(name, 'mid-drag', await globe.getAttribute('data-dragging'), await camDir(page));
    await shot('globe-mid-drag');
    await page.mouse.up();
    await page.waitForTimeout(900);
    console.log(name, 'after release (glide)', await camDir(page), 'moved', await globe.getAttribute('data-moved'));
    // zoom in to the limit of the model on screen
    for (let i = 0; i < 30; i++) await page.mouse.wheel(0, -120);
    await page.waitForTimeout(700);
    console.log(name, 'zoomed', await page.evaluate(() => [window.__polarisGlobe.nav.zoomNow, window.__polarisGlobe.nav.zoomMin].map((x) => +x.toFixed(3))), await camDir(page));
    await shot('globe-zoom-limit');
    await page.mouse.move(cx, cy - 200);
    await shot('globe-back-to-pole-button');
    await page.getByTestId('globe-home').click();
    await page.waitForTimeout(reducedWait(opts, 1000));
    console.log(name, 'back at pole', await camDir(page), 'moved', await globe.getAttribute('data-moved'));
    await shot('globe-back-to-pole');
    // a drag that ends on a pin is not a click on it
    const pb = await page.locator('.s-globe-pin button').nth(1).boundingBox();
    await page.mouse.move(pb.x + pb.width / 2 + 160, pb.y + pb.height / 2 + 40);
    await page.mouse.down();
    await page.mouse.move(pb.x + pb.width / 2, pb.y + pb.height / 2, { steps: 10 });
    await page.mouse.up();
    await page.waitForTimeout(400);
    console.log(name, 'after drag onto a pin: place', await page.getByTestId('simple-mode').getAttribute('data-place'));
    await page.getByTestId('globe-pad').focus();
    await page.keyboard.press('Home');
    await page.waitForTimeout(1200);
    // keyboard: the pad takes focus, arrows turn
    await page.getByTestId('globe-pad').focus();
    await page.keyboard.press('ArrowRight');
    await page.keyboard.press('ArrowRight');
    await page.keyboard.press('+');
    await page.waitForTimeout(600);
    console.log(name, 'keys', await camDir(page));
    await shot('globe-keyboard-focus');
    await page.keyboard.press('Home');
    await page.waitForTimeout(1000);
  } else {
    await shot('globe-phone');
  }
  // fly to the story site
  const pin = page.locator('[data-testid=globe-pin-site04_roi3] button');
  if (touch) await pin.tap();
  else await pin.click();
  await page.waitForSelector('[data-testid=simple-mode][data-place=site]', { timeout: 15_000 });
  await page.waitForSelector('[data-testid=scene3d][data-context=loaded]', { timeout: 45_000 }).catch(() => console.log(name, 'no terrain context'));
  await page.waitForFunction(() => !!window.__polarisScene, null, { timeout: 30_000 });
  await page.waitForTimeout(3500);
  await shot('site-arrival');
  const home = await cam(page);
  const ids = await page.locator('[data-testid^=scene-object-]').evaluateAll((els) => els.map((e) => e.getAttribute('data-object')));
  console.log(name, 'objects', ids.join(', '));
  for (const id of ids) {
    const at = await page.evaluate((i) => window.__polarisScene.screen(i), id);
    const stage = await page.locator('.simple-stage canvas').first().boundingBox();
    const x = stage.x + at.x;
    const y = stage.y + at.y;
    const key = id.replace(':', '-');
    // an object out of the picture, or under a panel, is reached from the "Look at" row instead
    const free = await page.evaluate(([px, py]) => { const el = document.elementFromPoint(px, py); return !!el && el.tagName === 'CANVAS'; }, [x, y]);
    if (free && !touch) {
      await page.mouse.move(x - 3, y - 3);
      await page.mouse.move(x, y, { steps: 3 });
      await page.waitForTimeout(450);
      console.log(name, id, 'hover', await page.evaluate(() => [document.querySelector('[data-testid=scene-hover-label] .s-hoverlabel')?.getAttribute('data-visible'), document.querySelector('[data-testid=scene-hover-label]')?.textContent, document.querySelector('.simple-stage canvas').style.cursor]));
      await shot(`scene-hover-${key}`);
      await page.mouse.click(x, y);
    } else if (free) await page.touchscreen.tap(x, y);
    else {
      console.log(name, id, 'not in the open picture at', Math.round(x), Math.round(y), ': opened from the Look at row');
      const b = page.getByTestId(`scene-object-${id}`);
      await b.scrollIntoViewIfNeeded();
      if (touch) await b.tap();
      else { await b.hover(); await page.waitForTimeout(300); await shot(`scene-list-hover-${key}`); await b.click(); await page.mouse.move(700, 600); }
    }
    await page.waitForTimeout(reducedWait(opts, 1900));
    const opened = await page.getByTestId('simple-mode').getAttribute('data-focus');
    if (opened !== id) console.log(name, id, 'DID NOT OPEN, got', opened);
    // is the object clear of its card?
    const clear = await page.evaluate((i) => {
      const a = window.__polarisScene.screen(i);
      const st = document.querySelector('.simple-stage canvas').getBoundingClientRect();
      const p = { x: st.left + a.x, y: st.top + a.y };
      const hit = [...document.querySelectorAll('.s-cardslot .s-objcard, .s-answerpanel, .s-statspanel, .s-dock, .s-bottom, .s-chrome')].filter((el) => { const r = el.getBoundingClientRect(); return r.width > 0 && p.x >= r.left && p.x <= r.right && p.y >= r.top && p.y <= r.bottom; }).map((el) => el.className);
      return { p: [Math.round(p.x), Math.round(p.y)], under: hit };
    }, id);
    console.log(name, id, 'card open; object at', clear.p, 'under', clear.under.join('|') || 'nothing', '· stepper hidden', await page.getByTestId('simple-mast-stepper').evaluate((e) => e.hidden), '· announce', (await page.getByTestId('scene-announce').textContent()).slice(0, 90));
    await shot(`card-${key}`);
    if (id === 'site' && !touch) {
      await page.getByTestId('simple-mast-5').click();
      await page.waitForTimeout(1700);
      await shot('card-site-ghost-mast-5m');
      await page.getByTestId('simple-mast-1').click();
      await page.waitForTimeout(900);
    }
    await page.keyboard.press('Escape');
    await page.waitForTimeout(reducedWait(opts, 1700));
    const back = await cam(page);
    console.log(name, id, 'returned exactly', back.every((n, i) => n === home[i]), 'max diff', Math.max(...back.map((n, i) => Math.abs(n - home[i]))).toExponential(2));
  }
  if (!touch) {
    // keyboard path: Tab to the list, the row shows, Enter flies
    await page.getByTestId('scene-object-sun').focus();
    await page.keyboard.press('Shift+Tab');
    await page.keyboard.press('Tab');
    await page.waitForTimeout(400);
    await shot('scene-keyboard-list');
    await page.keyboard.press('Enter');
    await page.waitForTimeout(reducedWait(opts, 1700));
    console.log(name, 'keyboard open: focus on', await page.evaluate(() => document.activeElement?.getAttribute('data-testid')));
    await page.keyboard.press('Escape');
    await page.waitForTimeout(reducedWait(opts, 1700));
    console.log(name, 'keyboard back: focus on', await page.evaluate(() => document.activeElement?.getAttribute('data-testid')));
    await page.getByTestId('site-card-close').click();
    await page.waitForTimeout(500);
    await shot('site-card-closed');
  }
  await ctx.close();
}
await browser.close();
function reducedWait(opts, ms) {
  return opts.reducedMotion ? 400 : ms;
}
