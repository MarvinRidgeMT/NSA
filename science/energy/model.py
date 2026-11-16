"""Phase 5 energy margin: array power and battery state of charge. Label: ENGINEERING ASSUMPTION.

Power (W) per hourly sample:
    P(t) = S(t) * A * eta * f_disc(t) * cos(incidence),   S(t) = S0 * (1 au / r(t))^2
  f_disc  visible fraction of the Sun disc at the array top (= D_mast) from the hourly disc-fraction cube
          (flat-local-horizon circular segment, uniform disc: no limb darkening);
  r       JPL Horizons observer-Sun range (au);
  cos(incidence) for a vertical array:
    'vsat'            single-axis vertical Sun tracking (rotates about the local vertical to face the Sun's
                      azimuth): cos(inc) = cos(el)
    'fixed_vertical'  fixed vertical face, outward normal at azimuth phi (ENU, 0 = north, 90 = east):
                      cos(inc) = max(0, cos(el) cos(az - phi))
  Only Sun quantities enter. Earth geometry and any antenna height never do (test_energy).

Battery (Wh), hourly sample-and-hold, absolute reserve R:
  net = (P - L) * dt;  net >= 0: stored += eta_c * net, clipped at capacity C (excess = curtailed)
                       net <  0: stored -= -net / eta_d, clipped at 0 (shortfall = unmet load)
  The update is order-preserving in the stored energy and in C, so with a fixed initial SoC fraction and an
  absolute reserve, "SoC >= reserve over the whole window" is monotone in C (bisection is valid) and the hours
  below reserve never increase with C.
"""
from __future__ import annotations

import math
import re
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
DEFAULT_CONFIG = HERE / 'assumptions.yaml'
LABEL = 'ENGINEERING ASSUMPTION'
ARRAYS = ('vsat', 'fixed_vertical')


# ---------------------------------------------------------------- config

def _scalar(s):
    s = s.strip()
    if s in ('', 'null', '~'):
        return None
    if s in ('true', 'false'):
        return s == 'true'
    if len(s) >= 2 and s[0] == s[-1] and s[0] in '"\'':
        return s[1:-1]
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        return s


def _parse_subset(text):
    """Strict YAML subset: nested mappings by indentation, scalars, and lists of mappings ('- k: v')."""
    lines = []
    for raw in text.splitlines():
        line = re.sub(r'(^|\s)#.*$', '', raw).rstrip()
        if line.strip():
            lines.append((len(line) - len(line.lstrip(' ')), line.strip()))
    pos = 0

    def block(indent):
        nonlocal pos
        if pos < len(lines) and lines[pos][1].startswith('- '):
            out = []
            while pos < len(lines) and lines[pos][0] == indent and lines[pos][1].startswith('- '):
                ind, txt = lines[pos]
                lines[pos] = (ind + 2, txt[2:])
                out.append(block(ind + 2))
            return out
        out = {}
        while pos < len(lines) and lines[pos][0] == indent and not lines[pos][1].startswith('- '):
            key, sep, val = lines[pos][1].partition(':')
            if not sep:
                raise ValueError(f'not a mapping line: {lines[pos][1]!r}')
            pos += 1
            if val.strip():
                out[key.strip()] = _scalar(val)
            elif pos < len(lines) and lines[pos][0] > indent:
                out[key.strip()] = block(lines[pos][0])
            else:
                out[key.strip()] = None
        return out

    out = block(lines[0][0] if lines else 0)
    if pos != len(lines):
        raise ValueError(f'unparsed line: {lines[pos][1]!r}')
    return out


def load_config(path=DEFAULT_CONFIG):
    text = Path(path).read_text()
    try:
        import yaml  # type: ignore
        cfg = yaml.safe_load(text)
    except ImportError:
        cfg = _parse_subset(text)
    b = cfg['battery']
    for k in ('charge_efficiency', 'discharge_efficiency'):
        if not 0 < b[k] <= 1:
            raise ValueError(f'battery.{k} must be in (0, 1]')
    if not 0 < b['initial_soc'] <= 1:
        raise ValueError('battery.initial_soc must be in (0, 1]')
    if b['reserve_wh'] < 0:
        raise ValueError('battery.reserve_wh must be >= 0')
    return cfg


# ---------------------------------------------------------------- power

def irradiance(range_au, s0=1361.0):
    r = np.asarray(range_au, float)
    return s0 / (r * r)


def cos_incidence(array, sun_el_deg, sun_az_deg=None, fixed_azimuth_deg=0.0):
    el = np.radians(np.asarray(sun_el_deg, float))
    if array == 'vsat':
        return np.maximum(np.cos(el), 0.0)
    if array == 'fixed_vertical':
        if sun_az_deg is None:
            raise ValueError('fixed_vertical needs the Sun azimuth')
        daz = np.radians(np.asarray(sun_az_deg, float) - fixed_azimuth_deg)
        return np.maximum(np.cos(el) * np.cos(daz), 0.0)
    raise ValueError(f'unknown array type {array!r}')


def power_w(cfg, array, sun_fraction, sun_el_deg, sun_az_deg, sun_range_au):
    """Array power at the bus (W) per sample. Takes only Sun inputs by construction."""
    a = cfg['array']
    f = np.clip(np.nan_to_num(np.asarray(sun_fraction, float), nan=0.0), 0.0, 1.0)
    return (irradiance(sun_range_au, cfg['solar_constant_w_m2']) * a['area_m2'] * a['efficiency'] * f
            * cos_incidence(array, sun_el_deg, sun_az_deg, a['fixed_azimuth_deg']))


