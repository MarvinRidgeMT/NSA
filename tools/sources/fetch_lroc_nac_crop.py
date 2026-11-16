#!/usr/bin/env python3
"""Fetch a small window of the LROC controlled 1 m/px NAC south-pole AVERAGE mosaic by HTTP byte ranges.

VISUAL CONTEXT ONLY. The product is an average of 18,323 NAC images (2009-2013); its own label says it
"does not accurately represent any realistic lighting condition". It must never feed the horizon solver,
never be used to infer elevation, and never be presented as the illumination at a mission time.

Source (PDS3, uncompressed 32-bit PC_REAL, band sequential, 1 label record):
  https://pds.lroc.im-ldi.com/data/LRO-L-LROC-5-RDR-V1.0/LROLRC_2001/DATA/BDR/NAC_POLE/NAC_POLE_SOUTH_CM_AVG/
Tile P892S2250 covers 88.5-90 S, 180-270 E: polar stereographic, centre 90 S / 0 E, R = 1737400 m, 1 m/px,
45488 x 45488. Label: SAMPLE_PROJECTION_OFFSET = 45487.5, LINE_PROJECTION_OFFSET = -0.5 (LROC Nov-2011
definition: offsets from the CENTRE of pixel (1,1) to the projection origin, positive right / down).
Pixel-centre map coordinates (metres, same axes as the PGDA 78 / 90 GeoTIFFs: +x toward 90 E, +y toward 0 E):
  x = (sample - 1) - SAMPLE_PROJECTION_OFFSET        y = LINE_PROJECTION_OFFSET - (line - 1)
The script re-reads the label and refuses to run if any of these values differ.

Only the standard library is needed to download. numpy + Pillow (+ rasterio) are needed for the outputs.
Usage:
  python tools/sources/fetch_lroc_nac_crop.py --xmin -12000 --xmax -10000 --ymin -13000 --ymax -11000 \
      --name site01_center_2km --out data/visual/lroc_nac_pole_south_cm_avg
Re-running resumes: rows already fetched are kept in <name>.partial. The archive rate-limits bursts
(HTTP 429, Retry-After 3600 s was observed after ~1,000 requests with 12 threads); the defaults are slow on purpose.
"""
from __future__ import annotations
import argparse, hashlib, json, os, re, sys, time, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

TILE = "NAC_POLE_SOUTH_CM_AVG_P892S2250"
BASE = "https://pds.lroc.im-ldi.com/data/LRO-L-LROC-5-RDR-V1.0/LROLRC_2001/DATA/BDR/NAC_POLE/NAC_POLE_SOUTH_CM_AVG/"
EXPECT = {"RECORD_BYTES": 181952, "LABEL_RECORDS": 1, "LINES": 45488, "LINE_SAMPLES": 45488, "SAMPLE_BITS": 32,
          "SAMPLE_TYPE": "PC_REAL", "MAP_SCALE": 1.0, "CENTER_LATITUDE": -90.0, "CENTER_LONGITUDE": 0.0,
          "LINE_PROJECTION_OFFSET": -0.5, "SAMPLE_PROJECTION_OFFSET": 45487.5, "A_AXIS_RADIUS": 1737.4,
          "MAP_PROJECTION_TYPE": "POLAR STEREOGRAPHIC", "POSITIVE_LONGITUDE_DIRECTION": "EAST"}


class RateLimited(Exception):
    """HTTP 429 from the archive; the message is its Retry-After value in seconds."""


def get(url: str, start: int, end: int, tries: int = 5) -> bytes:
    last = None
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"Range": f"bytes={start}-{end}", "User-Agent": "polaris-x-source-fetch/1"})
            with urllib.request.urlopen(req, timeout=40) as r:
                data = r.read()
                if r.status != 206 or len(data) != end - start + 1:
                    raise IOError(f"range not honoured: status {r.status}, {len(data)} bytes")
                return data
        except urllib.error.HTTPError as e:
            if e.code == 429:  # the PDS host rate-limits; never hammer it
                raise RateLimited(e.headers.get("Retry-After") or "unknown") from e
            last = e
            time.sleep(1.0 * (k + 1))
        except Exception as e:  # noqa: BLE001 - retried, then re-raised
            last = e
            time.sleep(1.0 * (k + 1))
    raise last  # type: ignore[misc]


