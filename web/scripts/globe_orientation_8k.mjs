// Orientation of the 8k Moon model quoted in src/simple/globeMath.ts. DISPLAY-ONLY check, not part of the app.
//   mkdir -p /tmp/fit8k && node scripts/globe_orientation_8k.mjs public/globe/NASA_SVS_Moon_NASA_LRO_8k_Topo_Small.glb public/globe/NASA_SVS_moon_small.glb /tmp/fit8k
// 1. Reads the model's own texture coordinates and fits the axis assignment that maps each vertex direction to its image
//    longitude / latitude (equirectangular, longitude 0 at the image centre, north up). Prints the fit and its misfit.
// 2. Checks that image layout: samples the 8k image at the compact model's vertices (whose frame was fitted against NASA's
//    CGI Moon Kit, scripts/globe_orientation.mjs) and correlates the two images, also with shifts, flips and mirroring.
// 3. Prints the relief range of the mesh (radius about its origin) and how far its normals lean from the radial direction.
// Uses macOS `sips` to decode the images into the output folder (third argument).
import fs from 'node:fs';
import { execFileSync } from 'node:child_process';
const [,, big, small, out] = process.argv;
function glb(p) {
  const buf = fs.readFileSync(p); const clen = buf.readUInt32LE(12); const j = JSON.parse(buf.subarray(20, 20 + clen).toString()); const bin = buf.subarray(20 + clen + 8);
  const acc = (i) => { const a = j.accessors[i], bv = j.bufferViews[a.bufferView]; const n = a.count * (a.type === 'VEC3' ? 3 : a.type === 'VEC2' ? 2 : 1); const o = bin.byteOffset + (bv.byteOffset || 0) + (a.byteOffset || 0); if (bv.byteStride && bv.byteStride !== (a.type==='VEC3'?12:8)) throw new Error('stride'); return new Float32Array(bin.buffer.slice(o, o + n * 4)); };
  const pr = j.meshes[0].primitives[0];
  const iv = j.bufferViews[j.images[0].bufferView];
  return { j, pos: acc(pr.attributes.POSITION), nrm: acc(pr.attributes.NORMAL), uv: acc(pr.attributes.TEXCOORD_0), img: bin.subarray(iv.byteOffset || 0, (iv.byteOffset || 0) + iv.byteLength), mime: j.images[0].mimeType, node: j.nodes };
}
function bmp(p) {
  const b = fs.readFileSync(p); const off = b.readUInt32LE(10), w = b.readInt32LE(18), h0 = b.readInt32LE(22), bpp = b.readUInt16LE(28) / 8;
  const h = Math.abs(h0), row = Math.ceil((w * bpp) / 4) * 4;
  return { w, h, at(u, v) { const x = Math.min(w - 1, Math.max(0, Math.floor(u * w))), y0 = Math.min(h - 1, Math.max(0, Math.floor(v * h))); const y = h0 > 0 ? h - 1 - y0 : y0; const i = off + y * row + x * bpp; return (b[i] + b[i + 1] + b[i + 2]) / 3; } };
}
const toBmp = (g, name, z) => { const ext = g.mime === 'image/png' ? 'png' : 'jpg'; fs.writeFileSync(`${out}/${name}.${ext}`, g.img); execFileSync('sips', ['-Z', String(z), '-s', 'format', 'bmp', `${out}/${name}.${ext}`, '--out', `${out}/${name}.bmp`], { stdio: 'ignore' }); return bmp(`${out}/${name}.bmp`); };
const B = glb(big), S = glb(small);
console.log('8k node', JSON.stringify(B.node));
const n = B.pos.length / 3;
// centre + radius
let mn = [1e9,1e9,1e9], mx = [-1e9,-1e9,-1e9];
for (let i = 0; i < n; i++) for (let k = 0; k < 3; k++) { const v = B.pos[3*i+k]; if (v < mn[k]) mn[k] = v; if (v > mx[k]) mx[k] = v; }
const c = mn.map((a, k) => (a + mx[k]) / 2);
let cm = [0,0,0]; for (let i = 0; i < n; i++) for (let k = 0; k < 3; k++) cm[k] += B.pos[3*i+k] / n;
console.log('bbox centre', c.map((x) => x.toFixed(5)), 'vertex mean', cm.map((x) => x.toFixed(5)));
let rs = 0, rmin = 9, rmax = 0, ang = 0, angMax = 0, M = [[0,0,0],[0,0,0],[0,0,0]], hi, lo;
const rr = new Float32Array(n);
for (let i = 0; i < n; i++) {
  const x = B.pos[3*i], y = B.pos[3*i+1], z = B.pos[3*i+2], r = Math.hypot(x, y, z); rr[i] = r; rs += r;
  if (r < rmin) { rmin = r; lo = i; } if (r > rmax) { rmax = r; hi = i; }
  const d = [x / r, y / r, z / r];
  const a = Math.acos(Math.min(1, d[0]*B.nrm[3*i] + d[1]*B.nrm[3*i+1] + d[2]*B.nrm[3*i+2])); ang += a; if (a > angMax) angMax = a;
  const u = B.uv[2*i], v = B.uv[2*i+1];
  const lon = (u - 0.5) * 2 * Math.PI, lat = (0.5 - v) * Math.PI;
  const m = [Math.cos(lat) * Math.cos(lon), Math.cos(lat) * Math.sin(lon), Math.sin(lat)];
  for (let a2 = 0; a2 < 3; a2++) for (let b2 = 0; b2 < 3; b2++) M[a2][b2] += m[a2] * d[b2];
}
const mean = rs / n;
console.log('radius about origin: mean', mean.toFixed(5), 'min', rmin.toFixed(5), 'max', rmax.toFixed(5), '=> relief', ((rmin/mean-1)*100).toFixed(2)+'%', ((rmax/mean-1)*100).toFixed(2)+'%', ' real Moon: about -0.52% .. +0.62% (−9.1 km .. +10.8 km of 1737.4 km)');
console.log('normal vs radial: mean', (ang / n * 180 / Math.PI).toFixed(2), 'deg, max', (angMax * 180 / Math.PI).toFixed(1));
console.log('UV fit  m(x=lon0,y=90E,z=north) = R d(model);  R*3/n rows:'); for (const r of M) console.log('  ', r.map((x) => (x * 3 / n).toFixed(4)).join(' '));
const R = M.map((r) => r.map((x) => Math.round(x * 3 / n)));
console.log('R rounded', JSON.stringify(R));
const ll = (i) => { const d = [B.pos[3*i]/rr[i], B.pos[3*i+1]/rr[i], B.pos[3*i+2]/rr[i]]; const m = R.map((r) => r[0]*d[0]+r[1]*d[1]+r[2]*d[2]); return `lat ${(Math.asin(m[2])*180/Math.PI).toFixed(1)} lon ${(Math.atan2(m[1], m[0])*180/Math.PI).toFixed(1)} r ${rr[i].toFixed(4)} uv ${B.uv[2*i].toFixed(3)},${B.uv[2*i+1].toFixed(3)}`; };
console.log('highest', ll(hi), '| lowest', ll(lo));
// residual of the UV fit
let res = 0, resMax = 0, cnt = 0;
for (let i = 0; i < n; i += 5) { const d = [B.pos[3*i]/rr[i], B.pos[3*i+1]/rr[i], B.pos[3*i+2]/rr[i]]; const m = R.map((r) => r[0]*d[0]+r[1]*d[1]+r[2]*d[2]); const u = B.uv[2*i], v = B.uv[2*i+1]; const lon = (u - 0.5) * 2 * Math.PI, lat = (0.5 - v) * Math.PI; const e = Math.acos(Math.min(1, m[0]*Math.cos(lat)*Math.cos(lon) + m[1]*Math.cos(lat)*Math.sin(lon) + m[2]*Math.sin(lat))); res += e; cnt++; if (e > resMax) resMax = e; }
console.log('UV-fit residual: mean', (res/cnt*180/Math.PI).toFixed(3), 'deg, max', (resMax*180/Math.PI).toFixed(2));
// image check against the compact model (frame fitted earlier against NASA CGI Moon Kit: +Y north, lon0 = -Z, 90E = -X)
const tb = toBmp(B, 'big', 2048), ts = toBmp(S, 'small', 1024);
const sn = S.pos.length / 3; const pts = [];
for (let i = 0; i < sn; i++) { const x = S.pos[3*i], y = S.pos[3*i+1], z = S.pos[3*i+2], r = Math.hypot(x, y, z); const m = [-z / r, -x / r, y / r]; pts.push({ lat: Math.asin(m[2]), lon: Math.atan2(m[1], m[0]), t: ts.at(S.uv[2*i], S.uv[2*i+1]) }); }
const corr = (f) => { let sa=0,sb=0,saa=0,sbb=0,sab=0,k=0; for (const p of pts) { if (Math.abs(p.lat) > 1.3) continue; const [u, v] = f(p); const b = tb.at(((u % 1) + 1) % 1, v), a = p.t; sa+=a;sb+=b;saa+=a*a;sbb+=b*b;sab+=a*b;k++; } return (sab - sa*sb/k) / Math.sqrt((saa - sa*sa/k) * (sbb - sb*sb/k)); };
for (const sh of [0, 0.25, 0.5, 0.75]) console.log('8k image vs compact model image, lon0 at u =', (0.5 + sh) % 1, ': north-up', corr((p) => [p.lon / (2*Math.PI) + 0.5 + sh, 0.5 - p.lat / Math.PI]).toFixed(4), 'south-up', corr((p) => [p.lon / (2*Math.PI) + 0.5 + sh, 0.5 + p.lat / Math.PI]).toFixed(4), 'mirrored', corr((p) => [-p.lon / (2*Math.PI) + 0.5 + sh, 0.5 - p.lat / Math.PI]).toFixed(4));
for (const dd of [-2,-1,-0.5,0,0.5,1,2]) console.log('  lon shift', dd, 'deg', corr((p) => [(p.lon + dd*Math.PI/180) / (2*Math.PI) + 0.5, 0.5 - p.lat / Math.PI]).toFixed(4), ' lat shift', corr((p) => [p.lon / (2*Math.PI) + 0.5, 0.5 - (p.lat + dd*Math.PI/180) / Math.PI]).toFixed(4));
