#!/usr/bin/env python3
"""Build data/source_registry.json: one machine-readable record per external source and local source file.

Every local file is hashed (SHA-256) and, where a hash was already documented, compared with it.
Roles: numerical-authority | ephemeris-authority | reference-layer | visual-context | reference-only.
Nothing here validates the science: release status stays SOURCE_BASED_UNVALIDATED.
Usage:  python tools/sources/build_source_registry.py            write data/source_registry.json
        python tools/sources/build_source_registry.py --check    verify only: exit 1 on a hash mismatch or missing file
rasterio is optional (adds CRS/transform/nodata for GeoTIFFs).
"""
from __future__ import annotations
import glob, hashlib, json, os, sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SPS = "south polar stereographic, centre 90 S / 0 E, sphere R = 1737400 m, metres; +x toward 90 E, +y toward 0 E"
ME = "MOON_ME (mean Earth / polar axis) tied to DE421"

# Hashes documented before this registry existed (docs/DATA_PROVENANCE.md, app/assets/nasa/README.md).
DOCUMENTED = {
    "app/data/source/pgda78/Site01/Site01_final_adj_5mpp_surf.tif": "3ba7b97cb00a2bcf21189c3aeb535f65afc21207154ab9f0d43c5bdc1f7e747e",
    "app/data/source/pgda78/Site01/Site01_final_adj_5mpp_toterr.tif": "cf2cf52f52d2aa51e60d058010d10b0ebfb1d3e920f5a2b9a46eb6c51054ab1c",
    "app/data/source/pgda78/Site01/Clones/Site01_final_adj_5mpp_0001_err.tif": "242de9e3da624a276864cc4fa7c499e96981c95fd27583565e68e92434faf05b",
    "app/data/source/pgda78/Site01/Clones/Site01_final_adj_5mpp_0002_err.tif": "97b2c05633e308c72eddfc5a337089836d80b5edb7469321976973f7eeb7dcad",
    "app/data/source/pgda78/Site01/Clones/Site01_final_adj_5mpp_0050_err.tif": "5819388022b1f32d50eab7bdd1c8d8446a9ddfcf88ba4693d24116f86ea02e37",
    "app/data/source/pgda78/Site01/Clones/Site01_final_adj_5mpp_0100_err.tif": "596dcdf341b411893e2994571685bd54f911bfb476855ca6ce8d8f0f5f676698",
    "app/assets/nasa/NASA_SVS_Moon_NASA_LRO_8k_Topo_Small.glb": "c4b65fb4df622a37fd75366c2ed9bf9e163e41c0fde178b3b27e31b0173e6953",
    "app/assets/nasa/NASA_SVS_moon_small.glb": "12d3b0bb7fe214903f51447d1bc61710f442e92a11c703fcaca6d4e7ff8e67d4",
    "app/data/polaris-source-site01-2026-11-14-v2.json": "6a16ee59965e47afe54527c0b2bcdd90c6d40ba40a2423ca964e7da8e89a4fb6",
    "app/data/polaris-source-two-site-2026-11-14-v2.json": "b60129a0399e9dd58ab42e6fb7fe76c82355b2b823dbbf4f3fa80e3aa87658ee",
    "app/data/polaris-offline-source-case.json": "11919cfbbd9d84e68dad02520dadfc95880dd3a40aabe16d9e60a8e48a1dfee3",
    "app/data/polaris-runtime-source-case.json": "713099a1623690fd761dcab8b3b2a0439e3f87f96cddd58d0d722fddc4e72062",
}


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def raster_meta(path: str):
    try:
        import rasterio
    except ImportError:
        return None
    try:
        with rasterio.open(path) as d:
            t = d.transform
            return {"width": d.width, "height": d.height, "dtype": d.dtypes[0], "nodata": (None if d.nodata is None else str(d.nodata)),
                    "pixelSizeM": [t.a, -t.e], "originUpperLeftM": [t.c, t.f], "rowOrder": "row 0 = north (largest y)",
                    "pixelRegistration": d.tags().get("AREA_OR_POINT", "unstated"),
                    "boundsM": [d.bounds.left, d.bounds.bottom, d.bounds.right, d.bounds.top], "crsWkt": d.crs.to_wkt() if d.crs else None}
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


