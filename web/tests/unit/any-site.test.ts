import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  ANYSITE_CREDIT,
  CLONES,
  cloneRanges,
  computedPoints,
  gridDeg,
  gridSpacingM,
  hours,
  loadAnySite,
  mastLabel,
  nearestPoint,
  parseWindow,
  pct,
  pctRange,
  pointLabel,
  siteRow,
  slopeText,
  windowPhrase,
  type AnyPoint,
  type AnySiteFile,
} from '../../src/simple/anySite';
import { distanceM, type SpotManifest } from '../../src/simple/spotCheck';

/**
 * S14 Part A: the any-site results in Simple mode. Every expected value below is read from
 * data/anysite/precompute_summary.json (the original, from feature/v2-whole-moon), the bundle or the certainty sidecar.
 */
const root = resolve(__dirname, '../../..');
const originalBytes = readFileSync(resolve(root, 'data/anysite/precompute_summary.json'));
type Row = Record<string, unknown> & { id: string; status: string; group: string; lat: number | null; lon: number | null; uncertainty?: Record<string, unknown> };
const original = JSON.parse(originalBytes.toString('utf8')) as { schema: string; label: string; window: string; counts: Record<string, Record<string, number>>; sites: Row[] };
const copy = JSON.parse(readFileSync(resolve(__dirname, '../../public/anysite/points.json'), 'utf8')) as AnySiteFile;
const m = JSON.parse(readFileSync(resolve(__dirname, '../../public/pgda69-spot/manifest.json'), 'utf8')) as SpotManifest;
const R = m.grid.radiusM;
const bundle = JSON.parse(readFileSync(resolve(root, 'data/viewer/polaris-x5d-roi-2026-11-14-v2.json'), 'utf8')) as {
  datasets: { siteId: string; site: { latitudePlanetocentricDeg: number; longitudeEastDeg: number }; derived: { certainty_curve: Curve[]; scenarios: { id: string; observer?: { groundM: number; mastM: number } }[] } }[];
};
type Curve = { mast_m: number; metric: string; nominal: number; min: number; max: number; n_clones: number };
const sidecar = JSON.parse(readFileSync(resolve(__dirname, '../../public/certainty/sidecar.json'), 'utf8')) as { sites: Record<string, { certainty_curve: Curve[] }> };

const points = computedPoints(copy);
const done = original.sites.filter((s) => s.status === 'done');
const byId = (id: string) => done.find((s) => s.id === id)!;
const count = (status: string) => Object.values(original.counts).reduce((n, g) => n + (g[status] ?? 0), 0);

/** the nearest done row found another way: largest dot product of unit vectors, over the original file */
function bruteNearest(lat: number, lon: number): Row {
  const v = (la: number, lo: number) => {
    const [a, b] = [(la * Math.PI) / 180, (lo * Math.PI) / 180];
    return [Math.cos(a) * Math.cos(b), Math.cos(a) * Math.sin(b), Math.sin(a)];
  };
  const q = v(lat, lon);
  let best: Row | null = null;
  let dot = -Infinity;
  for (const s of done) {
    const p = v(s.lat!, s.lon!);
    const d = q[0] * p[0] + q[1] * p[1] + q[2] * p[2];
    if (d > dot) [dot, best] = [d, s];
  }
  return best!;
}

describe('S14 web copy of the any-site results', () => {
  it('is a field-for-field copy of the original: every row, every kept field, nothing else', () => {
    expect(copy.source.sha256).toBe(createHash('sha256').update(originalBytes).digest('hex'));
    expect(copy.source.bytes).toBe(originalBytes.length);
    expect(copy.source.schema).toBe(original.schema);
    expect(copy.label).toBe(original.label);
    expect(copy.window).toBe(original.window);
    expect(copy.counts).toEqual(original.counts);
    expect(copy.sites.length).toBe(original.sites.length);
    const kept = copy.kept.filter((k) => !k.includes('.'));
    expect(copy.kept).toContain(`uncertainty.${CLONES}`);
    original.sites.forEach((o, i) => {
      const c = copy.sites[i] as unknown as Record<string, unknown>;
      const want: Record<string, unknown> = {};
      for (const k of kept) if (k in o) want[k] = o[k];
      if (o.uncertainty && CLONES in o.uncertainty) want.uncertainty = { [CLONES]: o.uncertainty[CLONES] };
      expect(c).toEqual(want);
    });
    // every field the page reads is one that was kept
    for (const k of ['id', 'name', 'group', 'lat', 'lon', 'status', 'slope_deg', 'sun_pct', 'earth_pct', 'sun_earth_pct', 'longest_sun_gap_h']) expect(kept).toContain(k);
  });

  it('is what the build script writes from the original (--check)', () => {
    expect(execFileSync('node', [resolve(__dirname, '../../scripts/build_anysite_web.mjs'), '--check'], { encoding: 'utf8' })).toContain('ok:');
  });

  it('docs/DATA_PROVENANCE.md records the commit it came from and the SHA-256 of the original', () => {
    const doc = readFileSync(resolve(root, 'docs/DATA_PROVENANCE.md'), 'utf8');
    expect(doc).toContain(copy.source.sha256);
    expect(doc).toContain(copy.source.commit);
    expect(doc).toContain(copy.source.branch);
    expect(copy.source.commit).toMatch(/^[0-9a-f]{40}$/);
  });

  it('carries the honesty label and the credit line the page prints', () => {
    expect(copy.label).toBe('SOURCE-BASED UNVALIDATED');
    expect(copy.credit).toBe(ANYSITE_CREDIT);
  });
});

