import { describe, expect, it, vi } from 'vitest';
import { eqcPixel, greatCircleKm, latLonFromDir, polarPixel, polarStereo, raySphere } from '../../src/globe/geo';
import { computeNow, memberRanges, membersFor, membersNotRun, nearestSite, probeSolver, reproduceCommand, validateSummary, type AnysiteRow } from '../../src/globe/anysite';
import { layerTextures, validateLayerManifest } from '../../src/globe/layers';
import { globeOrder, SVS_ENTRY, type GlobeEntry } from '../../src/globe/globeAsset';
import { parseUrlState, serializeUrlState } from '../../src/store/urlState';

// Reference values from pyproj via science.terrain.stack.ZONES[zone].forward (PROJ4 '+proj=stere +lat_0=±90 +lat_ts=±90
// +lon_0=0 +R=1737400'), printed in this session's venv on 16 Nov 2026.
const PYPROJ: [string, number, number, number, number][] = [
  ['sp', -89.47409, -137.3813, -10798.287, -11735.359],
  ['sp', -85, 45, 107277.323, 107277.323],
  ['sp', -80, -120, -263276.579, -152002.804],
  ['np', 85, 30, 75856.522, -131387.351],
  ['np', 88, -100, -59731.406, 10532.259],
];

describe('globe display geometry', () => {
  it('polar stereographic forward matches pyproj to < 1 mm', () => {
    for (const [zone, lat, lon, x, y] of PYPROJ) {
      const p = polarStereo(lat, lon, zone as 'sp' | 'np');
      expect(Math.abs(p.x - x)).toBeLessThan(1e-3);
      expect(Math.abs(p.y - y)).toBeLessThan(1e-3);
    }
  });
  it('polar pixel: the pole is the image centre; +y is row 0; -x is column 0', () => {
    const c = polarPixel(-90, 0, 'sp', 152000, 304, 304);
    expect(c.col).toBeCloseTo(152);
    expect(c.row).toBeCloseTo(152);
    const north0E = polarPixel(-85, 0, 'sp', 152000, 304, 304); // sp: 0 E is +y -> above the centre
    expect(north0E.row).toBeLessThan(152);
    expect(polarPixel(-85, -90, 'sp', 152000, 304, 304).col).toBeLessThan(152); // 90 W is -x
    expect(polarPixel(85, 0, 'np', 152000, 304, 304).row).toBeGreaterThan(152); // np: 0 E is -y -> below the centre
  });
  it('equirectangular pixel wraps longitude and puts 90 N on row 0', () => {
    expect(eqcPixel(90, -180, 2880, 1440)).toEqual({ col: 0, row: 0 });
    expect(eqcPixel(0, 0, 2880, 1440)).toEqual({ col: 1440, row: 720 });
    expect(eqcPixel(0, 190, 2880, 1440).col).toBeCloseTo(eqcPixel(0, -170, 2880, 1440).col);
  });
  it('latLonFromDir inverts the globe axes (+Y north, +Z lon 0, +X 90 E)', () => {
    expect(latLonFromDir(0, 0, 1)).toEqual({ lat: 0, lon: 0 });
    expect(latLonFromDir(1, 0, 0).lon).toBeCloseTo(90);
    expect(latLonFromDir(-1, 0, 0).lon).toBeCloseTo(-90);
    expect(latLonFromDir(0, -1, 0).lat).toBeCloseTo(-90);
    const lat = -89.47409;
    const lon = -137.3813;
    const c = Math.cos((lat * Math.PI) / 180);
    const v = [c * Math.sin((lon * Math.PI) / 180), Math.sin((lat * Math.PI) / 180), c * Math.cos((lon * Math.PI) / 180)];
    const back = latLonFromDir(v[0], v[1], v[2]);
    expect(back.lat).toBeCloseTo(lat, 9);
    expect(back.lon).toBeCloseTo(lon, 9);
  });
  it('great-circle distance: a quarter meridian is πR/2 km', () => {
    expect(greatCircleKm(0, 0, 90, 0)).toBeCloseTo((Math.PI * 1737.4) / 2, 6);
    expect(greatCircleKm(-89, 179.9, -89, -179.9)).toBeCloseTo((0.2 * Math.PI / 180) * 1737.4 * Math.cos((89 * Math.PI) / 180), 4); // across ±180
  });
  it('ray-sphere: hit from outside, miss, and from inside', () => {
    expect(raySphere([0, 0, 3], [0, 0, -1], 1)).toBeCloseTo(2);
    expect(raySphere([0, 2, 3], [0, 0, -1], 1)).toBeNull();
    expect(raySphere([0, 0, 0], [1, 0, 0], 1)).toBeCloseTo(1);
  });
});

