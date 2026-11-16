#!/usr/bin/env python3
"""Estimate the horizontal offset between an LROC NAC average-mosaic window and the PGDA 78 5 m DEM.

Method (display-registration evidence only, not a validation of either product):
  1. Block-average the 1 m image to the DEM's 5 m pixels (both are pixel-registered on multiples of 5 m).
  2. From the DEM build a proxy for "average brightness under a low Sun circling the horizon":
     mean over 72 azimuths of max(0, n . s) at Sun elevation 1.5 deg, no cast shadows.
  3. High-pass both (subtract a 25-pixel box mean), normalise, and find the integer shift (within +-12 px = 60 m)
     that maximises the normalised cross-correlation; refine with a 3-point parabola.
Reports the shift of the IMAGE relative to the DEM in metres (+x toward 90 E, +y toward 0 E) and the peak NCC.
"""
from __future__ import annotations
import argparse, json
import numpy as np, rasterio
from rasterio.windows import Window


def boxmean(a, k):
    pad = k // 2
    p = np.pad(a, pad, mode="reflect")
    c = np.cumsum(np.cumsum(p, 0), 1)
    c = np.pad(c, ((1, 0), (1, 0)))
    return (c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]) / (k * k)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--image-raw", help="little-endian float32 window, row 0 = north (needs --width --rows --xmin --ymax)")
    ap.add_argument("--image-tif", help="the *_1m_f32.tif written by fetch_lroc_nac_crop.py (size and origin are read from it)")
    ap.add_argument("--width", type=int); ap.add_argument("--rows", type=int)
    ap.add_argument("--xmin", type=float); ap.add_argument("--ymax", type=float)
    ap.add_argument("--dem", required=True)
    ap.add_argument("--out")
    a = ap.parse_args()
    if a.image_tif:
        with rasterio.open(a.image_tif) as src:
            if abs(src.transform.a - 1.0) > 1e-9 or abs(src.transform.e + 1.0) > 1e-9:
                raise SystemExit("image must be 1 m/px, north-up")
            a.width, a.rows, a.xmin, a.ymax = src.width, src.height, src.transform.c, src.transform.f
            full = src.read(1)
        rows = (a.rows // 5) * 5
        img = full[:rows].astype("f8")
    elif a.image_raw and None not in (a.width, a.rows, a.xmin, a.ymax):
        rows = (a.rows // 5) * 5
        img = np.fromfile(a.image_raw, dtype="<f4", count=a.width * rows).reshape(rows, a.width).astype("f8")
    else:
        raise SystemExit("give --image-tif, or --image-raw with --width --rows --xmin --ymax")
    img[~(img > -3e38)] = np.nan
    i5 = np.nanmean(img.reshape(rows // 5, 5, a.width // 5, 5), axis=(1, 3))
    with rasterio.open(a.dem) as d:
        t = d.transform
        col0, row0 = round((a.xmin - t.c) / t.a), round((t.f - a.ymax) / -t.e)
        z = d.read(1, window=Window(col0, row0, a.width // 5, rows // 5)).astype("f8")
        sp = t.a
    dzdx = np.gradient(z, sp, axis=1)          # +x east-ish grid axis
    dzdy = -np.gradient(z, sp, axis=0)         # rows run north -> south, so +y = -row
    nrm = np.sqrt(dzdx**2 + dzdy**2 + 1)
    nx, ny, nz = -dzdx / nrm, -dzdy / nrm, 1 / nrm
    e = np.radians(1.5); sim = np.zeros_like(z)
    for az in np.radians(np.arange(0, 360, 5)):
        sim += np.maximum(0, np.sin(e) * nz + np.cos(e) * (nx * np.sin(az) + ny * np.cos(az)))
    sim /= 72
    ok = np.isfinite(i5) & np.isfinite(sim)
    A = np.where(ok, i5, np.nanmean(i5)); B = np.where(ok, sim, np.nanmean(sim))
    A = A - boxmean(A, 25); B = B - boxmean(B, 25)
    m, best, R = 12, None, {}
    for dy in range(-m, m + 1):
        for dx in range(-m, m + 1):
            a_ = A[m + dy: A.shape[0] - m + dy, m + dx: A.shape[1] - m + dx]
            b_ = B[m: B.shape[0] - m, m: B.shape[1] - m]
            r = float(np.sum((a_ - a_.mean()) * (b_ - b_.mean())) / (np.sqrt(np.sum((a_ - a_.mean())**2) * np.sum((b_ - b_.mean())**2))))
            R[(dy, dx)] = r
            if best is None or r > best[0]:
                best = (r, dy, dx)
    r, dy, dx = best
    def sub(c, lo, hi):
        den = lo - 2 * c + hi
        return 0.0 if den == 0 else 0.5 * (lo - hi) / den
    sx = dx + (sub(r, R[(dy, dx - 1)], R[(dy, dx + 1)]) if abs(dx) < m else 0)
    sy = dy + (sub(r, R[(dy - 1, dx)], R[(dy + 1, dx)]) if abs(dy) < m else 0)
    out = {"peakNcc": round(r, 4), "nccAtZeroShift": round(R[(0, 0)], 4),
           "imageShiftRelativeToDemM": {"x": round(sx * sp, 2), "y": round(-sy * sp, 2)},
           "searchRadiusM": m * sp, "comparedPixels5m": int(ok.sum()), "rowsUsed1m": rows,
           "atSearchEdge": abs(dx) == m or abs(dy) == m,
           "windowM": {"xmin": a.xmin, "xmax": a.xmin + a.width, "ymax": a.ymax, "ymin": a.ymax - rows},
           "dem": a.dem.replace("\\", "/"), "status": "display-alignment-evidence-only",
           "method": "5 m block mean of image vs DEM mean-low-Sun proxy, 25-px high-pass, integer NCC + parabola"}
    print(json.dumps(out, indent=1))
    if a.out:
        json.dump(out, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