describe('S14 headline values equal the bundle and the certainty sidecar (checked before wiring)', () => {
  for (const d of bundle.datasets) {
    const row = done.find((s) => s.id === d.siteId);
    const side = sidecar.sites[d.siteId];
    it.skipIf(!row || !side)(`${d.siteId}: Sun, Sun + Earth, clone ranges, coordinates and ground height`, () => {
      const w = parseWindow(original.window)!;
      const at = (c: Curve[], metric: RegExp) => c.find((r) => r.mast_m === w.mastM && metric.test(r.metric))!;
      const u = (row!.uncertainty as Record<string, Record<string, { min: number; max: number; n: number }>>)[CLONES];
      for (const curve of [side.certainty_curve, d.derived.certainty_curve]) {
        const sun = at(curve, /^sun_cent(re|er)_pct$/);
        const both = at(curve, /^both_cent(re|er)_pct$/);
        expect(row!.sun_pct).toBe(sun.nominal);
        expect(row!.sun_earth_pct).toBe(both.nominal);
        expect([u.sun_center_visible_pct_hourly_samples.min, u.sun_center_visible_pct_hourly_samples.max, u.sun_center_visible_pct_hourly_samples.n]).toEqual([sun.min, sun.max, sun.n_clones]);
        expect([u.sun_and_earth_center_visible_pct_hourly_samples.min, u.sun_and_earth_center_visible_pct_hourly_samples.max]).toEqual([both.min, both.max]);
      }
      expect([row!.lat, row!.lon]).toEqual([d.site.latitudePlanetocentricDeg, d.site.longitudeEastDeg]);
      const base = d.derived.scenarios.find((s) => s.id === 'baseline')!.observer!;
      expect(row!.ground_m).toBe(base.groundM);
      expect(base.mastM).toBe(w.mastM);
    });
  }
  // Earth in sight and the longest Sun gap are not in the certainty curves: they are held to the bundle's own hourly baseline
  // samples at the same 1 m mast (share of samples with the Earth's centre visible; longest run of samples with the Sun's
  // centre hidden, one sample per hour)
  for (const d of bundle.datasets) {
    const row = done.find((s) => s.id === d.siteId && s.lat === d.site.latitudePlanetocentricDeg && s.lon === d.site.longitudeEastDeg);
    const base = d.derived.scenarios.find((s) => s.id === 'baseline') as { observer?: { mastM: number }; samples?: Record<'sun' | 'earth' | 'both', { visible: boolean[] }> } | undefined;
    it.skipIf(!row || !base?.samples)(`${d.siteId}: Earth in sight and the longest Sun gap equal the bundle's hourly samples`, () => {
      const w = parseWindow(original.window)!;
      expect(base!.observer!.mastM).toBe(w.mastM);
      const share = (v: boolean[]) => (100 * v.filter(Boolean).length) / v.length;
      const s = base!.samples!;
      expect(s.earth.visible.length).toBe(w.days * 24 + 1);
      expect(Number(share(s.earth.visible).toFixed(3))).toBe(row!.earth_pct);
      expect(Number(share(s.sun.visible).toFixed(3))).toBe(row!.sun_pct);
      expect(Number(share(s.both.visible).toFixed(3))).toBe(row!.sun_earth_pct);
      let run = 0;
      let longest = 0;
      for (const x of s.sun.visible) longest = Math.max(longest, (run = x ? 0 : run + 1));
      expect(longest).toBe(row!.longest_sun_gap_h);
    });
  }
  it('site04_roi3 and site01_roi6 hold the values checked by hand on 18 Nov 2026', () => {
    const r3 = byId('site04_roi3') as Record<string, number> & Row;
    const c3 = (r3.uncertainty as Record<string, Record<string, { min: number; max: number }>>)[CLONES].sun_center_visible_pct_hourly_samples;
    expect([r3.sun_pct, r3.earth_pct, r3.sun_earth_pct, c3.min, c3.max, r3.longest_sun_gap_h]).toEqual([94.362, 77.745, 72.107, 87.537, 97.329, 19]);
    const r6 = byId('site01_roi6') as Record<string, number> & Row;
    expect([r6.sun_pct, r6.earth_pct]).toEqual([100, 81.602]);
  });
  it('covers the two sites the sidecar has', () => {
    expect(bundle.datasets.filter((d) => done.some((s) => s.id === d.siteId) && sidecar.sites[d.siteId]).length).toBe(Object.keys(sidecar.sites).length);
  });
});

