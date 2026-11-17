// Repeats the orientation fit of the Moon model quoted in src/simple/globeMath.ts. DISPLAY-ONLY check, not part of the app.
//   1. reference: curl -o ref.jpg https://svs.gsfc.nasa.gov/vis/a000000/a004700/a004720/lroc_color_poles_1k.jpg
//                 sips -s format bmp ref.jpg --out ref.bmp
//   2. model image: run scripts/make_globe_lite.mjs once, or extract the GLB image yourself, then
//                 sips -Z 1024 -s format bmp <image> --out tex.bmp
//   3. node scripts/globe_orientation.mjs public/globe/NASA_SVS_moon_small.glb tex.bmp ref.bmp
// Prints the best axis assignments (rows: Moon x = lon 0, y = 90 E, z = north, in model axes) with their correlation,
// and the correlation after turning the best one by a few degrees about each axis.
import fs from 'node:fs';
function bmp(p) {
  const b = fs.readFileSync(p); const off = b.readUInt32LE(10), w = b.readInt32LE(18), h0 = b.readInt32LE(22), bpp = b.readUInt16LE(28) / 8;
  const h = Math.abs(h0), row = Math.ceil((w * bpp) / 4) * 4;
  return { w, h, at(u, v) { const x = Math.min(w - 1, Math.max(0, Math.floor(u * w))), y0 = Math.min(h - 1, Math.max(0, Math.floor(v * h))); const y = h0 > 0 ? h - 1 - y0 : y0; const i = off + y * row + x * bpp; return (b[i] + b[i + 1] + b[i + 2]) / 3; } };
}
const [,, glb, texP, refP] = process.argv;
const tex = bmp(texP), ref = bmp(refP);
const buf = fs.readFileSync(glb); const clen = buf.readUInt32LE(12); const j = JSON.parse(buf.subarray(20, 20 + clen).toString()); const bin = buf.subarray(20 + clen + 8);
const bv = j.bufferViews, n = j.accessors[0].count;
const cp = (o, len) => new Float32Array(bin.buffer.slice(bin.byteOffset + o, bin.byteOffset + o + len));
const pos = cp(bv[0].byteOffset, n * 12), uv = cp(bv[2].byteOffset, n * 8);
const pts = [];
for (let i = 0; i < n; i++) { const x = pos[3 * i], y = pos[3 * i + 1], z = pos[3 * i + 2], r = Math.hypot(x, y, z); pts.push({ d: [x / r, y / r, z / r], t: tex.at(uv[2 * i], uv[2 * i + 1]), r }); }
// moon frame M: x = lon0 lat0, y = 90E, z = north. m = R * d(model)
function score(R) {
  let sa = 0, sb = 0, saa = 0, sbb = 0, sab = 0, k = 0;
  for (const p of pts) {
    const d = p.d; const m = [0, 1, 2].map((i) => R[i][0] * d[0] + R[i][1] * d[1] + R[i][2] * d[2]);
    const lat = Math.asin(Math.max(-1, Math.min(1, m[2]))), lon = Math.atan2(m[1], m[0]);
    if (Math.abs(lat) > 1.3) continue; // reference poles are filled in that kit image
    const b = ref.at(lon / (2 * Math.PI) + 0.5, 0.5 - lat / Math.PI), a = p.t;
    sa += a; sb += b; saa += a * a; sbb += b * b; sab += a * b; k++;
  }
  return (sab - sa * sb / k) / Math.sqrt((saa - sa * sa / k) * (sbb - sb * sb / k));
}
const perms = [[0, 1, 2], [0, 2, 1], [1, 0, 2], [1, 2, 0], [2, 0, 1], [2, 1, 0]];
const out = [];
for (const p of perms) for (let s = 0; s < 8; s++) {
  const R = [0, 1, 2].map((i) => [0, 1, 2].map((c) => (c === p[i] ? (s >> i) & 1 ? -1 : 1 : 0)));
  const det = R[0][0] * (R[1][1] * R[2][2] - R[1][2] * R[2][1]) - R[0][1] * (R[1][0] * R[2][2] - R[1][2] * R[2][0]) + R[0][2] * (R[1][0] * R[2][1] - R[1][1] * R[2][0]);
  out.push({ R, det, c: score(R) });
}
out.sort((a, b) => b.c - a.c);
for (const o of out.slice(0, 5)) console.log(o.c.toFixed(4), 'det', o.det, JSON.stringify(o.R));
// refine best with small rotations about each moon axis
const best = out[0];
const rot = (ax, a) => { const c = Math.cos(a), s = Math.sin(a); return ax === 0 ? [[1, 0, 0], [0, c, -s], [0, s, c]] : ax === 1 ? [[c, 0, s], [0, 1, 0], [-s, 0, c]] : [[c, -s, 0], [s, c, 0], [0, 0, 1]]; };
const mul = (A, B) => A.map((r) => [0, 1, 2].map((c) => r[0] * B[0][c] + r[1] * B[1][c] + r[2] * B[2][c]));
for (const ax of [0, 1, 2]) { let line = `axis ${ax}:`; for (const deg of [-4, -2, -1, -0.5, 0, 0.5, 1, 2, 4]) line += ` ${deg}:${score(mul(rot(ax, (deg * Math.PI) / 180), best.R)).toFixed(4)}`; console.log(line); }
// radius vs lat sanity: mean radius near poles vs equator in best frame; and highest/lowest points
let hi = pts[0], lo = pts[0]; for (const p of pts) { if (p.r > hi.r) hi = p; if (p.r < lo.r) lo = p; }
const ll = (p) => { const m = [0, 1, 2].map((i) => best.R[i][0] * p.d[0] + best.R[i][1] * p.d[1] + best.R[i][2] * p.d[2]); return [(Math.asin(m[2]) * 180 / Math.PI).toFixed(1), (Math.atan2(m[1], m[0]) * 180 / Math.PI).toFixed(1), p.r.toFixed(4)]; };
console.log('highest', ll(hi), 'lowest', ll(lo));
