"""Mars surface solar energy, direct beam only — ENGINEERING ASSUMPTION, tau an explicit input.

    S(r)      = S0 / r_AU^2,  S0 = 1361 W/m^2 (total solar irradiance at 1 AU; Kopp & Lean 2011, GRL 38, L01706)
    mu        = sin(e_sun)  (Sun-centre elevation above the sphere-normal horizon plane; Horizons, airless)
    G_dir,h   = S(r) mu exp(-tau / mu)  if the Sun centre is above the terrain skyline and mu >= MU_MIN, else 0
Beer-Lambert extinction with a plane-parallel air mass 1/mu (cut at mu < MU_MIN = 0.05, e < 2.9 deg, where 1/mu
diverges and the plane-parallel air mass is wrong). The DIFFUSE sky term is OMITTED: on Mars it is a large share of the
total at tau >~ 1 (Appelbaum & Flood 1990, Solar Energy 45, 353), so these numbers are the direct component only, a lower
bound on insolation, not a power prediction. No Mars sky-brightness MODEL is shipped. Daily energy = trapezoid of hourly
samples. Panel orientation, dust deposition on panels, temperature and conversion efficiency are not modelled.
"""
from __future__ import annotations

import numpy as np

S0_W_M2 = 1361.0
MU_MIN = 0.05
LABEL = 'ENGINEERING ASSUMPTION (direct beam, Beer-Lambert, tau input; diffuse omitted)'
TAUS = (0.3, 0.5, 1.0, 2.0, 5.0)


def direct_horizontal(el_deg, r_au, visible, tau):
    mu = np.sin(np.radians(np.asarray(el_deg, float)))
    ok = np.asarray(visible, bool) & (mu >= MU_MIN)
    S = S0_W_M2 / np.asarray(r_au, float) ** 2
    return np.where(ok, S * mu * np.exp(-tau / np.where(ok, mu, 1.0)), 0.0)


def top_of_atmosphere_horizontal(el_deg, r_au):
    mu = np.sin(np.radians(np.asarray(el_deg, float)))
    return np.where(mu > 0, S0_W_M2 / np.asarray(r_au, float) ** 2 * mu, 0.0)


def mean_daily_wh_m2(t_unix, g_w_m2, sol_s=88_775.244):
    """Mean energy per sol (Wh/m^2) = time-integral (trapezoid) / span x sol length."""
    t = np.asarray(t_unix, float)
    return float(np.trapezoid(g_w_m2, t) / (t[-1] - t[0]) * sol_s / 3600.0)
