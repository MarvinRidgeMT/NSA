import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { validateBundle } from '../../src/bundle/validate';
import { basisFor } from '../../src/bundle/frame';
import { GLOBE_NAV, nearAltitude, radPerPixel, releaseVelocity, texelsPerRadian, zoomFloor } from '../../src/simple/globeMath';
import { blockingRidges, cropReachM, ridgeCard, ridgesNote, sceneObjects } from '../../src/simple/sceneFocus';
import { renderHook } from '@testing-library/react';
import { attributionScenarioId, useRidgeFocus } from '../../src/store/ridge';
import { useUi } from '../../src/store/ui';
import type { View } from '../../src/store/view';

/** S12. Expected card values are read from the bundle file here, never typed in. */
const bundlePath = resolve(__dirname, '../../../data/viewer/polaris-x5d-roi-2026-11-14-v2.json');
const raw = JSON.parse(readFileSync(bundlePath, 'utf8'));
// the loader reshapes what it is given, so it gets its own copy and `raw` stays as the file has it
const loaded = validateBundle(JSON.parse(readFileSync(bundlePath, 'utf8')));

/** The parts of a View the card builders read, for one dataset on its first series. */
function viewOf(i: number, seriesId?: string): View {
  const dataset = loaded.bundle.datasets[i];
  const series = dataset.derived?.scenarios.find((s) => (seriesId ? s.id === seriesId : s.samples)) ?? null;
  return { dataset, series, scenario: series, times: loaded.times[i], basis: basisFor(dataset) } as unknown as View;
}

describe('zoom limits come from the Moon image on screen', () => {
  it('a finer image lets the camera closer; the limit is one image pixel per MAX_TEXEL_CSS_PX', () => {
    const fov = 30;
    const h = 800;
    const coarse = nearAltitude(577, h, fov, GLOBE_NAV.MAX_TEXEL_CSS_PX);
    const fine = nearAltitude(1304, h, fov, GLOBE_NAV.MAX_TEXEL_CSS_PX);
    expect(fine).toBeLessThan(coarse);
    // at that height, one image pixel (1 / texelsPerRad of surface) spans exactly the allowed CSS pixels
    expect(1 / 1304 / radPerPixel(fine, h, fov)).toBeCloseTo(GLOBE_NAV.MAX_TEXEL_CSS_PX, 9);
    expect(zoomFloor(1304, h, fov, 3.45)).toBeCloseTo(fine / 3.45, 12);
    // never past the whole-Moon view, and no zoom at all for an image with no measured detail
    expect(zoomFloor(10, h, fov, 3.45)).toBe(1);
    expect(zoomFloor(0, h, fov, 3.45)).toBe(1);
  });
  it('measures image pixels per radian from texture coordinates (an equirectangular sphere gives about height / π)', () => {
    // a latitude-longitude band around the equator, unit sphere, standard equirectangular texture coordinates
    const [W, H, n] = [2048, 1024, 64];
    const pos: number[] = [];
    const uv: number[] = [];
    const idx: number[] = [];
    for (let j = 0; j <= 4; j++)
      for (let i = 0; i <= n; i++) {
        const lon = (i / n) * 2 * Math.PI;
        const lat = ((j - 2) / 4) * 0.2;
        pos.push(Math.cos(lat) * Math.cos(lon), Math.sin(lat), Math.cos(lat) * Math.sin(lon));
        uv.push(i / n, 0.5 + lat / Math.PI);
      }
    for (let j = 0; j < 4; j++) for (let i = 0; i < n; i++) idx.push(j * (n + 1) + i, j * (n + 1) + i + 1, (j + 1) * (n + 1) + i, j * (n + 1) + i + 1, (j + 1) * (n + 1) + i + 1, (j + 1) * (n + 1) + i);
    const t = texelsPerRadian(pos, uv, idx, W, H);
    expect(t / (H / Math.PI)).toBeGreaterThan(0.97);
    expect(t / (H / Math.PI)).toBeLessThan(1.03);
  });
});

