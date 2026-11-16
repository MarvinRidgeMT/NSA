"""Phase 5 energy margin model — ENGINEERING ASSUMPTION (not a lander power specification).

Power (W) at each hourly ephemeris sample:
    P(t) = S(t) · A · η · f_disc(t) · cos(incidence)
    S(t) = 1361 W/m² × (1 au / r(t))²         r = JPL Horizons Sun range (cached year ephemeris)
    f_disc = visible Sun disc fraction at the ARRAY TOP (D_mast), from the hourly disc-fraction cube
array types
    vsat           vertical single-axis Sun-tracking array (VSAT-style): normal follows the Sun azimuth,
                   incidence = Sun elevation  ->  cos(inc) = cos(el)
    fixed_vertical vertical array whose normal points at azimuth a (0° N, 90° E, local ENU):
                   cos(inc) = cos(el) · max(0, cos(az_sun − a))
Only the array top height enters P. An antenna height is a separate layout field that the power model never reads.

Energy per hourly interval [t_k, t_k+1]: trapezoid of P (Wh). Load per interval: constant + scheduled load
evaluated at the interval start (Wh). Battery step, per interval:
    net = gen − load
    net ≥ 0: soc += η_c · net, capped at capacity (excess is 'spilled')
    net < 0: soc −= |net| / η_d, floored at 0 (shortfall is 'unserved')
Feasible capacity C: soc ≥ reserve·C before flooring at every step, starting from initial·C. Feasibility is
monotone in C (for C' > C, induction keeps soc' − soc ≥ reserve·(C' − C): discharges subtract the same amount, and a
capped charge gives soc' = C' with soc ≤ C, so the gap is ≥ C' − C), so the needed capacity is found by bisection
on [0, E_load / (η_d (initial − reserve))], the upper bound being feasible even with zero generation.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

SOLAR_CONSTANT_W_M2 = 1361.0
ARRAY_TYPES = ('vsat', 'fixed_vertical')
DEFAULT_YAML = Path(__file__).with_name('assumptions.yaml')
LABEL = 'ENGINEERING ASSUMPTION'


# ---------------------------------------------------------------- config (YAML)

def _scalar(s):
    s = s.strip()
    if s in ('null', '~', ''):
        return None
    if s in ('true', 'false'):
        return s == 'true'
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        return s.strip('"\'')


def parse_simple_yaml(text):
    """Strict parser for the block-style subset used by assumptions.yaml (nested maps, lists of maps, scalars,
    # comments). PyYAML is not in the project venv; anything outside this subset raises ValueError."""
    lines = []
    for raw in text.splitlines():
        body = raw.split('#', 1)[0].rstrip()
        if body.strip():
            if '\t' in body[: len(body) - len(body.lstrip())]:
                raise ValueError('tabs not allowed')
            lines.append((len(body) - len(body.lstrip()), body.strip()))

    def block(lines, i, ind):
        if lines[i][1].startswith('- '):
            out = []
            while i < len(lines) and lines[i][0] == ind and lines[i][1].startswith('- '):
                sub = [(ind + 2, lines[i][1][2:])]
                j = i + 1
                while j < len(lines) and lines[j][0] > ind:
                    sub.append(lines[j]); j += 1
                item, _ = block(sub, 0, ind + 2)
                out.append(item); i = j
            return out, i
        out = {}
        while i < len(lines) and lines[i][0] == ind:
            key, sep, rest = lines[i][1].partition(':')
            if not sep or not key or key.startswith('- '):
                raise ValueError(f'unsupported YAML line: {lines[i][1]!r}')
            if rest.strip():
                out[key.strip()] = _scalar(rest); i += 1
            elif i + 1 < len(lines) and lines[i + 1][0] > ind:
                out[key.strip()], i = block(lines, i + 1, lines[i + 1][0])
            else:
                out[key.strip()] = None; i += 1
        if i < len(lines) and lines[i][0] > ind:
            raise ValueError(f'bad indentation at {lines[i][1]!r}')
        return out, i

    if not lines:
        return {}
    data, i = block(lines, 0, lines[0][0])
    if i != len(lines):
        raise ValueError(f'unparsed YAML from {lines[i][1]!r}')
    return data


@dataclass(frozen=True)
class Battery:
    capacity_wh: float
    charge_efficiency: float
    discharge_efficiency: float
    min_reserve_fraction: float
    initial_soc_fraction: float

    def __post_init__(self):
        if not (0 < self.charge_efficiency <= 1 and 0 < self.discharge_efficiency <= 1):
            raise ValueError('efficiencies must be in (0, 1]')
        if not (0 <= self.min_reserve_fraction < self.initial_soc_fraction <= 1):
            raise ValueError('need 0 <= reserve < initial <= 1')


@dataclass(frozen=True)
class Config:
    area_m2: float
    efficiency: float
    fixed_azimuth_deg: object          # float or 'auto'
    battery: Battery
    constant_w: float
    scheduled: tuple                   # of dicts: name, power_w, start_utc_hour, duration_h, every_h
    source: str = 'science/energy/assumptions.yaml'


def load_config(path=DEFAULT_YAML):
    p = Path(path)
    try:
        import yaml  # type: ignore
        d = yaml.safe_load(p.read_text())
    except ImportError:
        d = parse_simple_yaml(p.read_text())
    a, b, l = d['array'], d['battery'], d['load']
    az = a.get('fixed_azimuth_deg', 'auto')
    try:
        src = str(p.resolve().relative_to(Path(__file__).resolve().parents[2]))
    except ValueError:
        src = str(p)
    return Config(area_m2=float(a['area_m2']), efficiency=float(a['efficiency']),
                  fixed_azimuth_deg=az if az == 'auto' else float(az),
                  battery=Battery(**{k: float(v) for k, v in b.items()}),
                  constant_w=float(l['constant_w']), scheduled=tuple(l.get('scheduled') or ()), source=src)


# ---------------------------------------------------------------- power

def irradiance(range_au):
    return SOLAR_CONSTANT_W_M2 / np.asarray(range_au, float) ** 2


def cos_incidence(sun_el_deg, sun_az_deg, array_type, azimuth_deg=None):
    el = np.radians(np.asarray(sun_el_deg, float))
    if array_type == 'vsat':
        return np.cos(el)
    if array_type == 'fixed_vertical':
        d = np.radians(np.asarray(sun_az_deg, float) - float(azimuth_deg))
        return np.cos(el) * np.maximum(0.0, np.cos(d))
    raise ValueError(array_type)


def power_w(range_au, sun_el_deg, sun_az_deg, f_disc, area_m2, efficiency, array_type, azimuth_deg=None):
    """P = S·A·η·f_disc·cos(inc). f_disc broadcasts against the time axis (last axis)."""
    return (irradiance(range_au) * area_m2 * efficiency * cos_incidence(sun_el_deg, sun_az_deg, array_type, azimuth_deg)
            * np.asarray(f_disc, float))


@dataclass(frozen=True)
class Layout:
    """Asset heights above ground. Power reads array_top_m only; antenna_top_m exists for link work."""
    array_top_m: float
    antenna_top_m: float = 1.0


def layout_power(eph, disc_by_mast, masts, layout, cfg, array_type, azimuth_deg=None):
    """Hourly power for one terrain map. disc_by_mast: (n_mast, H) visible Sun fraction; masts: their heights."""
    j = int(np.flatnonzero(np.isclose(np.asarray(masts, float), layout.array_top_m))[0])
    return power_w(eph['sun_range_au'], eph['sun_el'], eph['sun_az'], disc_by_mast[j], cfg.area_m2, cfg.efficiency,
                   array_type, azimuth_deg)


def interval_energy_wh(p_w, dt_h=1.0):
    p = np.asarray(p_w, float)
    return 0.5 * (p[..., :-1] + p[..., 1:]) * dt_h


def load_w(t_unix, cfg):
    t = np.asarray(t_unix, float)
    hour = t / 3600.0
    out = np.full(t.shape, cfg.constant_w, float)
    for s in cfg.scheduled:
        ph = np.mod(hour - float(s['start_utc_hour']), float(s['every_h']))
        out += np.where(ph < float(s['duration_h']) - 1e-9, float(s['power_w']), 0.0)
    return out


def best_fixed_azimuth(range_au, sun_el, sun_az, f_disc, step_deg=1.0):
    """Azimuth (deg) of the fixed vertical array maximising mean power for the given series."""
    s = irradiance(range_au) * np.cos(np.radians(sun_el)) * np.asarray(f_disc, float)
    azs = np.arange(0.0, 360.0, step_deg)
    c = np.maximum(0.0, np.cos(np.radians(np.asarray(sun_az)[None, :] - azs[:, None])))
    return float(azs[int(np.argmax(c @ s))])


# ---------------------------------------------------------------- battery

def simulate(gen_wh, load_wh, capacity_wh, bat, n_steps=None, step=None):
    """Battery state-of-charge simulation, vectorised over leading axes.

    gen_wh, load_wh: (..., N) interval energies, or pass `step(k) -> (gen_k, load_k)` and n_steps to avoid
    materialising windows. capacity_wh broadcasts to the cell shape. Returns a ledger dict (Wh unless noted)."""
    if step is None:
        gen_wh = np.asarray(gen_wh, float); load_wh = np.broadcast_to(np.asarray(load_wh, float), gen_wh.shape)
        n_steps = gen_wh.shape[-1]
        step = lambda k: (gen_wh[..., k], load_wh[..., k])          # noqa: E731
    g0, l0 = step(0)
    shape = np.broadcast_shapes(np.shape(g0), np.shape(l0), np.shape(capacity_wh))
    C = np.broadcast_to(np.asarray(capacity_wh, float), shape)
    reserve = bat.min_reserve_fraction * C
    soc = bat.initial_soc_fraction * C
    soc0 = soc.copy()
    min_raw = soc.copy()
    below = np.zeros(shape, np.int32)
    charged = np.zeros(shape); discharged = np.zeros(shape); spilled = np.zeros(shape); unserved = np.zeros(shape)
    gen_tot = np.zeros(shape); load_tot = np.zeros(shape)
    for k in range(n_steps):
        g, l = step(k)
        g = np.broadcast_to(g, shape); l = np.broadcast_to(l, shape)
        net = g - l
        gen_tot += g; load_tot += l
        surplus = np.maximum(net, 0.0); deficit = np.maximum(-net, 0.0)
        room = C - soc
        stored = np.minimum(bat.charge_efficiency * surplus, room)
        spilled += surplus - stored / bat.charge_efficiency
        draw = deficit / bat.discharge_efficiency
        raw = soc + stored - draw
        min_raw = np.minimum(min_raw, raw)
        taken = np.minimum(draw, soc + stored)
        unserved += (draw - taken) * bat.discharge_efficiency
        soc = soc + stored - taken
        charged += stored; discharged += taken
        below += (soc < reserve - 1e-9)
    return {'soc0': soc0, 'soc_end': soc, 'min_soc_raw': min_raw, 'min_soc': np.maximum(min_raw, 0.0),
            'hours_below_reserve': below, 'charged': charged, 'discharged': discharged, 'spilled': spilled,
            'unserved': unserved, 'gen': gen_tot, 'load': load_tot, 'capacity': C, 'reserve': reserve}


def feasible(ledger, tol_wh=1e-6):
    return ledger['min_soc_raw'] >= ledger['reserve'] - tol_wh


def capacity_upper_bound(load_total_wh, bat):
    return load_total_wh / (bat.discharge_efficiency * (bat.initial_soc_fraction - bat.min_reserve_fraction))


def battery_needed(gen_wh=None, load_wh=None, bat=None, n_steps=None, step=None, load_total_wh=None, iters=32):
    """Smallest capacity (Wh) keeping soc >= reserve over the window (bisection, vectorised). Returns the upper
    end of the final bracket (always feasible); bracket width = hi0 / 2**iters."""
    if step is None:
        gen_wh = np.asarray(gen_wh, float)
        load_total_wh = np.broadcast_to(np.asarray(load_wh, float), gen_wh.shape).sum(axis=-1)
    hi = np.asarray(capacity_upper_bound(load_total_wh, bat), float) * (1 + 1e-9) + 1e-6
    lo = np.zeros_like(hi)
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        ok = feasible(simulate(gen_wh, load_wh, mid, bat, n_steps=n_steps, step=step))
        hi = np.where(ok, mid, hi); lo = np.where(ok, lo, mid)
    return hi


def window_stepper(e_gen, e_load, starts):
    """step(k) for windows starting at interval indices `starts` (last axis of e_gen = interval)."""
    starts = np.asarray(starts, int)
    return lambda k: (e_gen[..., starts + k], e_load[starts + k])


def round_up(x, q=1.0, slack=0.01):
    """Ceil to q, ignoring the bisection bracket (<< slack): a window with no deficit reports 0, not 1 Wh."""
    return np.ceil(np.asarray(x) / q - slack) * q


__all__ = ['ARRAY_TYPES', 'Battery', 'Config', 'LABEL', 'Layout', 'SOLAR_CONSTANT_W_M2', 'battery_needed',
           'best_fixed_azimuth', 'capacity_upper_bound', 'cos_incidence', 'feasible', 'interval_energy_wh',
           'irradiance', 'layout_power', 'load_config', 'load_w', 'parse_simple_yaml', 'power_w', 'round_up',
           'simulate', 'window_stepper']