def window_to_pixels(xmin: float, xmax: float, ymin: float, ymax: float, s0: float, l0: float):
    """1-based inclusive (sample_first, sample_last, line_first, line_last) for pixel-EDGE bounds in metres at 1 m/px.

    Pixel centres: x = (sample-1) - s0, y = l0 - (line-1). Pixel `sample` spans x +-0.5, line spans y +-0.5.
    """
    return (int(round(xmin + s0 + 0.5)) + 1, int(round(xmax + s0 + 0.5)),
            int(round(l0 + 0.5 - ymax)) + 1, int(round(l0 + 0.5 - ymin)))


def missing_blocks(todo, block_rows: int):
    """Group sorted missing row indices into (first, count) runs of consecutive rows, at most block_rows long."""
    out, run = [], []
    for i in sorted(todo):
        if run and (i != run[-1] + 1 or len(run) >= block_rows):
            out.append((run[0], len(run))); run = []
        run.append(i)
    if run:
        out.append((run[0], len(run)))
    return out


def block_byte_range(first: int, count: int, l_first: int, s_first: int, w: int, rec: int, label_records: int):
    """Inclusive byte range covering window rows first..first+count-1 (0-based within the window): from the first wanted
    sample of the first row to the last wanted sample of the last row. Row k of the block starts k*rec bytes in."""
    start = rec * label_records + (l_first + first - 1) * rec + (s_first - 1) * 4
    return start, start + (count - 1) * rec + w * 4 - 1


def pixel_center_xy(sample: int, line: int, s0: float, l0: float):
    return (sample - 1) - s0, l0 - (line - 1)


