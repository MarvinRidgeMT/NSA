"""JPL Horizons observer ephemerides for a lunar surface site.

Query: CENTER='coord@301', COORD_TYPE=GEODETIC, SITE_COORD='E-lon,lat,alt_km'
(Horizons uses the 1737.4 km sphere for body 301, the same reference as LOLA LDEM,
so alt_km = DEM height above that sphere). QUANTITIES 4 (airless apparent az/el of
target CENTRE, az clockwise from local north), 13 (angular diameter), 20 (range).
Every raw response is archived byte-for-byte under data/raw/horizons/ with SHA-256
in MANIFEST.json. Parsing locates columns by header name, never by position.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import time
from pathlib import Path

API = 'https://ssd.jpl.nasa.gov/api/horizons.api'
ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / 'data' / 'raw' / 'horizons'
MONTHS = {m: i + 1 for i, m in enumerate('Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split())}

_COLS = {  # canonical key -> header regex
    'az_deg': re.compile(r'^Azi', re.I),
    'el_deg': re.compile(r'^Elev', re.I),
    'ang_diam_arcsec': re.compile(r'^Ang-diam', re.I),
    'range_au': re.compile(r'^delta$', re.I),
}
_REQUIRED = ('az_deg', 'el_deg')


def build_params(target, lat, lon, height_m, start=None, stop=None, step=None, tlist=None):
    p = {'format': 'text', 'COMMAND': f"'{target}'", 'OBJ_DATA': 'NO', 'MAKE_EPHEM': 'YES',
         'EPHEM_TYPE': 'OBSERVER', 'CENTER': "'coord@301'", 'COORD_TYPE': 'GEODETIC',
         'SITE_COORD': f"'{lon % 360:.7f},{lat:.7f},{height_m / 1000.0:.6f}'",
         'QUANTITIES': "'4,13,20'", 'CSV_FORMAT': 'YES', 'ANG_FORMAT': 'DEG', 'APPARENT': 'AIRLESS',
         'EXTRA_PREC': 'YES', 'TIME_DIGITS': 'FRACSEC', 'CAL_FORMAT': 'CAL', 'TIME_TYPE': 'UT'}
    if tlist is not None:
        p['TLIST'] = ' '.join(f"'{jd:.9f}'" for jd in tlist)
        p['TLIST_TYPE'] = 'JD'
    else:
        p.update({'START_TIME': f"'{start}'", 'STOP_TIME': f"'{stop}'", 'STEP_SIZE': f"'{step}'"})
    return p


def parse_text(text):
    lines = text.splitlines()
    try:
        soe = next(i for i, l in enumerate(lines) if l.strip() == '$$SOE')
        eoe = next(i for i, l in enumerate(lines) if l.strip() == '$$EOE')
    except StopIteration:
        raise ValueError('Horizons response has no $$SOE/$$EOE block')
    header = next(l for l in reversed(lines[:soe]) if 'Date__' in l)
    names = [h.strip() for h in header.split(',')]
    idx = {}
    for key, rx in _COLS.items():
        hits = [i for i, n in enumerate(names) if rx.search(n)]
        if hits:
            idx[key] = hits[0]
    for k in _REQUIRED:
        if k not in idx:
            raise ValueError(f'required column {k} missing from header {names}')
    rows = []
    for l in lines[soe + 1:eoe]:
        f = [x.strip() for x in l.split(',')]
        r = {'utc': _iso(f[0]), 'solar_flag': f[1] if len(f) > 1 else ''}
        for k, i in idx.items():
            r[k] = float(f[i]) if f[i] not in ('', 'n.a.') else None
        rows.append(r)
    return rows


def _iso(s):
    # '2026-Nov-14 00:00:00.000'
    d, t = s.split()
    y, mon, day = d.split('-')
    return f'{int(y):04d}-{MONTHS[mon]:02d}-{int(day):02d}T{t}Z'


def iso_to_unix(s):
    return dt.datetime.fromisoformat(s.replace('Z', '+00:00')).timestamp()


def unix_to_jd(t):
    return t / 86400.0 + 2440587.5


def unix_to_iso(t):
    return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'


def fetch(params, tag, raw_dir=RAW_DIR, retries=3):
    import requests
    raw_dir.mkdir(parents=True, exist_ok=True)
    for k in range(retries):
        try:
            r = requests.get(API, params=params, timeout=120)
            r.raise_for_status()
            break
        except Exception:
            if k == retries - 1:
                raise
            time.sleep(3 * (k + 1))
    body = r.content
    path = raw_dir / f'{tag}.txt'
    path.write_bytes(body)
    sha = hashlib.sha256(body).hexdigest()
    man_p = raw_dir / 'MANIFEST.json'
    with _ManifestLock(raw_dir):
        _update_manifest(man_p, path, sha, body, params)
    return body.decode('utf-8'), sha, path.relative_to(ROOT).as_posix()


class _ManifestLock:
    """Cross-platform exclusive lock (O_EXCL lock file) so parallel bundle builds cannot
    interleave read-modify-write of MANIFEST.json."""
    def __init__(self, raw_dir, timeout_s=120.0):
        self.p = Path(raw_dir) / 'MANIFEST.lock'; self.timeout_s = timeout_s

    def __enter__(self):
        import os
        t0 = time.time()
        while True:
            try:
                self.fd = os.open(self.p, os.O_CREAT | os.O_EXCL | os.O_WRONLY); return self
            except FileExistsError:
                if time.time() - t0 > self.timeout_s:
                    raise TimeoutError(f'stale lock {self.p}; delete it if no build is running')
                time.sleep(0.05)

    def __exit__(self, *exc):
        import os
        os.close(self.fd); os.remove(self.p)


def _update_manifest(man_p, path, sha, body, params):
    man = json.loads(man_p.read_text()) if man_p.exists() else []
    man = [m for m in man if m['path'] != path.relative_to(ROOT).as_posix()]
    q = {k: v for k, v in params.items() if k != 'TLIST'}
    if 'TLIST' in params:
        q['TLIST_count'] = params['TLIST'].count("'") // 2
    man.append({'path': path.relative_to(ROOT).as_posix(), 'sha256': sha, 'bytes': len(body),
                'retrieved_utc': unix_to_iso(time.time()), 'api': API, 'params': q})
    tmp = man_p.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(man, indent=1)); tmp.replace(man_p)


def ephemeris(target, lat, lon, height_m, start, stop, step, tag):
    text, sha, path = fetch(build_params(target, lat, lon, height_m, start, stop, step), tag)
    rows = parse_text(text)
    for r in rows:
        r['t'] = iso_to_unix(r['utc'])
    return rows, {'path': path, 'sha256': sha}


def ephemeris_at(target, lat, lon, height_m, unix_times, tag):
    jd = [unix_to_jd(t) for t in unix_times]
    text, sha, path = fetch(build_params(target, lat, lon, height_m, tlist=jd), tag)
    rows = parse_text(text)
    if len(rows) != len(jd):
        raise ValueError(f'TLIST returned {len(rows)} rows for {len(jd)} times')
    for r, t in zip(rows, unix_times):
        r['t'] = t
        if abs(iso_to_unix(r['utc']) - t) > 0.01:
            raise ValueError(f'TLIST time mismatch {r["utc"]} vs {unix_to_iso(t)}')
    return rows, {'path': path, 'sha256': sha}