describe('S14 which rows answer a spot', () => {
  it('uses every "done" row and skips the rows that need coordinates', () => {
    expect(points.length).toBe(count('done'));
    expect(points.length).toBe(done.length);
    const skipped = copy.sites.filter((s) => s.status !== 'done');
    expect(skipped.length).toBe(count('needs coordinates'));
    expect(skipped.length).toBeGreaterThan(0);
    for (const s of skipped) {
      expect(s.status).toBe('needs coordinates');
      expect(points.some((p) => p.id === s.id)).toBe(false);
    }
  });

  it('a row without status "done" is skipped even when it has coordinates and sits exactly on the spot', () => {
    const real = points[0];
    const ghost = { ...copy.sites.find((s) => s.status !== 'done')!, lat: real.lat + 0.25, lon: real.lon, sun_pct: 1, earth_pct: 1, sun_earth_pct: 1, longest_sun_gap_h: 1, slope_deg: 1 };
    const pts = computedPoints({ ...copy, sites: [ghost, ...copy.sites] });
    expect(pts.length).toBe(points.length);
    expect(nearestPoint(R, pts, ghost.lat, ghost.lon)!.point.id).not.toBe(ghost.id);
    // a "done" row with a value missing is not answered from either
    const { sun_pct: _drop, ...holed } = real;
    expect(computedPoints({ ...copy, sites: [holed] }).length).toBe(0);
  });
});

describe('S14 nearest computed point', () => {
  it('at every computed point the nearest point is that point, at no distance, with the values of its row', () => {
    for (const o of done) {
      const n = nearestPoint(R, points, o.lat!, o.lon!)!;
      // (two rows may share coordinates; then the first in the file wins)
      const first = done.find((s) => s.lat === o.lat && s.lon === o.lon)!;
      expect(n.point.id).toBe(first.id);
      expect(n.distM).toBe(0);
      for (const k of ['sun_pct', 'earth_pct', 'sun_earth_pct', 'longest_sun_gap_h', 'slope_deg', 'name'] as const) expect(n.point[k]).toBe(first[k]);
    }
  });

  it('for spots between points it is the same row a second method finds, and the distance is the great-circle distance to it', () => {
    const spots: [number, number][] = [];
    // near each current site, across both 1° grids, and over the 10° grid at low latitude
    for (const s of done.filter((x) => x.group === 'current_sites')) spots.push([s.lat! + 0.01, s.lon!], [s.lat! - 0.3, s.lon! + 20]);
    for (let lat = -89.7; lat <= 89.7; lat += 7.3) for (let lon = -175; lon < 180; lon += 23.7) spots.push([lat, lon]);
    expect(spots.length).toBeGreaterThan(300);
    const groups = new Set<string>();
    for (const [lat, lon] of spots) {
      const n = nearestPoint(R, points, lat, lon)!;
      const want = bruteNearest(lat, lon);
      expect(n.point.id).toBe(want.id);
      expect(n.distM).toBeCloseTo(distanceM(R, lat, lon, want.lat!, want.lon!), 6);
      for (const p of points) expect(distanceM(R, lat, lon, p.lat, p.lon)).toBeGreaterThanOrEqual(n.distM);
      groups.add(n.point.group);
    }
    for (const g of Object.keys(original.counts).filter((k) => original.counts[k].done)) expect(groups).toContain(g);
  });

  it('a step of latitude away from a site is that far along the meridian', () => {
    const s = byId(bundle.datasets.find((d) => done.some((x) => x.id === d.siteId))!.siteId);
    const step = 0.001;
    const n = nearestPoint(R, points, s.lat! + step, s.lon!)!;
    expect(n.point.id).toBe(s.id);
    expect(n.distM).toBeCloseTo((R * step * Math.PI) / 180, 3);
  });

  it('grid spacing at a grid point is the distance to its closest neighbour in the same grid; named points have none', () => {
    for (const p of points.filter((_, i) => i % 9 === 0)) {
      const sp = gridSpacingM(R, points, p);
      if (gridDeg(p) === null) {
        expect(sp).toBeNull();
        continue;
      }
      const others = done.filter((s) => s.group === p.group && s.id !== p.id).map((s) => distanceM(R, p.lat, p.lon, s.lat!, s.lon!));
      expect(sp).toBe(Math.min(...others));
    }
    // on the equator of the global grid the spacing is the grid's own step, taken from the group's name
    const eq = points.find((p) => p.group.startsWith('global_grid') && p.lat === 0)!;
    expect(gridSpacingM(R, points, eq)!).toBeCloseTo((R * Number(gridDeg(eq)) * Math.PI) / 180, 3);
    for (const p of points.filter((x) => x.group === 'current_sites' || x.group === 'landing_sites')) expect(gridSpacingM(R, points, p)).toBeNull();
  });
});