def parse_label(text: str) -> dict:
    out = {}
    for key in EXPECT:
        m = re.search(rf"^\s*{key}\s*=\s*\"?([^\"<\r\n]+?)\"?\s*(<[^>]*>)?\s*$", text, re.M)
        if not m:
            raise SystemExit(f"label key missing: {key}")
        v = m.group(1).strip()
        out[key] = v if isinstance(EXPECT[key], str) else float(v)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for a in ("xmin", "xmax", "ymin", "ymax"):
        ap.add_argument(f"--{a}", type=float, required=True, help="pixel-EDGE bound, polar stereographic metres")
    ap.add_argument("--name", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--threads", type=int, default=2, help="keep low: the archive answers 429 (Retry-After 3600 s) to bursts")
    ap.add_argument("--pause-s", type=float, default=0.25, help="pause after each row request")
    ap.add_argument("--block-rows", type=int, default=1, help="fetch this many consecutive rows per request (fewer, larger requests; ~182 kB per row)")
    ap.add_argument("--budget-s", type=float, default=150, help="stop cleanly after this many seconds (resume by re-running)")
    a = ap.parse_args()
    url = BASE + TILE + ".IMG"
    try:
        run(a, url)
    except RateLimited as e:
        print(f"rate limited by the archive (HTTP 429, Retry-After {e} s). Rows fetched so far are kept; re-run later to resume.")
        sys.exit(4)


def run(a, url: str) -> None:
    with urllib.request.urlopen(urllib.request.Request(url, method="HEAD", headers={"User-Agent": "polaris-x-source-fetch/1"}), timeout=40) as r:
        final_url, total = r.geturl(), int(r.headers["Content-Length"])
        etag, modified = r.headers.get("ETag"), r.headers.get("Last-Modified")
    label_bytes = get(final_url, 0, 16383)
    label = parse_label(label_bytes.decode("latin-1"))
    for k, v in EXPECT.items():
        if label[k] != v:
            raise SystemExit(f"label {k} = {label[k]!r}, expected {v!r}: geometry rule not verified, refusing")
    rec, ns, nl = int(label["RECORD_BYTES"]), int(label["LINE_SAMPLES"]), int(label["LINES"])
    if total != rec * (nl + 1):
        raise SystemExit(f"file size {total} != {rec} x {nl + 1}")
    s0, l0 = label["SAMPLE_PROJECTION_OFFSET"], label["LINE_PROJECTION_OFFSET"]
    # pixel `s` (1-based) spans x in [s-1-s0-0.5, s-1-s0+0.5]; line L spans y in [l0-(L-1)-0.5, l0-(L-1)+0.5]
    s_first, s_last, l_first, l_last = window_to_pixels(a.xmin, a.xmax, a.ymin, a.ymax, s0, l0)
    if not (1 <= s_first <= s_last <= ns and 1 <= l_first <= l_last <= nl):
        raise SystemExit("requested window is outside tile " + TILE)
    w, h = s_last - s_first + 1, l_last - l_first + 1
    os.makedirs(a.out, exist_ok=True)
    partial, done_path = os.path.join(a.out, a.name + ".partial"), os.path.join(a.out, a.name + ".rows")
    if not os.path.exists(partial):
        with open(partial, "wb") as f:
            f.truncate(w * h * 4)
    done = set(int(x) for x in open(done_path).read().split()) if os.path.exists(done_path) else set()
    todo = [i for i in range(h) if i not in done]
    t0 = time.time()

    limited: list[str] = []

    def row(i: int):
        if limited or time.time() - t0 > a.budget_s:
            return None
        time.sleep(a.pause_s)
        line = l_first + i
        off = rec * int(label["LABEL_RECORDS"]) + (line - 1) * rec + (s_first - 1) * 4
        try:
            return i, get(final_url, off, off + w * 4 - 1)
        except RateLimited as e:
            limited.append(str(e))
            return None

    if a.block_rows > 1:
        # Few large requests instead of one per row: the archive limits request COUNT (HTTP 429 after ~1,000 small ones).
        # Each request covers `block_rows` consecutive missing rows, i.e. whole records in between (rec bytes per row).
        with open(partial, "r+b") as f, open(done_path, "a") as d:
            for first, count in missing_blocks(todo, a.block_rows):
                if time.time() - t0 > a.budget_s:
                    break
                start, end = block_byte_range(first, count, l_first, s_first, w, rec, int(label["LABEL_RECORDS"]))
                try:
                    data = get(final_url, start, end)
                except RateLimited as e:
                    limited.append(str(e))
                    break
                for k in range(count):
                    f.seek((first + k) * w * 4); f.write(data[k * rec: k * rec + w * 4]); d.write(f"{first + k}\n"); done.add(first + k)
                f.flush(); d.flush()
                time.sleep(a.pause_s)
    else:
        with open(partial, "r+b") as f, open(done_path, "a") as d, ThreadPoolExecutor(a.threads) as ex:
            for res in ex.map(row, todo):
                if res is None:
                    continue
                i, data = res
                f.seek(i * w * 4); f.write(data); d.write(f"{i}\n"); done.add(i)
    print(f"rows {len(done)}/{h} ({w} x {h} px) in {time.time() - t0:.0f} s")
    if limited:
        raise RateLimited(limited[0])
    if len(done) < h:
        print("incomplete: re-run the same command to resume"); sys.exit(3)

    import numpy as np
    from PIL import Image
    raw = open(partial, "rb").read()
    arr = np.frombuffer(raw, dtype="<f4").reshape(h, w)  # row 0 = northmost line (largest y), as in the source
    valid = np.isfinite(arr) & (arr > -3.0e38)  # ISIS special pixels are near -3.4028e38
    stats = {"validFraction": float(valid.mean()), "min": float(arr[valid].min()), "max": float(arr[valid].max()),
             "mean": float(arr[valid].mean())}
    p_lo, p_hi = (float(x) for x in np.percentile(arr[valid], [0.5, 99.5]))
    img8 = np.zeros((h, w), dtype=np.uint8)
    img8[valid] = np.clip(np.round(1 + 254 * (arr[valid] - p_lo) / (p_hi - p_lo)), 1, 255).astype(np.uint8)  # 0 = no data
    png = os.path.join(a.out, a.name + "_1m_8bit.png")
    Image.fromarray(img8, "L").save(png, optimize=True)
    tif = None
    try:
        import rasterio
        from rasterio.transform import from_origin
        tif = os.path.join(a.out, a.name + "_1m_f32.tif")
        wkt = ('PROJCS["Moon south polar stereographic, sphere R=1737400 m",GEOGCS["Moon sphere",DATUM["Moon_sphere",'
               'SPHEROID["Moon_sphere",1737400,0]],PRIMEM["Reference_Meridian",0],UNIT["degree",0.0174532925199433]],'
               'PROJECTION["Polar_Stereographic"],PARAMETER["latitude_of_origin",-90],PARAMETER["central_meridian",0],'
               'PARAMETER["false_easting",0],PARAMETER["false_northing",0],UNIT["metre",1]]')
        with rasterio.open(tif, "w", driver="GTiff", width=w, height=h, count=1, dtype="float32", crs=wkt,
                           transform=from_origin(a.xmin, a.ymax, 1.0, 1.0), compress="deflate", predictor=3,
                           nodata=float(np.float32(-3.4028226550889045e38))) as dst:
            dst.write(arr, 1)
    except ImportError:
        pass
    sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()  # noqa: E731
    manifest = {
        "role": "visual-context-only", "numericalAuthority": False,
        "product": {"dataSetId": "LRO-L-LROC-5-RDR-V1.0", "productId": TILE, "title": "Controlled 1 m/pixel South Pole Average Mosaic",
                    "productPage": "https://data.lroc.im-ldi.com/lroc/view_rdr/NAC_POLE_SOUTH_CM_AVG", "url": url, "resolvedUrl": final_url,
                    "fileBytes": total, "etag": etag, "lastModified": modified,
                    "cite": "Archinal et al. (2023), Controlled High-Resolution LROC NAC Polar Mosaics, LPSC 54, abstract 2333",
                    "wholeFileSha256": None, "wholeFileChecksumStatus": "8.28 GB tile not downloaded; only the byte ranges below"},
        "label": label, "labelSha256": hashlib.sha256(label_bytes).hexdigest(),
        "projection": {"type": "south polar stereographic", "centreLatDeg": -90, "centreLonEastDeg": 0, "radiusM": 1737400,
                       "pixelScaleM": 1.0, "axes": "+x toward 90 E, +y toward 0 E (same as PGDA 78/90 GeoTIFFs)",
                       "pixelRule": "x = (sample-1) - SAMPLE_PROJECTION_OFFSET; y = LINE_PROJECTION_OFFSET - (line-1); pixel centres"},
        "window": {"xminM": a.xmin, "xmaxM": a.xmax, "yminM": a.ymin, "ymaxM": a.ymax, "boundsAre": "pixel edges",
                   "sampleFirst": s_first, "sampleLast": s_last, "lineFirst": l_first, "lineLast": l_last, "width": w, "height": h,
                   "rowOrder": "row 0 = northmost (largest y), as in the source"},
        "acquiredUTC": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "rawWindowSha256": hashlib.sha256(raw).hexdigest(), "rawWindowDtype": "little-endian float32", "stats": stats,
        "display8bit": {"file": os.path.basename(png), "sha256": sha(png), "stretch": "linear, 0.5-99.5 percentile of valid pixels -> 1..255; 0 = no data",
                        "p0_5": p_lo, "p99_5": p_hi, "label": "VISUAL: display stretch, not radiometry"},
        "float32": ({"file": os.path.basename(tif), "sha256": sha(tif)} if tif else None),
        "limitations": [
            "Average of many NAC images under different Sun directions: not a real lighting state, and shading is baked in.",
            "Never an input to horizons, rays, elevations or metrics.",
            "Registration to the PGDA 78 5 m DEM is not guaranteed by either product; see the registration check in docs/DATA_PROVENANCE.md.",
            "Units of the averaged pixel value are not stated in the label read here; treated as relative brightness.",
        ],
    }
    with open(os.path.join(a.out, a.name + "_manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    for leftover in (partial, done_path):
        try:
            os.remove(leftover)
        except OSError as e:  # e.g. a sandbox that may not delete: the products above are complete either way
            print(f"note: could not remove {leftover} ({e}); it is safe to delete")
    print(json.dumps({"png": png, "tif": tif, "stats": stats, "rawWindowSha256": manifest["rawWindowSha256"]}, indent=1))


if __name__ == "__main__":
    main()
