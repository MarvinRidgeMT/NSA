// v2 T2 (docs/v2/PHASE_7_T2_PLAN.md): stage the globe inputs the viewer reads. Runs on every build after sync-bundles.
// All outputs are git-ignored. Nothing here edits a science file; it copies and describes.
//   1. public/draco/            three.js Draco decoder (the Blender globe GLB is Draco-compressed)
//   2. public/anysite/precompute_summary.json   copy of ../data/anysite/precompute_summary.json (+ .meta.json with SHA-256)
//   3. public/globe/globe_manifest.json         which globe GLBs exist, read from their own glTF JSON (generator,
//                                               scenes[0].extras.polaris, SHA-256), primary = Blender globe when present
import { createHash } from 'node:crypto';
import { copyFileSync, existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const web = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const repo = resolve(web, '..');
const pub = join(web, 'public');
const sha = (b) => createHash('sha256').update(b).digest('hex');

// 1. Draco decoder
const dracoSrc = join(web, 'node_modules', 'three', 'examples', 'jsm', 'libs', 'draco', 'gltf');
if (existsSync(dracoSrc)) {
  mkdirSync(join(pub, 'draco'), { recursive: true });
  for (const f of readdirSync(dracoSrc)) copyFileSync(join(dracoSrc, f), join(pub, 'draco', f));
}

// 2. any-site precompute summary
const sumSrc = join(repo, 'data', 'anysite', 'precompute_summary.json');
if (existsSync(sumSrc)) {
  mkdirSync(join(pub, 'anysite'), { recursive: true });
  const bytes = readFileSync(sumSrc);
  writeFileSync(join(pub, 'anysite', 'precompute_summary.json'), bytes);
  writeFileSync(
    join(pub, 'anysite', 'precompute_summary.meta.json'),
    JSON.stringify({ source: 'data/anysite/precompute_summary.json', sha256: sha(bytes), bytes: bytes.length, copiedBy: 'web/scripts/sync-globe.mjs' }, null, 1),
  );
}

// 3. globe manifest
function gltfJson(buf) {
  if (buf.readUInt32LE(0) !== 0x46546c67) throw new Error('not a GLB');
  const len = buf.readUInt32LE(12);
  return JSON.parse(buf.subarray(20, 20 + len).toString('utf8'));
}
function extrasPolaris(j) {
  for (const sc of j.scenes ?? []) {
    let x = sc?.extras?.polaris;
    if (typeof x === 'string') {
      try {
        x = JSON.parse(x);
      } catch {
        x = null;
      }
    }
    if (x && typeof x === 'object') return x;
  }
  return null;
}
const globeDir = join(pub, 'globe');
const candidates = [
  { file: 'polaris_moon_globe.glb', role: 'primary', kind: 'blender' },
  { file: 'NASA_SVS_moon_small.glb', role: 'fallback', kind: 'svs' },
];
const globes = [];
for (const c of candidates) {
  const p = join(globeDir, c.file);
  if (!existsSync(p)) continue;
  const bytes = readFileSync(p);
  let generator = null;
  let polaris = null;
  let draco = false;
  try {
    const j = gltfJson(bytes);
    generator = j.asset?.generator ?? null;
    polaris = extrasPolaris(j);
    draco = (j.extensionsUsed ?? []).includes('KHR_draco_mesh_compression');
  } catch (e) {
    generator = `unreadable: ${e.message}`;
  }
  // the Blender globe counts only when it names the POLARIS builder (same rule as blender/tests/glb_proof.py)
  const blenderOk = c.kind === 'blender' && (generator ?? '').startsWith('Khronos glTF Blender I/O') && polaris?.builder === 'blender/v2/globe.py';
  if (c.kind === 'blender' && !blenderOk) continue;
  globes.push({
    url: `globe/${c.file}`,
    role: c.role,
    kind: c.kind,
    sha256: sha(bytes),
    bytes: bytes.length,
    generator,
    draco,
    builder: polaris?.builder ?? null,
    tag: polaris?.tag ?? null,
    blender: polaris?.blender ?? null,
    units: polaris?.units ?? null,
    axes: polaris?.axes ?? null,
    radiusKm: polaris?.radiusKm ?? null,
    labels: polaris?.labels ?? null,
    heightsSource: polaris?.heightsSource ?? null,
    textureCredit: polaris?.textureCredit ?? null,
  });
}
mkdirSync(globeDir, { recursive: true });
writeFileSync(join(globeDir, 'globe_manifest.json'), JSON.stringify({ schema: 'polaris-globe-manifest-v1', writtenBy: 'web/scripts/sync-globe.mjs', globes }, null, 1));
console.log(`sync-globe: ${globes.map((g) => `${g.kind}(${g.role})`).join(', ') || 'no globe GLB'}; draco ${existsSync(join(pub, 'draco')) ? 'ok' : 'missing'}; anysite ${existsSync(sumSrc) ? 'ok' : 'missing'}`);
