#!/usr/bin/env python3
"""Copy the committed batch Coverage Gauge (a-science data/batch/2026-11-14/certainty_height/coverage_gauge.json)
into web/public/certainty/coverage.json with its SHA-256, so the viewer can show it next to clone-agreement claims.

Stdlib only. No value is computed or changed here: the numbers are copied verbatim from the batch file.
Definition (BATCH_RESULTS_THIRD): share of window hours, nominal DEM, 1 m mast, whose skyline-controlling cell lies
inside the clone tile (inscribed radius). It is a coverage share, never a probability.
"""
import hashlib, json, pathlib, sys

repo = pathlib.Path(__file__).resolve().parents[2]
src = repo / 'data/batch/2026-11-14/certainty_height/coverage_gauge.json'
out = repo / 'web/public/certainty/coverage.json'
if not src.exists():
    sys.exit(f'missing {src}')
raw = src.read_bytes()
data = json.loads(raw)
sites = {}
for key, val in data.items():  # "Site04_ROI3" -> "site04_roi3" (the bundle siteId convention)
    sites[key.lower()] = {
        'tile_inscribed_radius_m': val['tile_inscribed_radius_m'],
        'sun_pct': val['pct_hours_controlling_cell_inside_clone_tile']['sun'],
        'earth_pct': val['pct_hours_controlling_cell_inside_clone_tile']['earth'],
    }
doc = {
    'format': 'polaris-coverage-sidecar-v1',
    'status': 'SOURCE_BASED_UNVALIDATED',
    'definition': 'share of window hours (14-28 Nov 2026, 1 h, nominal DEM, 1 m mast) whose skyline-controlling cell lies inside the clone tile; not a probability',
    'source': {'path': str(src.relative_to(repo)), 'sha256': hashlib.sha256(raw).hexdigest(), 'repo_commit': '971df9a (a-science)', 'record': 'claude/BATCH_RESULTS_THIRD_2026-11-14.md'},
    'sites': sites,
}
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(doc, indent=2, sort_keys=True) + '\n')
print(f'wrote {out.relative_to(repo)}: {sites}')
