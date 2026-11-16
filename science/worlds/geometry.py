"""Sphere geometry and polar stereographic projections parameterised by the world's radius.

The formulas and their operation order are those of science/frames.py (written for R = 1 737 400 m), so with the Moon's
radius every function here returns bit-identical numbers (science/worlds/tests/test_geometry.py checks this). Nothing in
science/frames.py is changed.

Conventions (identical to frames.py): planetocentric latitude, east-positive longitude, body-fixed
P = (R + h) [cos lat cos lon, cos lat sin lon, sin lat]; azimuth clockwise from LOCAL north; elevation above the plane
normal to the site radius vector (sphere normal), no refraction.

Polar stereographic (sphere radius Rp, true scale at the pole, central meridian 0):
  south (lat_0 = -90): rho = 2 Rp tan(pi/4 + lat/2),  x = rho sin lon,  y =  rho cos lon   (= frames.stereo_forward)
  north (lat_0 = +90): rho = 2 Rp tan(pi/4 - lat/2),  x = rho sin lon,  y = -rho cos lon   (PROJ +proj=stere +lat_0=90)
The north form is the PDS DSMAP_POLAR convention used by the MESSENGER MLA GDR labels (checked against pyproj in tests).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Sphere:
    R: float   # reference radius for heights and ray geometry (m)

    def unit(self, lat, lon):
        la = np.radians(lat); lo = np.radians(lon)
        return np.stack([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)], axis=-1)

    def body_fixed(self, lat, lon, h):
        return (self.R + np.asarray(h, dtype=float))[..., None] * self.unit(lat, lon) \
            if np.ndim(h) else (self.R + float(h)) * self.unit(lat, lon)

    def up(self, lat, lon):
        return self.unit(lat, lon)

    @staticmethod
    def enu_basis(lat, lon):
        la = math.radians(lat); lo = math.radians(lon)
        e = np.array([-math.sin(lo), math.cos(lo), 0.0])
        n = np.array([-math.sin(la) * math.cos(lo), -math.sin(la) * math.sin(lo), math.cos(la)])
        u = np.array([math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la)])
        return e, n, u

    @staticmethod
    def elevation_angle_deg(P_obs, up, P):
        v = np.asarray(P) - np.asarray(P_obs)
        r = np.linalg.norm(v, axis=-1)
        return np.degrees(np.arcsin(np.clip((v @ np.asarray(up)) / r, -1.0, 1.0)))

    def destination(self, lat, lon, az_deg, s_m):
        """Great-circle destination on the R sphere (vectorised in s_m / az); same formula as frames.destination."""
        la = math.radians(lat); lo = math.radians(lon)
        a = np.radians(az_deg); d = np.asarray(s_m, dtype=float) / self.R
        sla = np.sin(la) * np.cos(d) + np.cos(la) * np.sin(d) * np.cos(a)
        la2 = np.arcsin(np.clip(sla, -1, 1))
        lo2 = lo + np.arctan2(np.sin(a) * np.sin(d) * np.cos(la), np.cos(d) - np.sin(la) * sla)
        lat2 = np.degrees(la2); lon2 = (np.degrees(lo2) + 180.0) % 360.0 - 180.0
        if np.ndim(lat2) == 0:
            return float(lat2), float(lon2)
        return lat2, lon2

    def smooth_dip_deg(self, eye_height_m):
        return -math.degrees(math.acos(self.R / (self.R + eye_height_m))) if eye_height_m > 0 else 0.0


@dataclass(frozen=True)
class PolarStereo:
    Rp: float          # projection sphere radius (m); may differ from the height datum (MLA: 2 439.4 vs 2 440.0 km)
    pole: str          # 'north' | 'south'

    def forward(self, lat, lon):
        lat = np.asarray(lat, dtype=float); lon = np.asarray(lon, dtype=float)
        if self.pole == 'south':
            rho = 2 * self.Rp * np.tan(np.pi / 4 + np.radians(lat) / 2)
            x = rho * np.sin(np.radians(lon)); y = rho * np.cos(np.radians(lon))
        else:
            rho = 2 * self.Rp * np.tan(np.pi / 4 - np.radians(lat) / 2)
            x = rho * np.sin(np.radians(lon)); y = -rho * np.cos(np.radians(lon))
        return (float(x), float(y)) if x.ndim == 0 else (x, y)

    def inverse(self, x, y):
        x = np.asarray(x, dtype=float); y = np.asarray(y, dtype=float)
        rho = np.hypot(x, y)
        if self.pole == 'south':
            lat = np.degrees(2 * np.arctan(rho / (2 * self.Rp)) - np.pi / 2)
            lon = np.degrees(np.arctan2(x, y))
        else:
            lat = np.degrees(np.pi / 2 - 2 * np.arctan(rho / (2 * self.Rp)))
            lon = np.degrees(np.arctan2(x, -y))
        return (float(lat), float(lon)) if lat.ndim == 0 else (lat, lon)

    def proj4(self):
        return f"+proj=stere +lat_0={90 if self.pole == 'north' else -90} +lon_0=0 +k=1 +x_0=0 +y_0=0 +R={self.Rp:g} +units=m"
