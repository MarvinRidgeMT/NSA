"""Sun azimuth / elevation at each site centre at each image time, from JPL Horizons.

Reuses science/horizons.py (build_params, parse_text): observer coord@301 on the 1737.4 km
sphere, airless apparent az/el of the Sun centre, azimuth clockwise from local north
(0 N, 90 E). Times are sent as a TLIST of UT Julian dates in batches; every raw response is
cached with SHA-256 by tools/imagery/http_cache.PoliteCache. The returned times are checked
against the request (|dt| <= 0.01 s), as science/horizons.ephemeris_at does.

USE: stratification of the catalogue only. Not a scoring input: render twins (§6.2) recompute
the geometry at the exact exposure time from the label/SPICE.
"""
from __future__ import annotations

import datetime as dt
import math

from science import horizons as hz

from .http_cache import CACHE_ROOT, PoliteCache, canonical_url

BATCH = 150  # TLIST entries per request (~4 KB GET URL)


def parse_utc(s):
    """ODE time strings: '2009-07-04T12:39:00.489Z' or '2007-11-08T14:25:55.373' (UTC)."""
    s = s.strip().replace('Z', '')
    if '.' in s:
        head, frac = s.split('.', 1)
        frac = (frac + '000000')[:6]
        s = f'{head}.{frac}'
    return dt.datetime.fromisoformat(s).replace(tzinfo=dt.timezone.utc).timestamp()


def subsolar_lat_deg(site_lat, site_lon, az_deg, el_deg):
    """Latitude of the Sun direction in the body frame, from local az/el at a site on the sphere.
    s_z = cos(el) cos(az) cos(lat) + sin(el) sin(lat). Parallax (R/AU ~ 1e-5 rad) is ignored."""
    phi = math.radians(site_lat)
    az, el = math.radians(az_deg), math.radians(el_deg)
    sz = math.cos(el) * math.cos(az) * math.cos(phi) + math.sin(el) * math.sin(phi)
    return math.degrees(math.asin(max(-1.0, min(1.0, sz))))


def sun_at(lat, lon, unix_times, cache=None, batch=BATCH):
    """{unix_time: (az_deg, el_deg)} for the Sun centre at (lat, lon, h=0 on the sphere).
    Height is irrelevant for the Sun direction at this precision (parallax < 1e-6 deg/km)."""
    cache = cache or PoliteCache(CACHE_ROOT / 'horizons', min_interval_s=2.0)
    ts = sorted(set(unix_times))
    out, sources = {}, []
    for k in range(0, len(ts), batch):
        chunk = ts[k:k + batch]
        params = hz.build_params('10', lat, lon, 0.0, tlist=[hz.unix_to_jd(t) for t in chunk])
        url = canonical_url(hz.API, params)
        body, sha, _, _ = cache.get(url, ext='txt')
        rows = hz.parse_text(body.decode('utf-8'))
        if len(rows) != len(chunk):
            raise ValueError(f'Horizons returned {len(rows)} rows for {len(chunk)} times')
        for r, t in zip(rows, chunk):
            if abs(hz.iso_to_unix(r['utc']) - t) > 0.01:
                raise ValueError(f'Horizons time mismatch {r["utc"]} vs {t}')
            out[t] = (r['az_deg'], r['el_deg'])
        sources.append({'url_sha256_key': url, 'sha256': sha})
    return out, sources
