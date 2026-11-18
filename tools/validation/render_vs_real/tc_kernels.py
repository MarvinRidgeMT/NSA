"""SELENE (Kaguya) / TC SPICE kernels from the USGS Astrogeology public ISIS data bucket (no account; usgs_data/kaguya/kernels/).

Static: SEL_TC_V01.TI (JAXA IK: focal lengths, boresights, distortion), kaguyaTcAddendum007.ti (ISIS IAK: boresight
sample/line, focal-plane transforms), SEL_V01.TF (frames: LISM_TC1_HEAD / LISM_TC2_HEAD), SEL_M_V01.TSC (SCLK), plus the
generic LSK / PCK / lunar frames / DE421 already in the NAC kernel cache.
Attitude: SEL_M_ALL_D_V02.BC (the whole-mission definitive CK; the labels' metakernels name "LongCK_D_V02").
Orbit (A11.3): ORBITS maps a name to its SPK. 'label' resolves the RISE solution named in the label's SPICE metakernel
(protocol §3.1: "the NAIF SPICE kernels named in the label"); 'grgm900c' is the later GRGM900C + altimetry solution, the
alternative the pipeline test (A11.4) compares.
Every download is recorded in <cache>/MANIFEST.jsonl (URL, bytes, SHA-256, retrieval UTC). Cache git-ignored.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import time
import urllib.request
from pathlib import Path

from .common import USER_AGENT, WORK, sha256_file

BUCKET = 'https://asc-isisdata.s3.us-west-2.amazonaws.com/'
PREFIX = 'usgs_data/kaguya/kernels/'
KDIR = WORK / 'spice_selene'
NAC_SPICE = WORK / 'spice'
STATIC = ['ik/SEL_TC_V01.TI', 'iak/kaguyaTcAddendum007.ti', 'fk/SEL_V01.TF', 'sclk/SEL_M_V01.TSC']
GENERIC = ['naif0012.tls', 'pck00010.tpc', 'moon_pa_de421_1900_2050.bpc', 'moon_080317.tf', 'moon_assoc_me.tf', 'de421.bsp']
CK = 'ck/SEL_M_ALL_D_V02.BC'
# RISE orbit solutions as named in the TC labels' SPICE_METAKERNEL_FILE_NAME, and their SPK in the bucket.
RISE_SPK = {'RISE100i_05': 'spk/SEL_M_071020_081226_SGMI_05.BSP', 'RISE100h_02': 'spk/SEL_M_071020_090610_SGMH_02.BSP'}
GRGM900C_SPK = 'spk/SELMAINGRGM900CL660DIRALT2008103020090610.bsp'     # GRGM900C to degree 660 + altimetry
ORBITS = ('label', 'grgm900c')


def _size(url):
    req = urllib.request.Request(url, method='HEAD', headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as r:
        return int(r.headers['Content-Length'])


def fetch(key, timeout=120):
    """Download once, resuming an interrupted transfer with HTTP Range requests (one process at a time per file)."""
    local = KDIR / Path(key).name
    if local.exists() and local.stat().st_size > 0:
        return local
    KDIR.mkdir(parents=True, exist_ok=True)
    part = local.with_suffix(local.suffix + '.partial')
    url = BUCKET + key
    total = _size(url)
    for attempt in range(30):
        have = part.stat().st_size if part.exists() else 0
        if have >= total:
            break
        req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT, 'Range': f'bytes={have}-'})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r, open(part, 'ab') as f:
                if have and r.status != 206:
                    raise RuntimeError(f'{key}: server ignored the Range request (HTTP {r.status})')
                while True:
                    b = r.read(1 << 22)
                    if not b:
                        break
                    f.write(b)
        except (OSError, TimeoutError) as e:          # stalled or dropped: resume from what is on disk
            print(f'{Path(key).name}: resume after {type(e).__name__} at {part.stat().st_size} / {total} bytes', flush=True)
            time.sleep(min(60, 5 * (attempt + 1)))
    if part.stat().st_size != total:
        raise RuntimeError(f'{key}: {part.stat().st_size} of {total} bytes after retries')
    part.rename(local)
    with open(KDIR / 'MANIFEST.jsonl', 'a') as f:
        f.write(json.dumps({'file': local.name, 'url': BUCKET + key, 'bytes': local.stat().st_size, 'sha256': sha256_file(local),
                            'retrieved_utc': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                            'source': 'USGS Astrogeology ISIS data (public S3), usgs_data/kaguya'}) + '\n')
    return local


def rise_solution(metakernel_name):
    """'RISE100i_05' etc. from a label's SPICE_METAKERNEL_FILE_NAME, or None."""
    m = re.search(r'(RISE\d+[a-z]_\d+)', metakernel_name or '')
    return m.group(1) if m else None


def spk_key(lab, orbit):
    if orbit == 'grgm900c':
        return GRGM900C_SPK, 'GRGM900C L660 + altimetry'
    if orbit != 'label':
        raise ValueError(orbit)
    sol = rise_solution(lab.get('spice_metakernel'))
    if sol not in RISE_SPK:
        return None, f"label metakernel names no known RISE orbit ({lab.get('spice_metakernel')!r})"
    return RISE_SPK[sol], sol


def kernels_for(lab, orbit='label', fetch_missing=True):
    """Kernel paths for one TC label and orbit choice, or (None, record) when the label's orbit is unknown.
    Coverage of the image interval is checked by the camera model (spkcov/ckcov), not here."""
    key, name = spk_key(lab, orbit)
    rec = {'orbit': orbit, 'spk': key, 'orbitSolution': name, 'ck': CK}
    if key is None:
        return None, {**rec, 'error': name}
    keys = [PREFIX + s for s in STATIC] + [PREFIX + CK, PREFIX + key]
    if not fetch_missing:
        return [KDIR / Path(k).name for k in keys], rec
    paths = [NAC_SPICE / g for g in GENERIC] + [fetch(k) for k in keys]
    return paths, {**rec, 'kernels': [p.name for p in paths]}
