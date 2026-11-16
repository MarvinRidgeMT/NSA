"""L8 (part) — toterr-vs-clone calibration factor per site, from the existing research results.

The PGDA 78 'toterr' layer (per-pixel total height error) was used, with a Gaussian model and
either independent (rho = 0) or empirically correlated errors, to predict how many clone-hours flip
state (research/long_features/code/step3_rq2.py, model B). The 20 clones give the observed count.
Calibration factor = observed / expected flip clone-hours (1 = calibrated, < 1 = toterr over-predicts).
Also the per-pixel sigma ratio clone_std / toterr (median over the controlling cells).
"""
from __future__ import annotations

import json

from .common import ROOT, write_result

SRC = ROOT / 'research' / 'long_features' / 'results' / 'rq2_report.json'


def compute(src=SRC):
    r = json.loads(src.read_text())
    out = {}
    for key, v in r.items():
        if '/' not in key:
            continue
        site, win = key.split('/')
        obs = v['B_toterr_rho_emp']['observed_flip_clone_hours']
        row = {'observed_flip_clone_hours': obs}
        for model in ('B_toterr_rho0', 'B_toterr_rho_emp'):
            exp = v[model]['expected_flip_clone_hours']
            row[model] = {'expected_flip_clone_hours': exp,
                          'calibration_factor_obs_over_exp': None if exp < 1 else round(obs / exp, 3),
                          'over_prediction_exp_over_obs': None if obs == 0 else round(exp / obs, 3)}
        e = v['B_toterr_rho_emp']['expected_flip_clone_hours']
        row['note'] = ('no flips in either' if obs == 0 and e < 1 else
                       f'toterr predicts ~0 flips, clones show {obs}' if e < 1 else
                       'too few flips to calibrate' if obs < 30 else '')
        out.setdefault(site, {})[win] = row
    for site in out:
        sc = r.get(site, {}).get('sigma_check')
        if sc:
            out[site]['sigma_ratio_clone_std_over_toterr_median'] = round(sc['ratio_median'], 3)
    return out


README = """# L8 (part 2) — toterr vs clone calibration factor

**Label:** PILOT · SOURCE-BASED · UNVALIDATED.

**Question.** The PGDA 78 `toterr` layer, used as a Gaussian height-error model, was reported to over-predict state flips
by ≈ ×1.5 relative to the 20 clones. Is that one factor, or does it vary by site?

**Method.** `python -m science.limits.l8_calibration`: arithmetic on `research/long_features/results/rq2_report.json`
(model B, independent ρ = 0 and empirically correlated ρ). Factor = observed / expected flip clone-hours; also the
median per-pixel σ ratio clone-std / toterr at the controlling cells.

**Result.** See `RESULT.md`. 12-month window: toterr **over**-predicts at Site04 RoI 3 (×1.41) and Site01 RoI 6 (×1.69),
but **under**-predicts at Site07 RoI 1 (×0.55) and Site11 RoI 4 (×0.70), although the per-pixel σ ratio is similar
(0.63–0.77) everywhere. So no single factor applies; a per-site factor is needed, and at Sites 07/11 the flips come
from something the per-pixel σ does not capture (likely correlated, multi-cell ridge changes — the same sites where the
16-ridge forecast captures only ~37–44 %).

**What it does not show.** The clones are themselves 20 draws of one error model (Barker et al. 2021), so this is
"toterr vs that model", not vs truth. The demo-window rows have too few flips to calibrate. Not a probability.
"""


def table_md(res):
    L = ['| site | window | observed flip clone-h | expected (ρ=0) | expected (ρ emp.) | obs/exp (ρ emp.) | exp/obs (ρ emp.) | σ ratio clone/toterr |',
         '|---|---|---|---|---|---|---|---|']
    for site, w in res['sites'].items():
        for win in ('nov14d', 'year'):
            if win not in w:
                continue
            x = w[win]
            L.append(f"| {site} | {win} | {x['observed_flip_clone_hours']} | {x['B_toterr_rho0']['expected_flip_clone_hours']} | "
                     f"{x['B_toterr_rho_emp']['expected_flip_clone_hours']} | {x['B_toterr_rho_emp']['calibration_factor_obs_over_exp']} | "
                     f"{x['B_toterr_rho_emp']['over_prediction_exp_over_obs']} | {w.get('sigma_ratio_clone_std_over_toterr_median')} | {x['note']} |")
    L[0] += ' note |'; L[1] += '---|'
    return '# L8 calibration table\n\nPILOT · SOURCE-BASED · UNVALIDATED.\n\n' + '\n'.join(L) + '\n'


def main():
    res = {'item': 'L8_calibration', 'sites': compute()}
    write_result('L8_calibration', res, [SRC], README, {'RESULT.md': table_md(res)})
    print(table_md(res))


if __name__ == '__main__':
    main()