const rows: AnysiteRow[] = [
  { id: 'a3', name: 'needs coords', group: 'artemis3_regions', lat: null, lon: null, status: 'needs coordinates' },
  { id: 'p', name: 'south pole', group: 'south_grid_1deg', lat: -89.999999, lon: 0, status: 'done', sun_pct: 51.9 },
  { id: 'w', name: 'west', group: 'global_grid_10deg', lat: 0, lon: 179.5, status: 'done' },
  { id: 'e', name: 'east', group: 'global_grid_10deg', lat: 0, lon: -170, status: 'done' },
  { id: 's1', name: 'Site01', group: 'current_sites', lat: -89.47409, lon: -137.3813, status: 'done', uncertainty: { 'pgda78-clone': { label: 'PGDA 78 clones', sun_center_visible_pct_hourly_samples: { min: 90, max: 100, median: 95, n: 20 } }, assumed: { status: 'not-run', reason: 'no error model' }, products: { compared: [] } } },
  { id: 'err', name: 'error', group: 'global_grid_10deg', lat: 10, lon: 10, status: 'error' },
];

describe('nearest precomputed any-site row', () => {
  it('exact hit, across the antimeridian, near the pole, never a row without coordinates or not done', () => {
    expect(nearestSite(rows, -89.47409, -137.3813)?.row.id).toBe('s1');
    expect(nearestSite(rows, -89.47409, -137.3813)?.distanceKm).toBeLessThan(1e-6);
    expect(nearestSite(rows, 0, -179.9)?.row.id).toBe('w'); // 179.5 E is 0.6 deg away across ±180
    expect(nearestSite(rows, -89.99, 120)?.row.id).toBe('p');
    expect(nearestSite(rows, 10, 10)?.row.id).not.toBe('err');
    expect(nearestSite([rows[0]], 0, 0)).toBeNull();
  });
  it('reproduce command carries the same window, mast and members as the precompute', () => {
    expect(membersFor('landing_sites')).toBe('clones,assumed,products');
    expect(membersFor('south_grid_1deg')).toBe('');
    expect(reproduceCommand(-89.5, 10, { members: '', name: "Bob's" })).toBe(
      "$POLARIS_PYTHON -m science.anysite.solve --lat -89.5 --lon 10 --mast 1 --start '2026-11-14 00:00' --days 14 --members '' --name 'Bob'\\''s'",
    );
  });
  it('member ranges and not-run member sets are reported apart; products are never a range', () => {
    const s1 = rows[4];
    expect(memberRanges(s1).map((r) => r.key)).toEqual(['pgda78-clone']);
    expect(membersNotRun(s1)).toEqual([{ key: 'assumed', reason: 'no error model' }]);
  });
  it('summary schema is checked', () => {
    expect(() => validateSummary({ schema: 'x', sites: [] })).toThrow();
    expect(validateSummary({ schema: 'polaris-anysite-precompute-summary-v1', sites: [] }).sites).toEqual([]);
  });
});

const res = (body: unknown, init: { status?: number; ct?: string } = {}) =>
  ({ ok: (init.status ?? 200) < 400, status: init.status ?? 200, headers: { get: () => init.ct ?? 'application/json' }, json: async () => body }) as unknown as Response;

