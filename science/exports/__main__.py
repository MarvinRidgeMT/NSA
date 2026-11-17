"""python -m science.exports <command>

  value <file> <json-path>                 print one number from a source file (the per-number "read" command)
  site <site_id> [--out DIR]               Decision Card PDF, GeoTIFF masks, time series, provenance (data/exports/<site>)
  bundle <results-bundle.json> [--out DIR] CSV/JSON time series + provenance of one bundle (Moon any-site, Mercury, ...)
  anysite (--lat LAT --lon LON | --site-hash H) [--out DIR]
                                           the same for a precomputed any-site point (cache lookup; never solves)
  grid [--out DIR]                         global 10 deg GeoTIFF + polar 1 deg CSV from data/anysite/precompute_summary.json
"""
from __future__ import annotations

import argparse
import json
import sys

from . import bundle_export as E, common as C


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    ap = argparse.ArgumentParser(prog='python -m science.exports', description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    v = sub.add_parser('value'); v.add_argument('file'); v.add_argument('path')
    s = sub.add_parser('site'); s.add_argument('site'); s.add_argument('--out')
    b = sub.add_parser('bundle'); b.add_argument('file'); b.add_argument('--out')
    a = sub.add_parser('anysite'); a.add_argument('--lat', type=float); a.add_argument('--lon', type=float)
    a.add_argument('--site-hash'); a.add_argument('--out')
    g = sub.add_parser('grid'); g.add_argument('--out')
    ns = ap.parse_args(argv)
    cmd = E._command(argv)
    if ns.cmd == 'value':
        print(json.dumps(C.json_get(C.read_json(ns.file), ns.path), ensure_ascii=False))
        return 0
    if ns.cmd == 'site':
        r = E.export_site(ns.site, ns.out, cmd)
    elif ns.cmd == 'bundle':
        r = E.export_bundle(ns.file, ns.out, cmd)
    elif ns.cmd == 'anysite':
        h = ns.site_hash
        if h is None:
            _, s = E.precompute_site(lat=ns.lat, lon=ns.lon)
            if s is None:
                print(f'no precomputed site at ({ns.lat}, {ns.lon}); solve it first (python -m science.anysite.solve)',
                      file=sys.stderr)
                return 2
            h = s['site_hash']
        p = E.anysite_bundle_path(h)
        if p is None:
            print(f'bundle {h} is not in data/cache/anysite/bundles (git-ignored cache)', file=sys.stderr)
            return 2
        r = E.export_bundle(p, ns.out or E.DEFAULT_OUT / 'anysite' / h, cmd)
    else:
        r = E.export_grid(ns.out, cmd)
    print(f'{C.rel(r["out_dir"])}: {len(r["prov"]["outputs"])} files, {r["prov"]["n_numbers"]} numbers -> '
          f'{C.rel(r["provenance"])}, {C.rel(r["zip"])}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
