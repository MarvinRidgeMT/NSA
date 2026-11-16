import { describe, expect, it } from 'vitest';
import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';

/**
 * Final Apex P3: orientation of the display shadow model, checked without the GPU.
 * The display shadows read the context pack horizon maps (K grid azimuths per terrain node). At the observer node, the display
 * horizon in every direction is compared with the bundle's solver skyline after converting grid angles to local azimuths with the
 * bundle frame (localNorthInGrid / localEastInGrid). If the maps were rotated, mirrored or indexed from the wrong axis, the best
 * match would not sit at 0°. Display-consistency evidence only: the display model never sets a visible/blocked state.
 */
const pub = resolve(__dirname, '../../public');
const ctxDir = `${pub}/context/site04_roi3`;
const bundlePath = `${pub}/bundles/polaris-x5d-roi-2026-11-14-v2.json`;
const has = existsSync(`${ctxDir}/context.json`) && existsSync(bundlePath);

describe.runIf(has)('display shadow orientation vs the solver skyline (Site04 ROI3, observer node)', () => {
  const ctx = has ? JSON.parse(readFileSync(`${ctxDir}/context.json`, 'utf8')) : null;
  const b = has ? JSON.parse(readFileSync(bundlePath, 'utf8')) : null;
  const ds = b?.datasets.find((d: { siteId: string }) => d.siteId === 'site04_roi3');
  const median = (a: number[]) => {
    const s = [...a].sort((x, y) => x - y);
    return s[Math.floor(s.length / 2)];
  };
  const run = () => {
    const { localNorthInGrid: N, localEastInGrid: E } = ds.derived.frame as { localNorthInGrid: number[]; localEastInGrid: number[] };
    const base = ds.derived.scenarios.find((s: { id: string }) => s.id === 'baseline');
    const az: number[] = base.skyline.azimuthDeg;
    const el: (number | null)[] = base.skyline.elevationDeg;
    const binDeg: number = ds.derived.skylineBinDeg;
    const L = ctx.horizon.local;
    const K: number = ctx.horizon.azimuths;
    const raw = readFileSync(`${ctxDir}/${L.file}`);
    const i = Math.round((0 - L.originX) / L.spacingM);
    const j = Math.round((0 - L.originY) / L.spacingM);
    const deg = (q: number) => q * ctx.horizon.encoding.stepDeg + ctx.horizon.encoding.minDeg;
    const toLocal = (g: number) => {
      const dx = Math.sin((g * Math.PI) / 180);
      const dy = Math.cos((g * Math.PI) / 180);
      const n = dx * N[0] + dy * N[1];
      const e = dx * E[0] + dy * E[1];
      return (((Math.atan2(e, n) * 180) / Math.PI) % 360 + 360) % 360;
    };
    const disp = Array.from({ length: K }, (_, k) => ({ a: toLocal((360 * k) / K), h: deg(raw[(k * L.m + j) * L.m + i]) }));
    const sky = (a: number) => el[Math.round((((a % 360) + 360) % 360) / binDeg) % az.length];
    const score = (off: number, mirror = false) =>
      median(disp.filter((d) => sky(mirror ? -d.a + off : d.a + off) !== null).map((d) => Math.abs(d.h - (sky(mirror ? -d.a + off : d.a + off) as number))));
    return { score };
  };

  it('the best rotation is 0° (within one 5° step) and the mirrored convention fits worse', () => {
    const { score } = run();
    const offs = Array.from({ length: 72 }, (_, k) => k * 5 - 180);
    const best = offs.reduce((a, o) => (score(o) < score(a) ? o : a), 0);
    expect(Math.abs(best)).toBeLessThanOrEqual(5);
    const bestMirror = Math.min(...offs.map((o) => score(o, true)));
    expect(bestMirror).toBeGreaterThan(score(0));
    expect(score(180)).toBeGreaterThan(score(0) + 0.5);
  });

  it('median |display − solver| horizon at the observer stays under 1°', () => {
    // measured 0.80° on 15 Nov: ground node vs 1 m mast, 10 m nodes, 48 azimuths, finite display reach (see context.json skylineCrossCheck)
    expect(run().score(0)).toBeLessThan(1.0);
  });
});
