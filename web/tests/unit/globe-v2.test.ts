// @vitest-environment node
import { createHash } from 'node:crypto';
import { copyFileSync, existsSync, mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { createRequire } from 'node:module';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { GLOBE_8K, GLOBE_FULL, GLOBE_LITE, GLOBE_V2, MODEL_YAW_RAD, cubeFaceLatLon, cubeFaceTexel, globeFallback, globePlan, manifestEntry, moonDir, toModelAxes, yawFromAxes, type GlobeManifestEntry, type Vec3 } from '../../src/simple/globeMath';

/**
 * S14 Part B: the POLARIS v2 globe beside the two NASA SVS models. Every expected value is read from a file: the manifest
 * (public/globe/globe_manifest.json), the model itself (its glTF JSON and its Draco mesh) and the bundle's site coordinates.
 * The model is git-ignored for now, so the tests that open it are skipped where it is absent.
 */
const globeDir = resolve(__dirname, '../../public/globe');
const manifestPath = resolve(globeDir, 'globe_manifest.json');
const glbPath = resolve(globeDir, GLOBE_V2);
const bundlePath = resolve(__dirname, '../../../data/viewer/polaris-x5d-roi-2026-11-14-v2.json');
const DEG = 180 / Math.PI;
const manifest = existsSync(manifestPath) ? (JSON.parse(readFileSync(manifestPath, 'utf8')) as { schema: string; globes: GlobeManifestEntry[] }) : null;
const entry = manifestEntry(manifest, GLOBE_V2);
const hasModel = !!entry && existsSync(glbPath);

/** the three bundle sites, and a few typed points spread over all six cube faces (the first is the Check-a-spot placeholder) */
const sites: [string, number, number][] = (JSON.parse(readFileSync(bundlePath, 'utf8')).datasets as { siteId: string; site: { latitudePlanetocentricDeg: number; longitudeEastDeg: number } }[]).map((d) => [d.siteId, d.site.latitudePlanetocentricDeg, d.site.longitudeEastDeg]);
const typed: [string, number, number][] = [
  ['typed', -89.5, -137.4],
  ['typed', -85, 45],
  ['typed', -45, 170],
  ['typed', 0, 0],
  ['typed', 10, 20],
  ['typed', 0, 90],
  ['typed', 45, -120],
  ['typed', 88, 10],
];
const points = [...sites, ...typed];

describe('which model is drawn: the v2 globe by default, ?globe=8k | svs on request', () => {
  const all = [GLOBE_8K, GLOBE_FULL, GLOBE_LITE, GLOBE_V2];
  it('with no choice (or v2, or a word that names no model) the v2 globe, on a desktop and a phone, and the 8k model is never planned', () => {
    for (const lite of [false, true])
      for (const prefer of [undefined, null, 'v2', 'nonsense']) {
        expect(globePlan(all, lite, prefer)).toEqual({ first: GLOBE_V2, then: null });
        expect(globePlan([GLOBE_FULL, GLOBE_V2], lite, prefer)).toEqual({ first: GLOBE_V2, then: null });
      }
  });
  it('8k comes in over the compact model; svs is the compact model (a phone keeps its reduced image of it)', () => {
    for (const lite of [false, true]) expect(globePlan(all, lite, '8k')).toEqual({ first: GLOBE_FULL, then: GLOBE_8K });
    expect(globePlan(all, false, 'svs')).toEqual({ first: GLOBE_FULL, then: null });
    expect(globePlan(all, false, 'compact')).toEqual({ first: GLOBE_FULL, then: null });
    expect(globePlan(all, true, 'svs')).toEqual({ first: GLOBE_LITE, then: null });
  });
  it('software rendering (no GPU) keeps the reduced SVS model unless the link asks for v2 or 8k', () => {
    for (const prefer of [undefined, null, 'svs', 'nonsense']) expect(globePlan(all, true, prefer, true)).toEqual({ first: GLOBE_LITE, then: null });
    expect(globePlan(all, true, 'v2', true)).toEqual({ first: GLOBE_V2, then: null });
    expect(globePlan(all, true, '8k', true)).toEqual({ first: GLOBE_FULL, then: GLOBE_8K });
    expect(globePlan([GLOBE_FULL, GLOBE_V2], true, undefined, true)).toEqual({ first: GLOBE_FULL, then: null });
    // a GPU (phone or desktop) is not software: v2
    expect(globePlan(all, true, undefined, false)).toEqual({ first: GLOBE_V2, then: null });
  });
  it('an SVS choice where no SVS image is present keeps the v2 globe, never the 8k model (Codex review)', () => {
    for (const lite of [false, true]) {
      expect(globePlan([GLOBE_V2, GLOBE_8K], lite, 'svs')).toEqual({ first: GLOBE_V2, then: null });
      expect(globePlan([GLOBE_V2, GLOBE_8K], lite, undefined, true)).toEqual({ first: GLOBE_V2, then: null });
    }
    // only the reduced image: a desktop asking for svs gets it
    expect(globePlan([GLOBE_V2, GLOBE_8K, GLOBE_LITE], false, 'svs')).toEqual({ first: GLOBE_LITE, then: null });
  });
  it('the fallback for a v2 globe that fails to load is a light SVS model, never the 8k one', () => {
    expect(globeFallback([GLOBE_V2, GLOBE_FULL, GLOBE_LITE, GLOBE_8K], false)).toBe(GLOBE_FULL);
    expect(globeFallback([GLOBE_V2, GLOBE_FULL, GLOBE_LITE, GLOBE_8K], true)).toBe(GLOBE_LITE);
    expect(globeFallback([GLOBE_V2, GLOBE_FULL], true)).toBe(GLOBE_FULL);
    expect(globeFallback([GLOBE_V2, GLOBE_8K], false)).toBeNull();
  });
  it('a choice whose model is not there changes nothing; without the v2 globe the rule before S14 Part B holds', () => {
    expect(globePlan([GLOBE_FULL, GLOBE_V2], false, '8k')).toEqual({ first: GLOBE_V2, then: null });
    for (const lite of [false, true])
      for (const prefer of [undefined, '8k', 'svs', 'v2']) expect(globePlan([GLOBE_8K, GLOBE_FULL, GLOBE_LITE], lite, prefer)).toEqual(globePlan([GLOBE_8K, GLOBE_FULL, GLOBE_LITE], lite, prefer === 'v2' ? undefined : prefer));
    expect(globePlan([GLOBE_8K, GLOBE_FULL], false)).toEqual({ first: GLOBE_FULL, then: GLOBE_8K });
    expect(globePlan([GLOBE_V2], false, 'svs')).toEqual({ first: GLOBE_V2, then: null });
  });
});

describe('a model’s turn, read from its own sentence about its axes', () => {
  it('the three frames of globeMath’s header give their three turns', () => {
    expect(yawFromAxes('+Y north, -Z lon 0, -X lon 90 E')).toBe(0); // the compact model: this file's model frame
    expect(yawFromAxes('+Y north, +X lon 0, -Z lon 90 E')).toBeCloseTo(MODEL_YAW_RAD[GLOBE_8K], 12); // the 8k model
    expect(yawFromAxes('glTF +Y north, +Z lon 0, +X lon 90 E (Moon-fixed ME, rotated for the web viewer)')).toBeCloseTo(Math.PI, 12);
  });
  it('a sentence it cannot read, a tilted pole or a mirrored frame gives no turn', () => {
    expect(yawFromAxes(null)).toBeNull();
    expect(yawFromAxes('Z up')).toBeNull();
    expect(yawFromAxes('+Z north, +X lon 0, +Y lon 90 E')).toBeNull();
    expect(yawFromAxes('+Y north, +Z lon 0, -X lon 90 E')).toBeNull();
  });
  it('turning a point into a model’s own axes and reading it there gives the same latitude and longitude', () => {
    // own-axes readers, one per frame sentence above
    const read: [number, (d: Vec3) => [number, number]][] = [
      [0, (d) => [Math.asin(d[1]) * DEG, Math.atan2(-d[0], -d[2]) * DEG]],
      [MODEL_YAW_RAD[GLOBE_8K], (d) => [Math.asin(d[1]) * DEG, Math.atan2(-d[2], d[0]) * DEG]],
      [Math.PI, (d) => [Math.asin(d[1]) * DEG, Math.atan2(d[0], d[2]) * DEG]],
    ];
    for (const [, lat, lon] of points)
      for (const [yaw, f] of read) {
        const [la, lo] = f(toModelAxes(moonDir(lat, lon), yaw));
        expect(la).toBeCloseTo(lat, 9);
        expect(Math.cos((lo - lon) / DEG)).toBeCloseTo(1, 12);
      }
  });
});

describe('the v2 globe’s cube-face image layout (blender/v2/cubesphere.py)', () => {
  it('face centres and the round trip', () => {
    const n = 1024;
    const centres: [number, number][] = [[0, 0], [0, 90], [0, 180], [0, -90], [90, 0], [-90, 0]];
    centres.forEach(([lat, lon], face) => {
      const t = cubeFaceTexel(lat, lon, n);
      expect(t.face).toBe(face);
      expect(t.x).toBeCloseTo(n / 2, 9);
      expect(t.y).toBeCloseTo(n / 2, 9);
    });
    for (const [, lat, lon] of points) {
      const t = cubeFaceTexel(lat, lon, n);
      const back = cubeFaceLatLon(t.face, t.x, t.y, n);
      expect(back.lat).toBeCloseTo(lat, 9);
      expect(Math.cos((back.lon - lon) / DEG) * Math.cos(lat / DEG)).toBeCloseTo(Math.cos(lat / DEG), 12);
    }
    // north is up in the four side faces: a point north of a face centre is above it in the image
    expect(cubeFaceTexel(10, 0, n).y).toBeLessThan(n / 2);
    // east is right in the side faces
    expect(cubeFaceTexel(0, 10, n).x).toBeGreaterThan(n / 2);
  });
});

describe.skipIf(!manifest)('public/globe/globe_manifest.json', () => {
  it('names the v2 globe with the labels and credit that About this view shows', () => {
    expect(manifest!.schema).toBe('polaris-globe-manifest-v1');
    expect(entry).not.toBeNull();
    expect(entry!.labels!.heights).toContain('SOURCE-BASED · UNVALIDATED');
    expect(entry!.labels!.webBaseColour).toMatch(/^VISUAL base colour/);
    expect(entry!.textureCredit).toContain('LROC WAC');
    expect(yawFromAxes(entry!.axes)).toBeCloseTo(Math.PI, 12);
  });
});

/* ---- the model file itself ---- */

interface Prim {
  pos: Float32Array;
  uv: Float32Array;
  idx: Uint32Array;
  material: string;
  texSize: number;
}
/** JPEG width (= height here) from its start-of-frame marker */
function jpegSize(b: Uint8Array): number {
  for (let i = 2; i < b.length - 9; ) {
    if (b[i] !== 0xff) throw new Error('not a JPEG marker');
    const m = b[i + 1];
    const len = (b[i + 2] << 8) | b[i + 3];
    if (m >= 0xc0 && m <= 0xc3) {
      const h = (b[i + 5] << 8) | b[i + 6];
      const w = (b[i + 7] << 8) | b[i + 8];
      if (w !== h) throw new Error('face image is not square');
      return w;
    }
    i += 2 + len;
  }
  throw new Error('no JPEG frame header');
}
async function loadV2(): Promise<{ json: Record<string, any>; prims: Prim[] }> {
  const buf = readFileSync(glbPath);
  const jl = buf.readUInt32LE(12);
  const json = JSON.parse(buf.subarray(20, 20 + jl).toString('utf8'));
  const bin = buf.subarray(20 + jl + 8);
  const view = (i: number) => {
    const v = json.bufferViews[i];
    return new Uint8Array(bin.buffer, bin.byteOffset + (v.byteOffset ?? 0), v.byteLength);
  };
  // three.js ships the Draco decoder as a CommonJS script inside an ES-module package (no new package): a copy with a .cjs
  // name in a temporary folder loads through require
  const dir = mkdtempSync(join(tmpdir(), 'polaris-draco-'));
  copyFileSync(resolve(__dirname, '../../node_modules/three/examples/jsm/libs/draco/draco_decoder.js'), join(dir, 'draco_decoder.cjs'));
  const draco = await (createRequire(import.meta.url)(join(dir, 'draco_decoder.cjs')) as (o: object) => Promise<any>)({});
  rmSync(dir, { recursive: true, force: true });
  const prims: Prim[] = [];
  for (const p of json.meshes[0].primitives) {
    const ext = p.extensions.KHR_draco_mesh_compression;
    const data = view(ext.bufferView);
    const decoder = new draco.Decoder();
    const db = new draco.DecoderBuffer();
    db.Init(new Int8Array(data.buffer, data.byteOffset, data.byteLength), data.byteLength);
    const mesh = new draco.Mesh();
    if (!decoder.DecodeBufferToMesh(db, mesh).ok()) throw new Error('Draco decode failed');
    const floats = (id: number, size: number) => {
      const a = new draco.DracoFloat32Array();
      decoder.GetAttributeFloatForAllPoints(mesh, decoder.GetAttributeByUniqueId(mesh, id), a);
      const out = new Float32Array(mesh.num_points() * size);
      for (let i = 0; i < out.length; i++) out[i] = a.GetValue(i);
      draco.destroy(a);
      return out;
    };
    const idx = new Uint32Array(mesh.num_faces() * 3);
    const ia = new draco.DracoInt32Array();
    for (let f = 0; f < mesh.num_faces(); f++) {
      decoder.GetFaceFromMesh(mesh, f, ia);
      for (let k = 0; k < 3; k++) idx[3 * f + k] = ia.GetValue(k);
    }
    draco.destroy(ia);
    const mat = json.materials[p.material];
    const img = json.images[json.textures[mat.pbrMetallicRoughness.baseColorTexture.index].source];
    prims.push({ pos: floats(ext.attributes.POSITION, 3), uv: floats(ext.attributes.TEXCOORD_0, 2), idx, material: mat.name, texSize: jpegSize(view(img.bufferView)) });
    draco.destroy(mesh);
    draco.destroy(db);
    draco.destroy(decoder);
  }
  return { json, prims };
}
/** where a ray from the model's centre along `d` meets a primitive: the texture coordinates there, or null */
function hitUv(p: Prim, d: Vec3): [number, number] | null {
  const { pos, uv, idx } = p;
  for (let t = 0; t < idx.length; t += 3) {
    const a = idx[t] * 3;
    const b = idx[t + 1] * 3;
    const c = idx[t + 2] * 3;
    // quick reject: the triangle's first corner must be within a few degrees of the ray
    const ra = Math.hypot(pos[a], pos[a + 1], pos[a + 2]);
    if ((pos[a] * d[0] + pos[a + 1] * d[1] + pos[a + 2] * d[2]) / ra < 0.999) continue;
    const e1 = [pos[b] - pos[a], pos[b + 1] - pos[a + 1], pos[b + 2] - pos[a + 2]];
    const e2 = [pos[c] - pos[a], pos[c + 1] - pos[a + 1], pos[c + 2] - pos[a + 2]];
    const h = [d[1] * e2[2] - d[2] * e2[1], d[2] * e2[0] - d[0] * e2[2], d[0] * e2[1] - d[1] * e2[0]];
    const det = e1[0] * h[0] + e1[1] * h[1] + e1[2] * h[2];
    if (Math.abs(det) < 1e-12) continue;
    const s = [-pos[a], -pos[a + 1], -pos[a + 2]];
    const u = (s[0] * h[0] + s[1] * h[1] + s[2] * h[2]) / det;
    if (u < -1e-9 || u > 1 + 1e-9) continue;
    const q = [s[1] * e1[2] - s[2] * e1[1], s[2] * e1[0] - s[0] * e1[2], s[0] * e1[1] - s[1] * e1[0]];
    const v = (d[0] * q[0] + d[1] * q[1] + d[2] * q[2]) / det;
    if (v < -1e-9 || u + v > 1 + 1e-9) continue;
    if ((e2[0] * q[0] + e2[1] * q[1] + e2[2] * q[2]) / det <= 0) continue;
    const w = 1 - u - v;
    const [ia, ib, ic] = [idx[t] * 2, idx[t + 1] * 2, idx[t + 2] * 2];
    return [w * uv[ia] + u * uv[ib] + v * uv[ic], w * uv[ia + 1] + u * uv[ib + 1] + v * uv[ic + 1]];
  }
  return null;
}

describe.skipIf(!hasModel)('the v2 globe file (public/globe/polaris_moon_globe.glb)', () => {
  it('is the file its manifest describes: same bytes, same SHA-256, same axes sentence as the model carries inside', () => {
    const bytes = readFileSync(glbPath);
    expect(bytes.length).toBe(entry!.bytes);
    expect(createHash('sha256').update(bytes).digest('hex')).toBe(entry!.sha256);
    const jl = bytes.readUInt32LE(12);
    const json = JSON.parse(bytes.subarray(20, 20 + jl).toString('utf8'));
    const inside = JSON.parse(json.scenes[0].extras.polaris);
    expect(inside.axes).toBe(entry!.axes);
    expect(inside.labels.heights).toBe(entry!.labels!.heights);
    expect(inside.labels.webBaseColour).toBe(entry!.labels!.webBaseColour);
    expect(inside.textureCredit).toBe(entry!.textureCredit);
    expect((json.extensionsRequired ?? []).includes('KHR_draco_mesh_compression')).toBe(entry!.draco);
  });

  it('the three sites and the typed points fall on the image pixel the builder gave their latitude and longitude, within one pixel', async () => {
    const { prims } = await loadV2();
    expect(prims).toHaveLength(6);
    const yaw = yawFromAxes(entry!.axes)!;
    let worst = 0;
    for (const [name, lat, lon] of points) {
      // the direction the app draws this point in (pins, the dropped marker, typed coordinates), in the model's own axes
      const own = toModelAxes(moonDir(lat, lon), yaw);
      const want = cubeFaceTexel(lat, lon, prims[0].texSize);
      const hits = prims.map((p, i) => ({ i, uv: hitUv(p, own) })).filter((h) => h.uv);
      expect(hits.length, `${name} ${lat}, ${lon}: on the mesh`).toBeGreaterThan(0);
      // a point on a face edge may be met in either face; take the builder's face when it is among them
      const hit = hits.find((h) => h.i === want.face) ?? hits[0];
      expect(hit.i, `${name} ${lat}, ${lon}: cube face`).toBe(want.face);
      expect(prims[hit.i].material).toContain(`WAC face ${want.face} `);
      const n = prims[hit.i].texSize;
      const err = Math.hypot(hit.uv![0] * n - want.x, hit.uv![1] * n - want.y);
      worst = Math.max(worst, err);
      expect(err, `${name} ${lat}, ${lon}: ${err.toFixed(3)} px`).toBeLessThan(1);
    }
    // eslint-disable-next-line no-console
    console.log(`v2 globe: worst distance from the builder's pixel over ${points.length} points = ${worst.toFixed(3)} px of ${prims[0].texSize}`);
  }, 60_000);

  it('its mean radius is the manifest’s radius to a part in a thousand, in the manifest’s unit', async () => {
    const { prims } = await loadV2();
    let sum = 0;
    let n = 0;
    for (const p of prims) for (let i = 0; i < p.pos.length; i += 3 * 17) (sum += Math.hypot(p.pos[i], p.pos[i + 1], p.pos[i + 2])), n++;
    const e = entry as GlobeManifestEntry & { radiusKm: number; units: string };
    expect(e.units).toBe('km');
    expect(Math.abs(sum / n / e.radiusKm - 1)).toBeLessThan(1e-3);
  }, 60_000);
});
