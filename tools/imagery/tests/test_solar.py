"""Sun geometry: batching, time checks and caching with a fake Horizons transport."""
import urllib.parse

import pytest

from science import horizons as hz
from tools.imagery import solar
from tools.imagery.http_cache import PoliteCache

HDR = ('Date__(UT)__HR:MN:SC.fff, , , Azimuth_(a-app), Elevation_(a-app), Ang-diam, delta, deldot\n'
       '****\n')


def _fake(shift_s=0.0):
    calls = []

    def transport(url, timeout):
        calls.append(url)
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))
        jds = [float(x.strip("'")) for x in q['TLIST'].split()]
        lines = []
        for jd in jds:
            t = (jd - 2440587.5) * 86400.0 + shift_s
            iso = hz.unix_to_iso(t)  # 2026-11-16T07:00:00.000Z
            d, tm = iso[:-1].split('T')
            y, m, dd = d.split('-')
            mon = 'Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split()[int(m) - 1]
            lines.append(f' {y}-{mon}-{dd} {tm}, , , {(t / 1000) % 360:.6f}, 1.234500, 1900.0, 0.00257, 0.0')
        body = 'header\n' + HDR + '$$SOE\n' + '\n'.join(lines) + '\n$$EOE\n'
        return body.encode()
    return transport, calls


def test_sun_at_batches_and_caches(tmp_path):
    tr, calls = _fake()
    c = PoliteCache(tmp_path, transport=tr, sleep=lambda s: None)
    ts = [1.2e9 + 3600.0 * k for k in range(7)] + [1.2e9]  # one duplicate
    out, src = solar.sun_at(-89.5, 220.0, ts, cache=c, batch=3)
    assert len(calls) == 3 and len(out) == 7 and len(src) == 3
    assert all(v[1] == pytest.approx(1.2345) for v in out.values())
    q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(calls[0]).query))
    assert q['CENTER'] == "'coord@301'" and q['COMMAND'] == "'10'" and q['APPARENT'] == 'AIRLESS'
    tr2, calls2 = _fake()
    out2, _ = solar.sun_at(-89.5, 220.0, ts, cache=PoliteCache(tmp_path, transport=tr2), batch=3)
    assert calls2 == [] and out2 == out


def test_sun_at_rejects_time_mismatch(tmp_path):
    tr, _ = _fake(shift_s=1.0)
    with pytest.raises(ValueError):
        solar.sun_at(-89.5, 220.0, [1.2e9], cache=PoliteCache(tmp_path, transport=tr, sleep=lambda s: None))
