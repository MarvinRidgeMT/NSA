#!/usr/bin/env python3
"""Build the viewer's Certainty Height sidecar from the committed batch sweep CSVs. Standard library only.

Input  : data/batch/2026-11-14/certainty_height*/clone_sweep_summary.csv (+ manifest.json), from the a-science branch
         (third-computer polaris_batch run, commit 971df9a). Nothing is re-run; no terrain or ephemeris is touched.
         15 Nov: --batch-dir data/batch/2026-11-15_float64_rerun reads the float64 re-run of the same sweep (see its manifest).
Output : web/public/certainty/sidecar.json (format polaris-certainty-sidecar-v1).

What this tool does with the numbers:
  * copies each CSV row into the A2 `certainty_curve` row shape (nominal/min/p10/median/p90/max, n_clones, pass "k/N");
  * per requirement, reports the smallest SAMPLED mast whose pass string says every tested map passes (k == N);
  * reports the smallest SAMPLED mast whose Sun-centre spread (max - min, both copied) is <= AGREEMENT_TOLERANCE_P;
  * reports the smallest SAMPLED mast at which Sun-centre min == 100 (the batch README's own "Certainty Height").
These are look-ups and one subtraction over values the solver wrote. The viewer computes none of it.
The thresholds in the CSV columns (Sun >= 70 %, Sun+Earth >= 40 %) are the team's requirements, not NASA mission requirements.
Status of every number: SOURCE-BASED UNVALIDATED. Clone spread is not a probability.
"""
import argparse, csv, hashlib, json, re
from pathlib import Path

AGREEMENT_TOLERANCE_P = 1.0  # percentage points of Sun-centre visibility, declared here
METRICS = {"sun_centre_pct": ("Sun centre visible", 70.0), "both_centre_pct": ("Sun and Earth together", 40.0)}
DEFAULT_WHAT = "polaris_batch clone sweep (third-computer variant; code in data/batch/2026-11-14/code), nominal + 20 PGDA 78 clones, 1 m near ray step, window 2026-11-14 00:00 to 2026-11-28 00:00 UTC at 1 h (337 samples)"
DEFAULT_SOLVER_NOTE = "A separate solver from the repo bundles shown in the viewer (science/); at Site04 ROI3, 1 m mast, the two differ by 2 knife-edge hourly samples (A_SCIENCE_STATUS 13:06). a-science recommends the batch as the source of record for clone ranges and Certainty Height."


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch-dir", default="data/batch/2026-11-14")
    ap.add_argument("--out", default="web/public/certainty/sidecar.json")
    ap.add_argument("--commit", default="971df9a", help="a-science commit the CSVs were read from")
    ap.add_argument("--repo-branch", default="a-science", help="branch the CSVs were read from")
    ap.add_argument("--what", default=DEFAULT_WHAT, help="source.what text (describes the run that wrote the CSVs)")
    ap.add_argument("--solver-note", default=DEFAULT_SOLVER_NOTE, help="source.solver_note text (shown in the viewer)")
    a = ap.parse_args()
    batch = Path(a.batch_dir)
    files, rows_by_site, manifests = [], {}, []
    for d in sorted(batch.glob("certainty_height*")):
        f = d / "clone_sweep_summary.csv"
        if not f.exists():
            continue
        files.append({"path": f.as_posix(), "sha256": sha256(f)})
        m = d / "manifest.json"
        if m.exists():
            mj = json.loads(m.read_text())
            manifests.append({"path": m.as_posix(), "sha256": sha256(m), "created_utc": mj.get("created_utc"), "command": mj.get("command"), "label": mj.get("label"), "note": mj.get("note")})
        with f.open(newline="") as fh:
            for r in csv.DictReader(fh):
                key = f"{r['site'].lower()}_roi{r['roi']}"
                thresholds = {}
                for col in r:
                    mt = re.fullmatch(r"pass_(\w+)>=([\d.]+)", col)
                    if mt:
                        thresholds[mt.group(1)] = (float(mt.group(2)), r[col])
                for metric, (thr, passed) in thresholds.items():
                    if metric not in METRICS or METRICS[metric][1] != thr:
                        raise SystemExit(f"unexpected threshold column pass_{metric}>={thr} in {f}")
                    rows_by_site.setdefault(key, []).append({
                        "mast_m": float(r["mast_m"]), "metric": metric,
                        **{k: float(r[f"{metric}_{k}"]) for k in ("nominal", "min", "p10", "median", "p90", "max")},
                        "n_clones": int(r["n_clones"]), "pass": passed, "source_csv": f.as_posix(),
                    })
    if not rows_by_site:
        raise SystemExit(f"no certainty_height*/clone_sweep_summary.csv under {batch}")
    sites = {}
    for key, rows in sorted(rows_by_site.items()):
        rows.sort(key=lambda x: (x["mast_m"], x["metric"]))
        masts = sorted({x["mast_m"] for x in rows})
        def first(pred):
            return next((m for m in masts if pred(m)), None)
        def row(m, metric):
            return next(x for x in rows if x["mast_m"] == m and x["metric"] == metric)
        def all_pass(m, metric):
            k, n = row(m, metric)["pass"].split("/")
            return k == n
        sites[key] = {
            "sampled_masts_m": masts,
            "certainty_curve": rows,
            "certainty_height_m": {metric: first(lambda m, metric=metric: all_pass(m, metric)) for metric in METRICS},
            "agreement_mast_m": first(lambda m: row(m, "sun_centre_pct")["max"] - row(m, "sun_centre_pct")["min"] <= AGREEMENT_TOLERANCE_P),
            "all_maps_100pct_sun_mast_m": first(lambda m: row(m, "sun_centre_pct")["min"] >= 100.0),
        }
    out = {
        "format": "polaris-certainty-sidecar-v1",
        "status": "SOURCE_BASED_UNVALIDATED",
        "generated_by": "tools/certainty/build_certainty_sidecar.py",
        "source": {
            "what": a.what,
            "repo_branch": a.repo_branch, "repo_commit": a.commit, "files": files, "manifests": manifests,
            "solver_note": a.solver_note,
        },
        "requirements": [{"metric": k, "label": v[0], "op": ">=", "threshold": v[1], "unit": "%", "source": "team requirement (CSV pass columns); not a NASA mission requirement"} for k, v in METRICS.items()],
        "agreement_tolerance_p": AGREEMENT_TOLERANCE_P,
        "definitions": {
            "certainty_height_m": "per requirement: smallest SAMPLED mast at which every tested map passes (pass k == N); null = none in the sweep",
            "agreement_mast_m": f"smallest SAMPLED mast at which Sun-centre max - min across tested maps <= {AGREEMENT_TOLERANCE_P} percentage points",
            "all_maps_100pct_sun_mast_m": "smallest SAMPLED mast at which the Sun centre is visible 100 % of the window on every tested map (the batch README's 'Certainty Height')",
        },
        "sites": sites,
    }
    outp = Path(a.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    for k, s in sites.items():
        print(k, "masts", s["sampled_masts_m"], "| certainty_height_m", s["certainty_height_m"], "| agreement", s["agreement_mast_m"], "| 100% Sun on all maps", s["all_maps_100pct_sun_mast_m"])
    print("wrote", outp, sha256(outp)[:16])


if __name__ == "__main__":
    main()