def load_w(cfg, t_unix):
    """Constant + daily scheduled load (W) at each sample time (unix s, UTC)."""
    t = np.asarray(t_unix, float)
    hour = np.floor((t % 86400.0) / 3600.0 + 1e-9)
    L = np.full(t.shape, float(cfg['load']['constant_w']))
    for s in cfg['load'].get('scheduled') or []:
        h0, dur = float(s['utc_hour_start']), float(s['duration_h'])
        on = ((hour - h0) % 24.0) < dur
        L = L + np.where(on, float(s['power_w']), 0.0)
    return L


# ---------------------------------------------------------------- battery

def _step(E, C, net, eta_c, eta_d):
    """One sample-and-hold step. Returns new E plus ledger terms (bus Wh): curtailed, unmet, loss."""
    pos = net >= 0
    charge = np.where(pos, net, 0.0) * eta_c
    draw = np.where(pos, 0.0, -net) / eta_d
    E1 = E + charge - draw
    over = np.maximum(E1 - C, 0.0)          # stored-side excess above capacity
    under = np.maximum(-E1, 0.0)            # stored-side shortfall below empty
    E2 = E1 - over + under
    curtailed = over / eta_c
    unmet = under * eta_d
    accepted = np.where(pos, net, 0.0) - curtailed
    delivered = (draw - under) * eta_d
    loss = accepted * (1.0 - eta_c) + delivered * (1.0 / eta_d - 1.0)
    return E2, curtailed, unmet, loss


def simulate(gen_wh, load_wh, capacity_wh, cfg, ledger=False):
    """gen_wh, load_wh: (..., n_steps) energy per step. capacity_wh broadcasts against (...).

    Returns dict: soc (..., n+1) stored Wh incl. start, min_soc_frac, hours_below_reserve, ok (SoC >= reserve
    at every sample), and with ledger=True the totals gen, load, served, curtailed, unmet, loss (Wh).
    """
    b = cfg['battery']; dt = float(cfg.get('timestep_h', 1.0))
    gen = np.asarray(gen_wh, float); L = np.broadcast_to(np.asarray(load_wh, float), gen.shape)
    C = np.broadcast_to(np.asarray(capacity_wh, float), gen.shape[:-1]).astype(float)
    E = C * b['initial_soc']
    n = gen.shape[-1]
    soc = np.empty(gen.shape[:-1] + (n + 1,)); soc[..., 0] = E
    tot = {k: np.zeros(gen.shape[:-1]) for k in ('curtailed', 'unmet', 'loss')}
    for k in range(n):
        E, cu, un, lo = _step(E, C, gen[..., k] - L[..., k], b['charge_efficiency'], b['discharge_efficiency'])
        soc[..., k + 1] = E
        if ledger:
            tot['curtailed'] += cu; tot['unmet'] += un; tot['loss'] += lo
    R = b['reserve_wh']
    below = soc[..., 1:] < R - 1e-9
    with np.errstate(invalid='ignore', divide='ignore'):
        mn = np.where(C > 0, soc.min(axis=-1) / C, 0.0)
    out = {'soc': soc, 'min_soc_frac': mn, 'hours_below_reserve': below.sum(axis=-1) * dt,
           'ok': (soc >= R - 1e-9).all(axis=-1)}
    if ledger:
        out.update(tot)
        out['gen'] = gen.sum(axis=-1); out['load'] = L.sum(axis=-1)
        out['served'] = out['load'] - tot['unmet']
    return out


def _ok_only(gen, L, C, cfg):
    """Fast path for the bisection: True where SoC >= reserve at every sample."""
    b = cfg['battery']; R = b['reserve_wh'] - 1e-9
    ec, ed = b['charge_efficiency'], b['discharge_efficiency']
    E = C * b['initial_soc']
    ok = E >= R
    for k in range(gen.shape[-1]):
        net = gen[..., k] - L[..., k]
        E = np.clip(E + np.where(net >= 0, net * ec, net / ed), 0.0, C)
        ok &= E >= R
    return ok


def capacity_needed(gen_wh, load_wh, cfg, tol_wh=None):
    """Smallest capacity (Wh, upper bracket within tol) with SoC >= reserve over the whole window. Bisection.

    Upper start: (reserve + total load / eta_d) / initial_soc always suffices (the battery alone could carry
    the whole window's load above the reserve)."""
    b = cfg['battery']
    tol = float(tol_wh if tol_wh is not None else cfg['bisection']['tolerance_wh'])
    gen = np.asarray(gen_wh, float); L = np.broadcast_to(np.asarray(load_wh, float), gen.shape)
    hi = (b['reserve_wh'] + L.sum(axis=-1) / b['discharge_efficiency']) / b['initial_soc'] * 1.001 + tol
    hi = np.broadcast_to(hi, gen.shape[:-1]).astype(float).copy()
    lo = np.zeros_like(hi)
    if not _ok_only(gen, L, hi, cfg).all():
        raise AssertionError('upper bracket does not satisfy the reserve')
    lo_ok = _ok_only(gen, L, lo, cfg)
    hi = np.where(lo_ok, 0.0, hi)
    iters = int(math.ceil(math.log2(max(float(hi.max()), tol) / tol))) + 1
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        ok = _ok_only(gen, L, mid, cfg)
        hi = np.where(ok, mid, hi); lo = np.where(ok, lo, mid)
    return hi


def windows(hourly, starts, n_steps):
    """(..., H) -> (..., len(starts), n_steps) view of consecutive samples from each start."""
    from numpy.lib.stride_tricks import sliding_window_view
    v = sliding_window_view(hourly, n_steps, axis=-1)
    return v[..., starts, :]
