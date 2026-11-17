// Lighter Moon model for phones and software rendering (Simple-mode globe, S4). DISPLAY ONLY.
//   cd web && node scripts/make_globe_lite.mjs
// Reads public/globe/NASA_SVS_moon_small.glb (NASA SVS 14959 compact model), keeps its mesh untouched and replaces its
// 4096 x 4096 PNG image with a 2048 x 2048 JPEG of the same picture, written to public/globe/moon_lite.glb.
// Uses macOS `sips` for the resize. The output is git-ignored like the source model; rerun after `npm run sync-bundles`
// on a fresh checkout. When moon_lite.glb is absent the globe uses the full model on every device.
import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const web = join(dirname(fileURLToPath(import.meta.url)), '..');
const src = join(web, 'public', 'globe', 'NASA_SVS_moon_small.glb');
const out = join(web, 'public', 'globe', 'moon_lite.glb');
const SIZE = 2048;

const glb = readFileSync(src);
const jsonLen = glb.readUInt32LE(12);
const json = JSON.parse(glb.subarray(20, 20 + jsonLen).toString('utf8'));
const bin = glb.subarray(20 + jsonLen + 8, 20 + jsonLen + 8 + glb.readUInt32LE(20 + jsonLen));
if (json.images.length !== 1 || json.buffers.length !== 1) throw new Error('expected one image and one buffer');
const iv = json.bufferViews[json.images[0].bufferView];
if (iv.byteOffset + iv.byteLength !== bin.length && iv.byteOffset + iv.byteLength + 3 < bin.length) throw new Error('expected the image to be the last buffer view');

const dir = mkdtempSync(join(tmpdir(), 'moon-lite-'));
writeFileSync(join(dir, 'in.png'), bin.subarray(iv.byteOffset, iv.byteOffset + iv.byteLength));
execFileSync('sips', ['-Z', String(SIZE), '-s', 'format', 'jpeg', '-s', 'formatOptions', '82', join(dir, 'in.png'), '--out', join(dir, 'out.jpg')], { stdio: 'ignore' });
const jpg = readFileSync(join(dir, 'out.jpg'));

const pad = (b, fill) => (b.length % 4 ? Buffer.concat([b, Buffer.alloc(4 - (b.length % 4), fill)]) : b);
const newBin = pad(Buffer.concat([bin.subarray(0, iv.byteOffset), jpg]), 0);
iv.byteLength = jpg.length;
json.images[0].mimeType = 'image/jpeg';
json.buffers[0].byteLength = newBin.length;
json.asset.extras = { note: `image reduced to ${SIZE} px JPEG by web/scripts/make_globe_lite.mjs; mesh unchanged; display only` };
const newJson = pad(Buffer.from(JSON.stringify(json), 'utf8'), 0x20);
const head = Buffer.alloc(12);
head.writeUInt32LE(0x46546c67, 0);
head.writeUInt32LE(2, 4);
head.writeUInt32LE(12 + 8 + newJson.length + 8 + newBin.length, 8);
const chunk = (len, type) => { const b = Buffer.alloc(8); b.writeUInt32LE(len, 0); b.writeUInt32LE(type, 4); return b; };
writeFileSync(out, Buffer.concat([head, chunk(newJson.length, 0x4e4f534a), newJson, chunk(newBin.length, 0x004e4942), newBin]));
console.log(`moon_lite.glb: ${(readFileSync(out).length / 1e6).toFixed(2)} MB (source ${(glb.length / 1e6).toFixed(2)} MB), image ${SIZE} px JPEG ${(jpg.length / 1e6).toFixed(2)} MB`);
