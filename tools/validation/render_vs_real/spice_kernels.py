"""NAIF LRO SPICE kernels (PDS archive lro-l-spice-6-v1.0, public, no login): listing, per-time selection, resumable download.

Every downloaded kernel's URL, size, SHA-256 and retrieval UTC is appended to $POLARIS_DATA/v2/render_vs_real/spice/MANIFEST.jsonl.
Directory listings are cached (spice/listing_<dir>.html) so selection is reproducible without the network.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import time
from pathlib import Path

from .common import SPICE_DIR, USER_AGENT, sha256_file

BASE = 'https://naif.jpl.nasa.gov/pub/naif/pds/data/lro-l-spice-6-v1.0/lrosp_1000/data'
# Generic + LRO static kernels (fixed names; newest versions in the PDS archive on 16 Nov 2026).
STATIC = ['lsk/naif0012.tls', 'pck/pck00010.tpc', 'pck/moon_pa_de421_1900_2050.bpc', 'fk/moon_080317.tf',
          'fk/moon_assoc_me.tf', 'fk/lro_frames_2014049_v01.tf', 'ik/lro_lroc_v20.ti', 'spk/de421.bsp',
          'sclk/lro_clkcor_2026167_v00.tsc']
NAME = re.compile(r'^(lrosc|lrolc|lrorg)_(\d{7})_(\d{7})_v(\d+)\.(bc|bsp)$')


def _doy(s):
    return dt.datetime.strptime(s, '%Y%j')


def listing(subdir, refresh=False, get=None):
    """Kernel file names with sizes from the cached NAIF directory listing."""
    SPICE_DIR.mkdir(parents=True, exist_ok=True)
    p = SPICE_DIR / f'listing_{subdir}.html'
    if refresh or not p.exists():
        get = get or _get
        p.write_bytes(get(f'{BASE}/{subdir}/'))
    txt = re.sub(r'<[^>]+>', ' ', p.read_text(errors='replace'))
    out = []
    for m in re.finditer(r'(\S+\.(?:bc|bsp))\s+\d{4}-\d\d-\d\d \d\d:\d\d\s+([\d.]+[KMG]?)', txt):
        out.append((m.group(1), m.group(2)))
    return out


def size_bytes(s):
    mult = {'K': 1e3, 'M': 1e6, 'G': 1e9}
    return float(s[:-1]) * mult[s[-1]] if s[-1] in mult else float(s)


def windows(kind, files):
    """[(start, stop, name, size_str)] for one kernel family, keeping the highest version per period."""
    best = {}
    for name, size in files:
        m = NAME.match(name)
        if not m or m.group(1) != kind:
            continue
        key = (m.group(2), m.group(3))
        if key not in best or int(m.group(4)) > best[key][0]:
            best[key] = (int(m.group(4)), name, size)
    return sorted((_doy(a), _doy(b), n, s) for (a, b), (_v, n, s) in best.items())


def covering(wins, t0, t1):
    """Kernel files whose nominal [start, stop) period overlaps [t0, t1] (ends are day boundaries)."""
    return [w for w in wins if w[0] <= t1 and t0 < w[1] + dt.timedelta(days=1)]


def _get(url, timeout=600):
    import requests
    for attempt in range(4):
        try:
            r = requests.get(url, timeout=timeout, headers={'User-Agent': USER_AGENT})
            r.raise_for_status()
            return r.content
        except Exception:
            if attempt == 3:
                raise
            time.sleep(10 * (attempt + 1))


def fetch(relpath, pause_s=2.0):
    """Download one kernel (resumable by file: a complete file is never fetched again). Returns the local path."""
    SPICE_DIR.mkdir(parents=True, exist_ok=True)
    local = SPICE_DIR / Path(relpath).name
    if local.exists() and local.stat().st_size > 0:
        return local
    import requests
    url = f'{BASE}/{relpath}'
    part = local.with_suffix(local.suffix + '.partial')
    for attempt in range(5):
        try:
            have = part.stat().st_size if part.exists() else 0
            hdr = {'User-Agent': USER_AGENT}
            if have:
                hdr['Range'] = f'bytes={have}-'
            with requests.get(url, headers=hdr, stream=True, timeout=600) as r:
                if r.status_code == 416:
                    break
                r.raise_for_status()
                mode = 'ab' if (have and r.status_code == 206) else 'wb'
                with open(part, mode) as f:
                    for chunk in r.iter_content(1 << 20):
                        f.write(chunk)
            break
        except Exception:
            if attempt == 4:
                raise
            time.sleep(15 * (attempt + 1))
    part.rename(local)
    rec = {'url': url, 'file': local.name, 'bytes': local.stat().st_size, 'sha256': sha256_file(local),
           'retrieved_utc': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'source': 'NAIF PDS lro-l-spice-6-v1.0'}
    with open(SPICE_DIR / 'MANIFEST.jsonl', 'a') as f:
        f.write(json.dumps(rec) + '\n')
    time.sleep(pause_s)
    return local


def manifest():
    p = SPICE_DIR / 'MANIFEST.jsonl'
    if not p.exists():
        return {}
    return {json.loads(l)['file']: json.loads(l) for l in p.read_text().splitlines() if l.strip()}


def kernels_for(t0, t1, fetch_missing=True):
    """Kernel set for an observation interval [t0, t1] (datetimes, UTC). Returns (paths, record)."""
    ck = listing('ck')
    spk = listing('spk')
    sc = covering(windows('lrosc', ck), t0, t1)
    lc = covering(windows('lrolc', ck), t0, t1)
    rg = covering(windows('lrorg', spk), t0, t1)
    rel = list(STATIC) + [f'ck/{w[2]}' for w in sc + lc] + [f'spk/{w[2]}' for w in rg]
    if not (sc and lc and rg):
        return None, {'error': f'no coverage: lrosc {len(sc)}, lrolc {len(lc)}, lrorg {len(rg)}', 'kernels': rel}
    paths = [fetch(r) if fetch_missing else SPICE_DIR / Path(r).name for r in rel]
    return paths, {'kernels': [Path(r).name for r in rel], 'archive': BASE}


def main():
    """Fetch the kernels for every image in results/selection.json (sequential, resumable)."""
    from .common import RESULTS
    from .select import _t
    sel = json.loads((RESULTS / 'selection.json').read_text())
    need = set()
    for im in sel['images']:
        _paths, rec = kernels_for(_t(im['utc_start']), _t(im['utc_stop']), fetch_missing=False)
        need.update(rec['kernels'])
    rel = [r for r in STATIC] + sorted(f'ck/{n}' if n.endswith('.bc') else f'spk/{n}' for n in need
                                       if not any(n == Path(s).name for s in STATIC))
    for i, r in enumerate(rel):
        p = fetch(r)
        print(f'{i + 1}/{len(rel)} {p.name} {p.stat().st_size / 1e6:.1f} MB', flush=True)


if __name__ == '__main__':
    main()


# ------------------------------------------------------------------------------------------------ A4: LOLA/LRO RS orbits
GRGM_BASE = 'https://pds-geosciences.wustl.edu/lro/lro-l-rss-1-tracking-v1/lrors_0001/data/spk'
GRGM_RE = re.compile(r'(lro_(?:co|no_\d+|sm_\d+|es_\d+)_grgm900c_l600)\.bsp')


def grgm_periods(get=None):
    """[(start, stop, name)] of the GRGM900C science orbit SPKs, from their PDS3 labels (cached under spice/grgm_labels)."""
    d = SPICE_DIR / 'grgm_labels'
    d.mkdir(parents=True, exist_ok=True)
    lst = d / 'listing.html'
    get = get or _get
    if not lst.exists():
        lst.write_bytes(get(f'{GRGM_BASE}/'))
    names = sorted(set(GRGM_RE.findall(lst.read_text(errors='replace'))))
    out = []
    for n in names:
        p = d / f'{n}.lbl'
        if not p.exists():
            p.write_bytes(get(f'{GRGM_BASE}/{n}.lbl'))
            time.sleep(0.3)
        t = p.read_text(errors='replace')
        a = re.search(r'START_TIME\s*=\s*(\S+)', t)
        b = re.search(r'STOP_TIME\s*=\s*(\S+)', t)
        if a and b:
            out.append((dt.datetime.fromisoformat(a.group(1).rstrip('Z')), dt.datetime.fromisoformat(b.group(1).rstrip('Z')), n))
    return sorted(out)


def grgm_for(t0, t1, fetch_missing=True):
    """Local path of the GRGM900C SPK covering [t0, t1] entirely, or None (then the FDF lrorg orbit is used)."""
    for a, b, n in grgm_periods():
        if a <= t0 and t1 <= b:
            local = SPICE_DIR / f'{n}.bsp'
            if fetch_missing and not (local.exists() and local.stat().st_size > 0):
                import requests
                part = local.with_suffix('.bsp.partial')
                with requests.get(f'{GRGM_BASE}/{n}.bsp', headers={'User-Agent': USER_AGENT}, stream=True, timeout=600) as r:
                    r.raise_for_status()
                    with open(part, 'wb') as f:
                        for c in r.iter_content(1 << 20):
                            f.write(c)
                part.rename(local)
                rec = {'url': f'{GRGM_BASE}/{n}.bsp', 'file': local.name, 'bytes': local.stat().st_size, 'sha256': sha256_file(local),
                       'retrieved_utc': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                       'source': 'PDS Geosciences lro-l-rss-1-tracking-v1 (LOLA/LRO RS GRGM900C orbit)'}
                with open(SPICE_DIR / 'MANIFEST.jsonl', 'a') as f:
                    f.write(json.dumps(rec) + '\n')
            return local
    return None