describe('S14 words', () => {
  it('names a grid point by its grid and coordinates, a pole by name, and any other point by its name in the file', () => {
    const one = (p: AnyPoint) => `${Number(Math.abs(p.lat).toFixed(1))}°${p.lat < 0 ? 'S' : 'N'} ${Number(Math.abs(p.lon).toFixed(1))}°${p.lon < 0 ? 'W' : 'E'}`;
    for (const p of points) {
      const g = gridDeg(p);
      const label = pointLabel(p);
      if (g === null) expect(label).toBe(p.name);
      else if (/pole/.test(p.name)) expect(label).toBe(`${g}° grid point at the ${p.name}`);
      else expect(label).toBe(`${g}° grid point ${one(p)}`);
    }
    expect(new Set(points.map(gridDeg))).toEqual(new Set([null, ...Object.keys(original.counts).flatMap((k) => /_grid_(\d+)deg$/.exec(k)?.[1] ?? [])]));
    const sample = points.find((p) => p.group.startsWith('south_grid') && p.lon < 0 && !/pole/.test(p.name))!;
    expect(pointLabel(sample)).toMatch(/^\d+° grid point \d+°S [\d.]+°W$/);
  });

  it('reads the window and the mast out of the file’s own line, and falls back to the line as written', () => {
    const w = parseWindow(original.window)!;
    expect(original.window).toContain(`+ ${w.days} d`);
    expect(original.window).toContain(`mast ${w.mastM} m`);
    expect(original.window).toContain(`${w.startTime} UTC`);
    expect(new Date(`${w.start} UTC`).toISOString().slice(0, 10)).toBe(original.window.slice(0, 10));
    expect(windowPhrase(copy)).toBe(`${w.days} days from ${w.start} ${w.startTime} UTC, hourly samples, ${w.mastM} m mast`);
    expect(parseWindow('some other window')).toBeNull();
    expect(windowPhrase({ ...copy, window: 'some other window' })).toBe('some other window');
  });

  it('says which mast the values are for: "1 m mast" beside a 1 m mast, and "not the … picked above" beside any other', async () => {
    vi.stubGlobal('fetch', async () => ({ ok: true, status: 200, json: async () => copy }) as Response);
    const a = await loadAnySite();
    vi.unstubAllGlobals();
    const own = parseWindow(original.window)!.mastM;
    expect(own).toBe(1);
    expect(mastLabel(a, own)).toEqual({ same: true, label: '1 m mast', window: parseWindow(original.window)!.text });
    expect(mastLabel(a, 10)).toMatchObject({ same: false, label: 'for a 1 m mast (not the 10 m mast picked above)' });
    expect(mastLabel(a, 1.25).label).toBe('for a 1 m mast (not the 1.25 m mast picked above)');
    expect(mastLabel(a, null)).toMatchObject({ same: false, label: 'for a 1 m mast (not the mast picked above)' });
    // a window line the page cannot read: the mast is never claimed
    const odd = { ...a, window: null, file: { ...a.file, window: 'some other window' } };
    expect(mastLabel(odd, 1)).toEqual({ same: false, label: 'for the mast the file states (some other window), not necessarily the mast picked above', window: 'some other window' });
  });

  it('prints values at the cards’ precision and clone ranges only where the file has them', () => {
    const withClones = done.filter((s) => s.uncertainty && CLONES in s.uncertainty);
    expect(points.filter((p) => cloneRanges(p)).map((p) => p.id)).toEqual(withClones.map((s) => s.id));
    expect(withClones.length).toBeGreaterThan(0);
    for (const p of points.filter((_, i) => i % 50 === 0)) {
      expect(pct(p.sun_pct)).toBe(`${p.sun_pct.toFixed(1)} %`);
      expect(hours(p.longest_sun_gap_h)).toBe(`${Number(p.longest_sun_gap_h.toFixed(1))} h`);
      expect(slopeText(p.slope_deg)).toBe(`${p.slope_deg.toFixed(1)}°`);
    }
    const c = cloneRanges(points.find((p) => cloneRanges(p) && cloneRanges(p)!.sun_center_visible_pct_hourly_samples.min !== cloneRanges(p)!.sun_center_visible_pct_hourly_samples.max)!)!.sun_center_visible_pct_hourly_samples;
    expect(pctRange(c)).toBe(`${c.min.toFixed(1)}–${c.max.toFixed(1)} %`);
    expect(pctRange({ ...c, max: c.min })).toBe(`${c.min.toFixed(1)} %`);
  });

  it('pin cards: a bundle site gets the row with its id and its coordinates, or none', () => {
    for (const d of bundle.datasets) {
      const o = done.find((s) => s.id === d.siteId && s.lat === d.site.latitudePlanetocentricDeg && s.lon === d.site.longitudeEastDeg);
      const row = siteRow(points, d.siteId, d.site.latitudePlanetocentricDeg, d.site.longitudeEastDeg);
      if (!o) expect(row).toBeNull();
      else {
        expect(row!.earth_pct).toBe(o.earth_pct);
        expect(row!.longest_sun_gap_h).toBe(o.longest_sun_gap_h);
      }
      expect(siteRow(points, d.siteId, d.site.latitudePlanetocentricDeg + 1, d.site.longitudeEastDeg)).toBeNull();
    }
    expect(bundle.datasets.some((d) => siteRow(points, d.siteId, d.site.latitudePlanetocentricDeg, d.site.longitudeEastDeg))).toBe(true);
    expect(bundle.datasets.some((d) => !siteRow(points, d.siteId, d.site.latitudePlanetocentricDeg, d.site.longitudeEastDeg))).toBe(true);
  });
});