describe('solver API client', () => {
  it('down when the proxy answers 500, when it is static hosting (HTML), or when the answer is not a spec', async () => {
    expect((await probeSolver(vi.fn(async () => res('', { status: 500, ct: 'text/plain' })))).state).toBe('down');
    expect(await probeSolver(vi.fn(async () => res('<html>', { ct: 'text/html' })))).toMatchObject({ state: 'down', why: /static hosting/ });
    expect((await probeSolver(vi.fn(async () => res({ hello: 1 })))).state).toBe('down');
    expect((await probeSolver(vi.fn(async () => Promise.reject(new Error('ECONNREFUSED'))))).state).toBe('down');
  });
  it('running when GET answers the solver spec', async () => {
    expect(await probeSolver(vi.fn(async () => res({ name: 'polaris_anysite', endpoint: 'POST /anysite' })))).toEqual({ state: 'running', name: 'polaris_anysite', endpoint: 'POST /anysite' });
  });
  it('compute now posts the precompute window and surfaces solver errors', async () => {
    const f = vi.fn(async () => res({ error: 'ValueError: no height' }, { status: 400 }));
    expect(await computeNow(-85, 30, [], f)).toEqual({ error: 'ValueError: no height' });
    const call = (f.mock.calls[0] as unknown as [string, RequestInit])[1];
    expect(JSON.parse(String(call.body))).toEqual({ lat: -85, lon: 30, mast_m: 1, start: '2026-11-14 00:00', days: 14, step_h: 1, members: [] });
    expect((await computeNow(0, 0, [], vi.fn(async () => res('x', { status: 502, ct: 'text/plain' })))).error).toMatch(/did not answer JSON/);
  });
});

describe('layer manifest and globe choice', () => {
  const man = {
    schema: 'polaris-globe-layers-v1',
    label: 'x',
    created_utc: '',
    script: '',
    layers: [
      { id: 'sun-vis', files: [{ path: 'globe/analytics/sun_visibility_sp_1000m.png', width: 304, height: 304, projection: 'polar-stereographic-sp', halfExtentM: 152000 }], legend: { kind: 'ramp' } },
      { id: 'slope', files: [{ path: 'a.png', width: 2880, height: 1440, projection: 'equirectangular: …' }, { path: 'bad.png', width: 1, height: 1, projection: 'mercator' }], legend: { kind: 'ramp' } },
      { id: 'roughness', files: [], legend: { kind: 'ramp' } },
      { id: 'not-a-layer', files: [], legend: { kind: 'ramp' } },
    ],
  };
  it('drops unknown layers and projections; a layer with no file is not built', () => {
    const m = validateLayerManifest(man);
    expect(m.layers.map((l) => [l.id, l.built])).toEqual([
      ['sun-vis', true],
      ['slope', true],
      ['roughness', false],
    ]);
    expect(layerTextures(m.layers[0]).sp?.halfExtentM).toBe(152000);
    expect(layerTextures(m.layers[1]).eqc?.path).toBe('a.png');
    expect(() => validateLayerManifest({ schema: 'nope', layers: [] })).toThrow();
  });
  it('Blender globe first only when it names the POLARIS builder; SVS is the fallback', () => {
    const b = { ...SVS_ENTRY, url: 'globe/polaris_moon_globe.glb', kind: 'blender', role: 'primary', builder: 'blender/v2/globe.py' } as GlobeEntry;
    expect(globeOrder({ schema: 'polaris-globe-manifest-v1', globes: [b, SVS_ENTRY] }).map((g) => g.kind)).toEqual(['blender', 'svs']);
    expect(globeOrder({ schema: 'polaris-globe-manifest-v1', globes: [{ ...b, builder: 'someone else' }] }).map((g) => g.kind)).toEqual(['svs']);
    expect(globeOrder(null).map((g) => g.url)).toEqual(['globe/NASA_SVS_moon_small.glb']);
  });
  it('deep link carries globe=1 and the globe layer; unknown values are ignored', () => {
    const { state, ignored } = parseUrlState('?site=x&globe=1&gl=slope');
    expect(state).toMatchObject({ globe: '1', gl: 'slope' });
    expect(ignored).toEqual([]);
    expect(parseUrlState('?globe=yes&gl=pizza').ignored).toEqual(['globe=yes', 'gl=pizza']);
    expect(serializeUrlState({ site: 'x', globe: '1', gl: 'earth-vis' })).toBe('?site=x&globe=1&gl=earth-vis');
  });
});
