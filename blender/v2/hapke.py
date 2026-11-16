"""Hapke regolith photometry for the v2 Blender scene. Pure Python (math only); numpy only for reading the PDS map.

MODEL (Hapke 2012, "Theory of Reflectance and Emittance Spectroscopy", 2nd ed., Cambridge UP; the form used for LROC WAC by
Sato, Robinson, Hapke, Denevi & Boyd 2014, "Resolved Hapke parameter maps of the Moon", JGR Planets 119, 1775-1805,
doi:10.1002/2013JE004580):

    r(i,e,g) = K w/(4 pi) * mu0e/(mu0e + mue) * [ p(g) (1 + B_SH(g)) + H(mu0e/K) H(mue/K) - 1 ] * (1 + B_CB(g)) * S(i,e,psi)

  p(g)    double-lobed Henyey-Greenstein, c > 0 = back-scattering:
          (1+c)/2 (1-b^2)/(1 - 2b cos g + b^2)^1.5 + (1-c)/2 (1-b^2)/(1 + 2b cos g + b^2)^1.5
  B_SH(g) = B_S0 / (1 + tan(g/2)/h_S)                       shadow-hiding opposition effect
  B_CB    = 0 (B_C0 fixed at 0.0 in the LROC product)        coherent backscatter off
  H(x)    Hapke (2002) approximation, r0 = (1-gamma)/(1+gamma), gamma = sqrt(1-w):
          H(x) = 1 / (1 - w x [r0 + (1 - 2 r0 x)/2 ln((1+x)/x)])
  S, mu0e, mue  macroscopic roughness (Hapke 1984, Icarus 59, 41; Hapke 2012 ch. 12), theta-bar = 23.657 deg (LROC fixed)
  K = 1 (LROC product: filling factor stored as 0, porosity correction off; README says "fixed at 1.0", see PARAMS note)

Units: r is the radiance factor per unit incident irradiance (sr^-1): L = r * E for a beam of irradiance E (normal to the
beam). I/F = pi r. The Blender shader sets a Diffuse BSDF colour to pi r / mu0 so Cycles returns L = r E and handles shadows.

The formula is written ONCE as an expression graph (class X). `X.eval` gives the Python value; hapke_nodes.py emits the
same graph as Blender Math nodes. `reference_r` is an independent straight-line implementation; tests compare the two.

The phase-function sign convention and the exact Sato et al. equation numbers could not be checked against the paper text
(publisher page not reachable from this session); the convention above is Hapke (2012) and agrees with the map values
(c > 0 almost everywhere: lunar regolith back-scatters). Stated as an open item in docs/v2/PHASE_4_BLENDER_RESULTS.md.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

# --- published parameters --------------------------------------------------------------------------------------------
# Source: NASA PDS LRO-L-LROC-5-RDR-V1.0, volume LROLRC_2001, product WAC_HAPKEPARAMMAP_643NM (v1.1, created 2020-07-24),
#   https://pds.mcp.nasa.gov/data/store/img/lunar_reconnaissance_orbiter/pds4/lroc/lro-l-lroc-5-rdr/LROLRC_2001/DATA/SDP/WAC_HAPKEPARAMMAP/WAC_HAPKEPARAMMAP_643NM.IMG
#   SHA-256 28b17aa716d4c2428561bb7615b70de578c06f04d8a7a288a623753a0ab68d0f (1 820 160 bytes, retrieved 2026-11-16T07:29Z).
#   README (same directory): "Maps consist of 9 Hapke parameters (w, b, c, Bc0, hc, Bs0, hs, theta, phi) ... Bc0 fixed at 0.0,
#   hc fixed at 1.0, theta fixed at 23.657, phi fixed at 1.0"; maps 1 deg x 1 deg, 70 N - 70 S; cite Sato et al. (2014).
# Decode: PDS3 attached label of 4 x 1440-byte records (the image starts at byte 5760; the PDS4 .xml says 1440, which does not
#   fit the file size), 9 bands x 140 lines x 360 samples, IEEE754 LSB float32, band-sequential, line 1 centred at 69.5 N.
# The south-pole sites (~89.5 S) are outside the map. SOUTH_60_70 is the median of each band over the ten southernmost lines
#   (60-70 S, 3600 cells); GLOBAL is the median over the whole map. Recomputed and checked by blender/tests/test_hapke.py when
#   the file is in the cache.
PARAMS_643NM = {
    'SOUTH_60_70': {'w': 0.4215, 'b': 0.1907, 'c': 0.8394, 'B_S0': 1.5505, 'h_S': 0.0155},
    'GLOBAL':      {'w': 0.3955, 'b': 0.2279, 'c': 0.4242, 'B_S0': 1.6595, 'h_S': 0.0505},
}
FIXED = {'B_C0': 0.0, 'h_C': 1.0, 'theta_bar_deg': 23.657, 'K': 1.0}
PDS_FILE = 'WAC_HAPKEPARAMMAP_643NM.IMG'
PDS_SHA256 = '28b17aa716d4c2428561bb7615b70de578c06f04d8a7a288a623753a0ab68d0f'
PDS_URL = ('https://pds.mcp.nasa.gov/data/store/img/lunar_reconnaissance_orbiter/pds4/lroc/lro-l-lroc-5-rdr/LROLRC_2001/'
           'DATA/SDP/WAC_HAPKEPARAMMAP/WAC_HAPKEPARAMMAP_643NM.IMG')
BANDS = ('w', 'b', 'c', 'B_C0', 'h_C', 'B_S0', 'h_S', 'theta_bar_deg', 'phi')


def params(region='SOUTH_60_70'):
    p = dict(PARAMS_643NM[region])
    p.update(theta_bar_deg=FIXED['theta_bar_deg'], K=FIXED['K'])
    return p


def read_pds_map(path):
    """Decode the PDS map -> dict band -> 140x360 numpy array (NaN for the PDS special constants). Needs numpy."""
    import numpy as np
    raw = Path(path).read_bytes()
    a = np.frombuffer(raw[5760:], '<f4').reshape(9, 140, 360).astype(float)
    a[a < -3.0e38] = np.nan           # CORE_NULL / saturation constants 0xFF7FFFFB.. are ~ -3.4e38
    return {name: a[k] for k, name in enumerate(BANDS)}, hashlib.sha256(raw).hexdigest()


def map_statistics(maps):
    import numpy as np
    out = {}
    for region, sl in (('SOUTH_60_70', slice(130, 140)), ('GLOBAL', slice(0, 140))):
        out[region] = {k: float(np.nanmedian(maps[k][sl])) for k in ('w', 'b', 'c', 'B_S0', 'h_S')}
    return out


# --- expression graph -------------------------------------------------------------------------------------------------
class X:
    """Tiny expression graph. op in {'const','var', binary ops, unary funcs, 'select'}."""
    __slots__ = ('op', 'args', 'value', 'name')

    def __init__(self, op, *args, value=None, name=None):
        self.op, self.args, self.value, self.name = op, args, value, name

    @staticmethod
    def c(v):
        return X('const', value=float(v))

    @staticmethod
    def var(name):
        return X('var', name=name)

    @staticmethod
    def wrap(v):
        return v if isinstance(v, X) else X.c(v)

    def __add__(self, o): return X('add', self, X.wrap(o))
    def __radd__(self, o): return X('add', X.wrap(o), self)
    def __sub__(self, o): return X('sub', self, X.wrap(o))
    def __rsub__(self, o): return X('sub', X.wrap(o), self)
    def __mul__(self, o): return X('mul', self, X.wrap(o))
    def __rmul__(self, o): return X('mul', X.wrap(o), self)
    def __truediv__(self, o): return X('div', self, X.wrap(o))
    def __rtruediv__(self, o): return X('div', X.wrap(o), self)
    def __neg__(self): return X('mul', self, X.c(-1.0))
    def __pow__(self, o): return X('pow', self, X.wrap(o))

    def eval(self, env, memo=None):
        memo = {} if memo is None else memo
        k = id(self)
        if k in memo:
            return memo[k]
        a = [x.eval(env, memo) for x in self.args]
        v = _EVAL[self.op](self, env, a)
        memo[k] = v
        return v

    def count(self, seen=None):
        seen = set() if seen is None else seen
        if id(self) in seen:
            return 0
        seen.add(id(self))
        return (0 if self.op in ('const', 'var') else 1) + sum(x.count(seen) for x in self.args)


def _f(name):
    return lambda *xs: X(name, *[X.wrap(x) for x in xs])


sin, cos, tan, exp, log, sqrt, acos, atan, fabs = (_f(n) for n in ('sin', 'cos', 'tan', 'exp', 'log', 'sqrt', 'acos', 'atan', 'abs'))
fmin, fmax = _f('min'), _f('max')


def select(cond, a, b):
    """a where cond > 0 else b (Blender: Math 'GREATER_THAN' + mix)."""
    return X('select', X.wrap(cond), X.wrap(a), X.wrap(b))


def _safe_log(x):
    return math.log(x) if x > 0 else -1e30


_EVAL = {
    'const': lambda n, env, a: n.value,
    'var': lambda n, env, a: float(env[n.name]),
    'add': lambda n, env, a: a[0] + a[1],
    'sub': lambda n, env, a: a[0] - a[1],
    'mul': lambda n, env, a: a[0] * a[1],
    'div': lambda n, env, a: a[0] / a[1] if a[1] != 0 else 0.0,     # Blender Math DIVIDE returns 0 for /0
    'pow': lambda n, env, a: a[0] ** a[1] if a[0] >= 0 else 0.0,
    'sin': lambda n, env, a: math.sin(a[0]),
    'cos': lambda n, env, a: math.cos(a[0]),
    'tan': lambda n, env, a: math.tan(a[0]),
    'exp': lambda n, env, a: math.exp(max(-700.0, min(700.0, a[0]))),
    'log': lambda n, env, a: _safe_log(a[0]),
    'sqrt': lambda n, env, a: math.sqrt(a[0]) if a[0] > 0 else 0.0,
    'acos': lambda n, env, a: math.acos(max(-1.0, min(1.0, a[0]))),
    'atan': lambda n, env, a: math.atan(a[0]),
    'abs': lambda n, env, a: abs(a[0]),
    'min': lambda n, env, a: min(a[0], a[1]),
    'max': lambda n, env, a: max(a[0], a[1]),
    'select': lambda n, env, a: a[1] if a[0] > 0 else a[2],
}

EPS = 1e-4


def hapke_graph(p, mu0=None, mu=None, cosg=None):
    """Radiance factor r as an expression of the three shading inputs mu0 = cos i, mu = cos e, cosg = cos g.
    Parameters are baked in as constants. Returns (r, intermediates)."""
    mu0 = X.var('mu0') if mu0 is None else mu0
    mu = X.var('mu') if mu is None else mu
    cosg = X.var('cosg') if cosg is None else cosg
    w, b, c, BS0, hS, K = p['w'], p['b'], p['c'], p['B_S0'], p['h_S'], p.get('K', 1.0)
    tb = math.tan(math.radians(p['theta_bar_deg']))
    m0 = fmax(mu0, EPS)
    m = fmax(mu, EPS)
    i = acos(m0)
    e = acos(m)
    cg = fmax(fmin(cosg, 1.0), -1.0)
    g = acos(cg)
    si, se = sqrt(1.0 - m0 * m0), sqrt(1.0 - m * m)
    cpsi = fmax(fmin((cg - m0 * m) / fmax(si * se, 1e-6), 1.0), -1.0)
    psi = acos(cpsi)
    s2h = (1.0 - cpsi) * 0.5                         # sin^2(psi/2)
    fpsi = exp(-2.0 * sqrt(fmax((1.0 - cpsi) / (1.0 + cpsi + 1e-9), 0.0)))   # exp(-2 tan(psi/2))
    if tb == 0:
        return _hapke_tail(p, m0, m, cg, m0, m, X.c(1.0), g, i, e)
    chi = 1.0 / math.sqrt(1.0 + math.pi * tb * tb)
    ti, te = fmax(si / m0, 1e-6), fmax(se / m, 1e-6)  # tan i, tan e
    E1 = lambda t: exp(-2.0 / (math.pi * tb) / t)                 # exp(-2/(pi tan(tb) tan x))
    E2 = lambda t: exp(-1.0 / (math.pi * tb * tb) / (t * t))      # exp(-1/(pi tan^2(tb) tan^2 x))
    E1i, E1e, E2i, E2e = E1(ti), E1(te), E2(ti), E2(te)
    eta = lambda cx, sx, E1x, E2x: chi * (cx + sx * tb * E2x / (2.0 - E1x))
    eta_i, eta_e = eta(m0, si, E1i, E2i), eta(m, se, E1e, E2e)
    pp = psi / math.pi
    # i <= e
    den_a = 2.0 - E1e - pp * E1i
    mu0e_a = chi * (m0 + si * tb * (cpsi * E2e + s2h * E2i) / den_a)
    mue_a = chi * (m + se * tb * (E2e - s2h * E2i) / den_a)
    S_a = (mue_a / eta_e) * (m0 / eta_i) * chi / (1.0 - fpsi + fpsi * chi * m0 / eta_i)
    # i > e
    den_b = 2.0 - E1i - pp * E1e
    mu0e_b = chi * (m0 + si * tb * (E2i - s2h * E2e) / den_b)
    mue_b = chi * (m + se * tb * (cpsi * E2i + s2h * E2e) / den_b)
    S_b = (mue_b / eta_e) * (m0 / eta_i) * chi / (1.0 - fpsi + fpsi * chi * m / eta_e)
    i_gt_e = i - e
    mu0e = select(i_gt_e, mu0e_b, mu0e_a)
    mue = select(i_gt_e, mue_b, mue_a)
    S = select(i_gt_e, S_b, S_a)
    return _hapke_tail(p, m0, m, cg, mu0e, mue, S, g, i, e)


def _hapke_tail(p, m0, m, cg, mu0e, mue, S, g, i, e):
    w, b, c, BS0, hS, K = p['w'], p['b'], p['c'], p['B_S0'], p['h_S'], p.get('K', 1.0)
    gam = math.sqrt(1.0 - w)
    r0 = (1.0 - gam) / (1.0 + gam)

    def H(x):
        x = fmax(x / K, 1e-6)
        return 1.0 / (1.0 - w * x * (r0 + (1.0 - 2.0 * r0 * x) * 0.5 * log((1.0 + x) / x)))

    b2 = b * b
    pg = ((1.0 + c) * 0.5 * (1.0 - b2) / (1.0 - 2.0 * b * cg + b2) ** 1.5
          + (1.0 - c) * 0.5 * (1.0 - b2) / (1.0 + 2.0 * b * cg + b2) ** 1.5)
    tan_half_g = sqrt(fmax((1.0 - cg) / (1.0 + cg + 1e-9), 0.0))
    BSH = BS0 / (1.0 + tan_half_g / hS)
    r = K * w / (4.0 * math.pi) * mu0e / (mu0e + mue) * (pg * (1.0 + BSH) + H(mu0e) * H(mue) - 1.0) * S
    r = fmax(r, 0.0)
    return r, {'g': g, 'i': i, 'e': e, 'S': S, 'mu0e': mu0e, 'mue': mue, 'p': pg, 'BSH': BSH}


def diffuse_colour_graph(p, mu0=None, mu=None, cosg=None, cap=4.0):
    """Colour for a Cycles Diffuse BSDF so that it returns L = r E under a beam of irradiance E: pi r / mu0 (capped)."""
    mu0 = X.var('mu0') if mu0 is None else mu0
    r, _ = hapke_graph(p, mu0, mu, cosg)
    return fmin(math.pi * r / fmax(mu0, EPS), cap), r


def r_value(p, i_deg, e_deg, g_deg):
    """Evaluate the graph for angles in degrees (g must be geometrically possible for i and e)."""
    r, _ = hapke_graph(p)
    env = {'mu0': math.cos(math.radians(i_deg)), 'mu': math.cos(math.radians(e_deg)), 'cosg': math.cos(math.radians(g_deg))}
    return r.eval(env)


# --- independent reference implementation (straight-line, no graph) --------------------------------------------------
def H_hapke2002(x, w):
    gam = math.sqrt(1 - w)
    r0 = (1 - gam) / (1 + gam)
    return 1.0 / (1.0 - w * x * (r0 + (1 - 2 * r0 * x) / 2 * math.log((1 + x) / x)))


def reference_r(p, i_deg, e_deg, g_deg):
    """Hapke (2012) radiance factor, written out directly from the equations (Hapke 2012 eqs. 12.46-12.55 for roughness)."""
    w, b, c, BS0, hS, K = p['w'], p['b'], p['c'], p['B_S0'], p['h_S'], p.get('K', 1.0)
    i, e, g = (math.radians(v) for v in (i_deg, e_deg, g_deg))
    tb = math.tan(math.radians(p['theta_bar_deg']))
    mu0, mu = math.cos(i), math.cos(e)
    if i_deg == 0 or e_deg == 0:
        cpsi = 1.0
    else:
        cpsi = max(-1.0, min(1.0, (math.cos(g) - mu0 * mu) / (math.sin(i) * math.sin(e))))
    psi = math.acos(cpsi)
    if tb == 0:
        mu0e, mue, S = mu0, mu, 1.0
    else:
        chi = 1 / math.sqrt(1 + math.pi * tb ** 2)
        def E1(x): return math.exp(-2 / math.pi / tb / math.tan(x)) if x > 0 else 0.0
        def E2(x): return math.exp(-1 / math.pi / tb ** 2 / math.tan(x) ** 2) if x > 0 else 0.0
        def eta(x): return chi * (math.cos(x) + math.sin(x) * tb * E2(x) / (2 - E1(x)))
        f = math.exp(-2 * math.tan(psi / 2))
        s2 = math.sin(psi / 2) ** 2
        if i <= e:
            d = 2 - E1(e) - psi / math.pi * E1(i)
            mu0e = chi * (mu0 + math.sin(i) * tb * (math.cos(psi) * E2(e) + s2 * E2(i)) / d)
            mue = chi * (mu + math.sin(e) * tb * (E2(e) - s2 * E2(i)) / d)
            S = mue / eta(e) * mu0 / eta(i) * chi / (1 - f + f * chi * mu0 / eta(i))
        else:
            d = 2 - E1(i) - psi / math.pi * E1(e)
            mu0e = chi * (mu0 + math.sin(i) * tb * (E2(i) - s2 * E2(e)) / d)
            mue = chi * (mu + math.sin(e) * tb * (math.cos(psi) * E2(i) + s2 * E2(e)) / d)
            S = mue / eta(e) * mu0 / eta(i) * chi / (1 - f + f * chi * mu / eta(e))
    pg = ((1 + c) / 2 * (1 - b * b) / (1 - 2 * b * math.cos(g) + b * b) ** 1.5
          + (1 - c) / 2 * (1 - b * b) / (1 + 2 * b * math.cos(g) + b * b) ** 1.5)
    BSH = BS0 / (1 + math.tan(g / 2) / hS)
    return K * w / (4 * math.pi) * mu0e / (mu0e + mue) * (pg * (1 + BSH) + H_hapke2002(mu0e / K, w) * H_hapke2002(mue / K, w) - 1) * S


def lommel_seeliger_check(p, i_deg, e_deg, g_deg):
    """Ratio of the Hapke r to the Lommel-Seeliger law mu0/(mu0+mu) at the same geometry (diagnostic, not a test oracle)."""
    mu0, mu = math.cos(math.radians(i_deg)), math.cos(math.radians(e_deg))
    return reference_r(p, i_deg, e_deg, g_deg) / (mu0 / (mu0 + mu))