describe('release of a drag', () => {
  it('a moving pointer carries its speed; a pointer that stopped first carries none', () => {
    const moving = [0, 16, 32, 48].map((t, i) => ({ x: i * 10, y: -i * 5, t }));
    const v = releaseVelocity(moving, 50);
    expect(v.vx).toBeCloseTo(30 / 0.048, 6);
    expect(v.vy).toBeCloseTo(-15 / 0.048, 6);
    expect(releaseVelocity(moving, 300)).toEqual({ vx: 0, vy: 0 });
    expect(releaseVelocity([{ x: 0, y: 0, t: 0 }], 10)).toEqual({ vx: 0, vy: 0 });
  });
});

describe('ridge cards copy the bundle attribution', () => {
  for (const [i, ds] of (raw.datasets as { siteId: string; dem: { validCoverageRadiusM: number }; derived: { attribution: { ridges: Record<string, unknown>[] } } }[]).entries()) {
    it(`${ds.siteId}: one card per ridge of record, every value from its attribution row`, () => {
      const v = viewOf(i);
      const rows = ds.derived.attribution.ridges.filter((r) => r.of_record);
      const ridges = blockingRidges(v);
      expect(ridges.map((r) => r.id)).toEqual(rows.map((r) => r.id));
      expect(rows.length).toBeGreaterThan(0);
      for (const [k, row] of rows.entries()) {
        const card = ridgeCard(ridges[k], v);
        const fact = (key: string) => card.facts.find((f) => f.key === key)!;
        const [d0, d1] = (row.dist_range_km as number[]).map((x) => x * 1000);
        const far = d0 > ds.dem.validCoverageRadiusM;
        expect(card.far).toBe(far);
        expect(cropReachM(v)).toBe(ds.dem.validCoverageRadiusM);
        expect(card.title).toBe(`Ridge ${row.id}`);
        // distance: metres under 1 km, kilometres beyond, as a range
        const dist = fact('distance').value;
        if (d1 >= 1000) expect(dist).toBe(`${(d0 / 1000).toFixed(d1 >= 10000 ? 1 : 2)}–${(d1 / 1000).toFixed(d1 >= 10000 ? 1 : 2)} km`);
        else expect(dist).toBe(d0 === d1 ? `${d0.toFixed(0)} m` : `${d0.toFixed(0)}–${d1.toFixed(0)} m`);
        const [a0, a1] = row.az_span_deg as number[];
        expect(fact('bearing').value).toBe(`${a0.toFixed(1)}–${a1.toFixed(1)}°`);
        const rel = row.relief_m as number;
        const abs = Math.abs(rel) < 100 ? Math.abs(rel).toFixed(2) : Math.round(Math.abs(rel)).toLocaleString('en-US');
        expect(fact('height').value).toBe(`${rel > 0 ? '+' : rel < 0 ? '−' : ''}${abs} m`);
        expect(fact('sun-hours').value).toBe(`${row.sun_loss_h} h`);
        expect(fact('earth-hours').value).toBe(`${row.earth_loss_h} h`);
        expect(fact('sun-hours').sub).toContain(String(loaded.times[i].length));
        // the spoken line carries every value on the card
        for (const f of card.facts) expect(card.say).toContain(f.value);
      }
      // the list offers the site, the Sun, the Earth and exactly those ridges
      expect(sceneObjects(v).map((o) => o.id)).toEqual(['site', 'sun', 'earth', ...rows.map((r) => `ridge:${r.id}`)]);
    });
  }
  it('under a series the attribution does not describe, no ridge is offered', () => {
    const ds = raw.datasets[1];
    const other = ds.derived.scenarios.find((s: { id: string; samples?: unknown }) => s.samples && s.id !== ds.derived.attribution.scenarioId);
    expect(other).toBeTruthy();
    expect(blockingRidges(viewOf(1, other.id))).toEqual([]);
    // and the page says why, with both mast heights from the bundle's own scenarios
    const base = ds.derived.scenarios.find((s: { id: string }) => s.id === ds.derived.attribution.scenarioId);
    const note = ridgesNote(viewOf(1, other.id))!;
    expect(note).toContain(`the ${base.observer.mastM} m mast series only`);
    if (other.observer.mastM !== base.observer.mastM) expect(note).toContain(`not for ${other.observer.mastM} m`);
    expect(ridgesNote(viewOf(1))).toBeNull();
  });
  it('a bundle whose attribution names no scenario means the baseline: other series still get no ridges, and the note', () => {
    const ds = raw.datasets[1];
    const other = ds.derived.scenarios.find((s: { id: string; samples?: unknown }) => s.samples && s.id !== 'baseline');
    const strip = (v: View): View => ({ ...v, dataset: { ...v.dataset, derived: { ...v.dataset.derived!, attribution: { ...v.dataset.derived!.attribution!, scenarioId: undefined } } } }) as View;
    expect(blockingRidges(strip(viewOf(1, other.id)))).toEqual([]);
    expect(ridgesNote(strip(viewOf(1, other.id)))).toContain('mast series only');
    expect(blockingRidges(strip(viewOf(1, 'baseline'))).length).toBeGreaterThan(0);
    expect(ridgesNote(strip(viewOf(1, 'baseline')))).toBeNull();
    // the one rule every Simple-mode ridge lookup uses (store/ridge.ts)
    expect(attributionScenarioId(strip(viewOf(1, other.id)).dataset)).toBe('baseline');
    expect(attributionScenarioId(viewOf(1).dataset)).toBe(ds.derived.attribution.scenarioId);
  });
  it('an attribution that names no scenario, in a bundle with no baseline scenario, is held to no series at all', () => {
    const ds = raw.datasets[1];
    const other = ds.derived.scenarios.find((s: { id: string; samples?: unknown }) => s.samples && s.id !== 'baseline');
    const base = viewOf(1, other.id);
    const d = base.dataset.derived!;
    const v = { ...base, dataset: { ...base.dataset, derived: { ...d, scenarios: d.scenarios.filter((x) => x.id !== 'baseline'), attribution: { ...d.attribution!, scenarioId: undefined } } } } as View;
    expect(attributionScenarioId(v.dataset)).toBeUndefined();
    expect(blockingRidges(v)).toEqual([]);
    expect(ridgesNote(v)).toContain('does not say which series');
    // nor to a view with no series
    expect(blockingRidges({ ...v, series: null } as View)).toEqual([]);
  });
  it('the shared ridge lookup (3D sight labels, ridge dots, the answer) follows that rule in Simple mode only', () => {
    const ds = raw.datasets[1];
    const other = ds.derived.scenarios.find((s: { id: string; samples?: unknown }) => s.samples && s.id !== 'baseline');
    // a sample at which the bundle says the Earth is blocked, on the other series
    const k = (other.samples.earth.visible as (boolean | null)[]).findIndex((x) => x === false);
    expect(k).toBeGreaterThanOrEqual(0);
    const base = viewOf(1, other.id);
    const v = {
      ...base,
      dataset: { ...base.dataset, derived: { ...base.dataset.derived!, attribution: { ...base.dataset.derived!.attribution!, scenarioId: undefined } } },
      br: { i0: k, i1: k, f: 0, exact: k },
      nearest: k,
      sun: { visible: true },
      earth: { visible: false },
    } as unknown as View;
    try {
      useUi.getState().set({ attributionStrict: false });
      // Expert's rule, as submitted: an unnamed attribution is applied to the series on screen
      expect(renderHook(() => useRidgeFocus(v)).result.current.earth).not.toBeNull();
      useUi.getState().set({ attributionStrict: true });
      // Simple mode: it is the baseline's, so nothing is named under another series
      const strict = renderHook(() => useRidgeFocus(v)).result.current;
      expect(strict.earth).toBeNull();
      expect(strict.sun).toBeNull();
      expect(strict.focus).toBeNull();
    } finally {
      useUi.getState().set({ attributionStrict: false });
    }
  });
});