def local(rel: str, **extra):
    p = os.path.join(ROOT, rel)
    rec = {"path": rel, **extra}
    if not os.path.exists(p):
        rec.update(present=False)
        return rec
    digest = sha256(p)
    rec.update(present=True, bytes=os.path.getsize(p), sha256=digest,
               localFileMtimeUTC=datetime.fromtimestamp(os.path.getmtime(p), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    if rel in DOCUMENTED:
        rec["documentedSha256"] = DOCUMENTED[rel]
        rec["matchesDocumented"] = DOCUMENTED[rel] == digest
    if rel.lower().endswith((".tif", ".tiff")):
        m = raster_meta(p)
        if m:
            rec["raster"] = m
    return rec


def files(pattern: str, **extra):
    return [local(os.path.relpath(p, ROOT), **extra) for p in sorted(glob.glob(os.path.join(ROOT, pattern), recursive=True)) if os.path.isfile(p)]


def main() -> None:
    nac_manifests = [json.load(open(p)) | {"manifestPath": os.path.relpath(p, ROOT)} for p in sorted(glob.glob(os.path.join(ROOT, "data/visual/lroc_nac_pole_south_cm_avg/*_manifest.json")))]
    reg_checks = [json.load(open(p)) | {"path": os.path.relpath(p, ROOT)} for p in sorted(glob.glob(os.path.join(ROOT, "data/visual/lroc_nac_pole_south_cm_avg/*_registration.json")))]
    sources = [
        {"id": "NASA_PGDA_78", "role": "numerical-authority", "title": "LOLA 5 m/px south-pole site DEMs, uncertainty and clones",
         "url": "https://pgda.gsfc.nasa.gov/products/78", "dataUrl": "https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/",
         "credit": "NASA GSFC Planetary Geodesy Data Archive (PGDA)", "license": "not stated on the product page read; NASA public data, credit PGDA",
         "frame": ME, "projection": SPS, "pixelScaleM": 5, "verticalUnits": "metres (height relative to the 1737.4 km sphere)",
         "use": "local scientific geometry (nominal), total-Z RMS display, deterministic clones as alternatives (never probabilities)",
         "limitations": ["5 m is grid spacing: the product page reports that a large fraction of pixels are interpolated between LOLA tracks",
                         "only Site01 files are stored here; Site04 5 m data enters through a-science bundles"],
         "files": files("app/data/source/pgda78/**/*", acquired="2026-11-14 (docs/DATA_PROVENANCE.md)")},
        {"id": "NASA_PGDA_90", "role": "numerical-authority", "title": "LOLA regional south-pole DEM, LDEM_80S_80MPP_ADJ.TIF",
         "url": "https://pgda.gsfc.nasa.gov/products/90", "dataUrl": "https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LDEM_80S_80MPP_ADJ.TIF",
         "credit": "NASA GSFC PGDA", "frame": ME, "projection": SPS, "pixelScaleM": 80, "verticalUnits": "metres",
         "use": "regional horizon / long-range obstruction; not a substitute for the 5 m local surface",
         "wholeFileSha256": None, "wholeFileChecksumStatus": "remote COG read by HTTP range requests; never downloaded in full",
         "decodedCropSha256": {"Site01 401x401": "d27c5aa679cd00ffee0a95ce36e0049b3189b477a6e14efb941eecac92d73b5d",
                               "Site04 401x401": "e48bee96e517fe1e4d455a749d4f414e144be34c8a4639d536b8727cdc6383a4"},
         "decodedCropHashSource": "docs/DATA_PROVENANCE.md and the bundles' dem.cropValuesSha256", "files": []},
        {"id": "NASA_PGDA_69", "role": "reference-layer", "title": "Polar average Sun / Earth visibility (18.6-year, 60 m)",
         "url": "https://pgda.gsfc.nasa.gov/products/69", "credit": "NASA GSFC PGDA", "pixelScaleM": 60, "projection": SPS,
         "use": "separate reference/ranking map in the React viewer",
         "limitations": ["different quantity (disc-edge, surface pixel, 18.6-year average, 2016 DEM): NOT validation of the POLARIS mission-window solver"],
         "files": files("data/raw/pgda69/*")},
        {"id": "JPL_HORIZONS", "role": "ephemeris-authority", "title": "JPL Horizons observer tables, Sun (10) and Earth (399) from coord@301",
         "url": "https://ssd.jpl.nasa.gov/api/horizons.api", "docs": "https://ssd-api.jpl.nasa.gov/doc/horizons.html",
         "conventions": "UTC; airless apparent azimuth/elevation; azimuth clockwise from north (N 0, E 90); east-positive longitude",
         "use": "the only source of Sun/Earth directions; never Blender lamps or screen lighting",
         "note": "query URLs and API versions are stored inside each bundle's ephemeris.records[]",
         "files": files("app/data/raw/jpl/**/*.txt")},
        {"id": "NASA_SVS_14959", "role": "visual-context", "title": "Moon 3D Models for Web, AR, and Animation",
         "url": "https://svs.gsfc.nasa.gov/14959/", "credit": "NASA's Goddard Space Flight Center", "numericalAuthority": False,
         "use": "global navigation only; never sampled by any calculation",
         "limitations": ["the source page notes pinching/artifacts at the poles of the global model, which matters for a south-pole product"],
         "files": files("app/assets/nasa/*.glb", acquired="2026-11-14 (app/assets/nasa/README.md)")},
        {"id": "LROC_NAC_POLE_SOUTH_CM_AVG", "role": "visual-context", "title": "LROC Controlled 1 m/pixel South Pole Average Mosaic",
         "url": "https://data.lroc.im-ldi.com/lroc/view_rdr/NAC_POLE_SOUTH_CM_AVG",
         "dataUrl": "https://pds.lroc.im-ldi.com/data/LRO-L-LROC-5-RDR-V1.0/LROLRC_2001/DATA/BDR/NAC_POLE/NAC_POLE_SOUTH_CM_AVG/",
         "credit": "NASA/GSFC/Arizona State University (LROC team); cite Archinal et al. 2023, LPSC 54, #2333",
         "license": "not stated on the pages read; PDS-archived NASA mission data", "numericalAuthority": False,
         "frame": "controlled to LOLA track data (ISIS jigsaw); planetocentric, east-positive; frame name not stated in the label read",
         "projection": SPS, "pixelScaleM": 1,
         "use": "registered albedo/morphology texture over the 5 m DEM footprint (display only)",
         "limitations": ["average of 18,323 images under many Sun directions: per its label it does not represent any realistic lighting condition",
                         "shading is baked into the image; never use it as current-time illumination or to infer elevation",
                         "whole tile is 8.28 GB; only byte-range windows are stored, so there is no whole-file hash"],
         "windows": nac_manifests, "registrationChecks": reg_checks,
         "files": files("data/visual/lroc_nac_pole_south_cm_avg/*")},
        {"id": "USGS_LROC_WAC_MORPHOLOGY_100M", "role": "reference-only", "status": "not downloaded",
         "url": "https://astrogeology.usgs.gov/search/map/moon_lro_lroc_wac_global_morphology_mosaic_100m", "pixelScaleM": 100,
         "note": "candidate regional/global albedo; projection and the polar/non-polar brightness discontinuity must be checked before use", "files": []},
        {"id": "NASA_SVS_CGI_MOON_KIT", "role": "reference-only", "status": "not downloaded", "url": "https://svs.gsfc.nasa.gov/4720",
         "note": "look-development textures; the page says aesthetic products are not substitutes for scientific source data", "files": []},
        {"id": "SHADOWCAM", "role": "reference-only", "status": "not downloaded",
         "url": "https://www.nasa.gov/solar-system/nasas-shadowcam-images-lunar-south-pole-region/",
         "note": "PSR imagery only; never blend with illuminated LROC imagery as if radiometry matched", "files": []},
        {"id": "NASA_EYES_MOON_TREK", "role": "reference-only", "status": "interaction benchmarks, no data used",
         "url": "https://science.nasa.gov/eyes/", "url2": "https://trek.nasa.gov/moon/", "files": []},
    ]
    derived = {"note": "generated by this repository from the sources above; not sources themselves",
               "files": files("app/data/polaris-*.json") + files("data/bundles/*.json") + files("data/viewer/*.json"),
               "displayOnly": {"note": "VISUAL packs derived from the numerical DEMs for rendering only (numericalAuthority false): "
                                       "regional display copy + horizon maps (tools/terrain/build_terrain_context.py) and the visual-layers file",
                               "files": files("data/visual/terrain_context/*/*") + files("data/visual/visual_layers.json")}}
    all_files = [f for s in sources for f in s["files"]] + derived["files"] + derived["displayOnly"]["files"]
    mismatches = [f["path"] for f in all_files if f.get("matchesDocumented") is False]
    missing = [f["path"] for f in all_files if not f.get("present", True)] + [p for p in DOCUMENTED if not os.path.exists(os.path.join(ROOT, p))]
    reg = {"schema": "polaris-source-registry-v1", "generatedUTC": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "releaseStatus": "SOURCE_BASED_UNVALIDATED",
           "roles": {"numerical-authority": "feeds horizons, rays, metrics", "ephemeris-authority": "feeds Sun/Earth directions",
                     "reference-layer": "shown beside results, never mixed in", "visual-context": "display only, never numerical",
                     "reference-only": "consulted, not stored or used"},
           "summary": {"localFiles": len(all_files), "bytes": sum(f.get("bytes", 0) for f in all_files),
                       "documentedHashesChecked": sum(1 for f in all_files if "matchesDocumented" in f),
                       "hashMismatches": mismatches, "missingDocumentedFiles": sorted(set(missing))},
           "sources": sources, "derived": derived}
    out = os.path.join(ROOT, "data", "source_registry.json")
    if "--check" not in sys.argv:  # --check verifies only, so test runs do not rewrite the tracked file
        with open(out, "w") as f:
            json.dump(reg, f, indent=1)
    print(json.dumps(reg["summary"], indent=1))
    if "--check" in sys.argv and (mismatches or missing):
        sys.exit(1)


if __name__ == "__main__":
    main()
