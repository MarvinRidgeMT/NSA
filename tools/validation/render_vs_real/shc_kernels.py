"""KPLO / ShadowCam SPICE kernels from the USGS Astrogeology public ISIS data bucket (no account; usgs_data/kplo/kernels/).

Static: kplo_shadowcam_v00.ti (IK), kplo_instrumentAddendum_v02.ti (ISIS IAK: TDI offsets, timing constants), kplo_v06.tf
(frames: KPLO_SHC_A on the spacecraft), the newest kplo_sclkscet_v*.tsc, plus the generic LSK / PCK / lunar frames / DE421
already in the NAC kernel cache. Per image: the KPLO CK (kplo_sc_YYYYMMDD_YYYYMMDD_vNN.bc) and SPK
(kplo_d_YYYYMMDD_YYYYMMDD_vNN.bsp) covering its start-stop interval (end date exclusive), choosing the shortest covering
span, then the highest version. Every download is recorded in <cache>/MANIFEST.jsonl (URL, bytes, SHA-256, retrieval UTC). Cache git-ignored.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

from .common import USER_AGENT, WORK, sha256_file

BUCKET = 'https://asc-isisdata.s3.us-west-2.amazonaws.com/'
PREFIX = 'usgs_data/kplo/kernels/'
KDIR = WORK / 'spice_kplo'
NAC_SPICE = WORK / 'spice'
STATIC_KPLO = ['ik/kplo_shadowcam_v00.ti', 'iak/kplo_instrumentAddendum_v02.ti', 'fk/kplo_v06.tf']
GENERIC = ['naif0012.tls', 'pck00010.tpc', 'moon_pa_de421_1900_2050.bpc', 'moon_080317.tf', 'moon_assoc_me.tf', 'de421.bsp']
NAME = re.compile(r'^kplo_(sc|d)_(\d{8})_(\d{8})_v(\d+)\.(bc|bsp)$')


def _get(url, timeout=600):
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    for attempt in range(5):
        try:
            return urllib.request.urlopen(req, timeout=timeout)
        except Exception:
            if attempt == 4:
                raise
            time.sleep(5 * (attempt + 1))


def listing(kind, refresh=False):
    """[(key, size)] of a kernel folder (cached in <cache>/listing_<kind>.json)."""
    KDIR.mkdir(parents=True, exist_ok=True)
    p = KDIR / f'listing_{kind}.json'
    if p.exists() and not refresh:
        return json.loads(p.read_text())
    out, token = [], None
    while True:
        q = {'list-type': '2', 'prefix': PREFIX + kind + '/', 'max-keys': '1000'}
        if token:
            q['continuation-token'] = token
        x = _get(BUCKET + '?' + urllib.parse.urlencode(q), 120).read().decode()
        for c in re.findall(r'<Contents>(.*?)</Contents>', x, re.S):
            k = re.search(r'<Key>(.*?)</Key>', c).group(1)
            if not k.endswith('.db') and not k.endswith('makedb'):
                out.append([k, int(re.search(r'<Size>(.*?)</Size>', c).group(1))])
        m = re.search(r'<NextContinuationToken>(.*?)</NextContinuationToken>', x)
        if not m:
            break
        token = m.group(1)
    p.write_text(json.dumps(out))
    return out


def fetch(key):
    local = KDIR / Path(key).name
    if local.exists() and local.stat().st_size > 0:
        return local
    KDIR.mkdir(parents=True, exist_ok=True)
    part = local.with_suffix(local.suffix + '.partial')
    with _get(BUCKET + key) as r, open(part, 'wb') as f:
        while True:
            b = r.read(1 << 20)
            if not b:
                break
            f.write(b)
    part.rename(local)
    with open(KDIR / 'MANIFEST.jsonl', 'a') as f:
        f.write(json.dumps({'file': local.name, 'url': BUCKET + key, 'bytes': local.stat().st_size, 'sha256': sha256_file(local),
                            'retrieved_utc': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                            'source': 'USGS Astrogeology ISIS data (public S3), usgs_data/kplo'}) + '\n')
    return local


def _covering(kind, t0, t1):
    best = None
    for key, size in listing(kind):
        m = NAME.match(Path(key).name)
        if not m:
            continue
        a = dt.datetime.strptime(m.group(2), '%Y%m%d')
        b = dt.datetime.strptime(m.group(3), '%Y%m%d')       # end date exclusive (checked with spkcov/ckcov: coverage ends 00:00)
        if a <= t0 and t1 <= b:
            rank = ((b - a).days, -int(m.group(4)))
            if best is None or rank < best[0]:
                best = (rank, key, size)
    return best


def newest_sclk():
    keys = [k for k, _ in listing('sclk') if k.endswith('.tsc')]
    return max(keys, key=lambda k: int(re.search(r'_v(\d+)\.tsc$', k).group(1)))


def kernels_for(t0, t1, fetch_missing=True):
    """Kernel paths for [t0, t1] (naive UTC datetimes) or (None, record) when a CK or SPK does not cover it."""
    ck = _covering('ck', t0, t1)
    spk = _covering('spk', t0, t1)
    rec = {'ck': ck[1] if ck else None, 'spk': spk[1] if spk else None, 'sclk': newest_sclk()}
    if not (ck and spk):
        return None, {**rec, 'error': f"no KPLO {'CK' if not ck else 'SPK'} covers {t0:%Y-%m-%dT%H:%M:%S}-{t1:%H:%M:%S}"}
    keys = [PREFIX + s for s in STATIC_KPLO] + [rec['sclk'], ck[1], spk[1]]
    if not fetch_missing:
        return [KDIR / Path(k).name for k in keys], rec
    paths = [NAC_SPICE / g for g in GENERIC] + [fetch(k) for k in keys]
    return paths, {**rec, 'kernels': [p.name for p in paths], 'bytes': ck[2] + spk[2]}