describe('S14 loading the file', () => {
  afterEach(() => vi.unstubAllGlobals());
  const answer = (body: unknown, ok = true) => ({ ok, status: ok ? 200 : 503, json: async () => body }) as Response;

  it('a request that never answers is dropped after the stated time, with a reason; the body is waited for too', async () => {
    const never = (_u: string, init?: RequestInit) => new Promise<Response>((_, no) => init!.signal!.addEventListener('abort', () => no(new DOMException('aborted', 'AbortError'))));
    vi.stubGlobal('fetch', never);
    await expect(loadAnySite('x.json', 40)).rejects.toThrow('x.json: no answer after 0.04 s');
    // headers arrive, the body never does
    vi.stubGlobal('fetch', (_u: string, init?: RequestInit) => Promise.resolve({ ok: true, status: 200, json: () => new Promise((_, no) => init!.signal!.addEventListener('abort', () => no(new DOMException('aborted', 'AbortError')))) }));
    await expect(loadAnySite('x.json', 40)).rejects.toThrow('no answer after');
  });

  it('reads the copy, and refuses an HTTP error, another schema, or a file without the honesty label', async () => {
    vi.stubGlobal('fetch', async () => answer(copy));
    const a = await loadAnySite();
    expect(a.points.length).toBe(points.length);
    expect(a.windowPhrase).toBe(windowPhrase(copy));
    vi.stubGlobal('fetch', async () => answer(copy, false));
    await expect(loadAnySite()).rejects.toThrow('HTTP 503');
    vi.stubGlobal('fetch', async () => answer({ ...copy, schema: 'other' }));
    await expect(loadAnySite()).rejects.toThrow('unexpected any-site file');
    vi.stubGlobal('fetch', async () => answer({ ...copy, label: 'VALIDATED' }));
    await expect(loadAnySite()).rejects.toThrow('not "SOURCE-BASED UNVALIDATED"');
  });
});
