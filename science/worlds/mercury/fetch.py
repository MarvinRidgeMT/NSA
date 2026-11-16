"""Download the Mercury catalogue with the S2 fetcher (sequential, rate-limited, resumable, SHA-256, manifest lines).

  python -m science.worlds.mercury.fetch --check           # HEAD every file, compare sizes
  python -m science.worlds.mercury.fetch                   # download the plan (cap 30 GB new)
  python -m science.worlds.mercury.fetch --products mercury_mla_gdr_v2,mercury_pgda85_prokofiev

Manifest: $POLARIS_DATA/v2/manifest.jsonl (shared with S2; one appended line per file, same keys).
"""
from __future__ import annotations

import argparse
import sys

from tools.globe import fetch as F

from . import products as catalogue


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=None)
    ap.add_argument("--products", default=None)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--max-new-gb", type=float, default=30.0)
    ap.add_argument("--min-free-gb", type=float, default=200.0)
    ap.add_argument("--max-mbps", type=float, default=16.0)
    ap.add_argument("--min-interval", type=float, default=1.0)
    a = ap.parse_args(argv)
    root = F.polaris_data(a.root)
    plan = [catalogue.get(w) for w in a.products.split(",")] if a.products else catalogue.download_plan()
    policy = F.Policy(min_interval_s=a.min_interval, max_bytes_per_s=(a.max_mbps * 1024 * 1024) or None)
    if a.check:
        return 1 if F.check(plan, policy) else 0
    budget = {"new_bytes": 0, "max_new_bytes": int(a.max_new_gb * F.GB), "min_free_bytes": int(a.min_free_gb * F.GB)}
    throttle = F.Throttle(policy)
    print(f"{F.utc_now()} root={root} free={F.free_bytes(root) / F.GB:.1f} GB plan={[p.product_id for p in plan]}", flush=True)
    try:
        for p in plan:
            F.fetch_product(p, root, policy, throttle, budget, log=lambda s: print(s, flush=True))
            print(f"{F.utc_now()} product done: {p.product_id}; run total {budget['new_bytes'] / F.GB:.2f} GB", flush=True)
    except F.BudgetStop as e:
        print(f"{F.utc_now()} {e}")
    for f in budget.get("failures", []):
        print(f"{F.utc_now()} FAILED {f['url']}: {f['error']}")
    print(f"{F.utc_now()} done; run total {budget['new_bytes'] / F.GB:.2f} GB; free {F.free_bytes(root) / F.GB:.1f} GB")
    return 1 if budget.get("failures") else 0


if __name__ == "__main__":
    sys.exit(main())
