// S14 Part A (18 Nov 2026): the web copy of the any-site results for Simple mode's "Check a spot" and pin cards.
//
// Reads  ../data/anysite/precompute_summary.json  (POLARIS v2, Anish Meruva; copied from origin/feature/v2-whole-moon)
// Writes public/anysite/points.json: every row of the original, with only the fields the page shows. Values are copied, never
// recomputed or rounded; rows without a result ("needs coordinates") are kept as they are, so the page's own rule skips them.
//
//   node scripts/build_anysite_web.mjs           write the copy
//   node scripts/build_anysite_web.mjs --check   exit 1 if the copy on disk is not what this script would write
//
// tests/unit/any-site.test.ts compares the copy with the original field by field, without using this script.
import { createHash } from 'node:crypto';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const web = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const SOURCE = 'data/anysite/precompute_summary.json';
/** where the original came from (docs/DATA_PROVENANCE.md records the same commit and the file's SHA-256) */
const ORIGIN = { branch: 'feature/v2-whole-moon', commit: '2ee08d19d50ee98ebe87cd95765fd62f62ed95a5' };
/** fields copied for every row that has them, under their original names */
const KEPT = ['id', 'name', 'group', 'lat', 'lon', 'status', 'reason', 'slope_deg', 'sun_pct', 'earth_pct', 'sun_earth_pct', 'longest_sun_gap_h'];
/** the one member of `uncertainty` the page shows: the range across the PGDA 78 terrain clones, copied whole when present */
const CLONES = 'pgda78-clone';

const bytes = readFileSync(join(web, '..', SOURCE));
const src = JSON.parse(bytes.toString('utf8'));
if (src.schema !== 'polaris-anysite-precompute-summary-v1') throw new Error(`unexpected schema ${src.schema}`);

const sites = src.sites.map((s) => {
  const row = {};
  for (const k of KEPT) if (k in s) row[k] = s[k];
  if (s.uncertainty && CLONES in s.uncertainty) row.uncertainty = { [CLONES]: s.uncertainty[CLONES] };
  return row;
});
const head = {
  schema: 'POLARIS-X-anysite-web-v1',
  credit: 'Any-site results: POLARIS v2 (Anish Meruva)',
  source: { file: SOURCE, schema: src.schema, sha256: createHash('sha256').update(bytes).digest('hex'), bytes: bytes.length, ...ORIGIN },
  label: src.label,
  window: src.window,
  counts: src.counts,
  kept: [...KEPT, `uncertainty.${CLONES}`],
};
// one row per line: small enough to read in a diff, and it compresses well
const text = `${JSON.stringify(head).slice(0, -1)},"sites":[\n${sites.map((s) => JSON.stringify(s)).join(',\n')}\n]}\n`;
JSON.parse(text);

const out = join(web, 'public', 'anysite', 'points.json');
if (process.argv.includes('--check')) {
  if (!existsSync(out) || readFileSync(out, 'utf8') !== text) {
    console.error(`${out} is not what ${SOURCE} gives; run: node scripts/build_anysite_web.mjs`);
    process.exit(1);
  }
  console.log(`ok: ${out} matches ${SOURCE}`);
} else {
  mkdirSync(dirname(out), { recursive: true });
  writeFileSync(out, text);
  console.log(`${out}: ${sites.length} rows, ${text.length} bytes (original ${bytes.length}), sha256 of original ${head.source.sha256}`);
}
