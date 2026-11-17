"""Mars data catalogue (T3, prompt §3.3). Same `Product`/`FileSpec` records as tools/globe/products.py, so the S2 fetcher
(tools.globe.fetch.fetch_product) downloads them unchanged and appends the same manifest lines to
$POLARIS_DATA/v2/manifest.jsonl; files land under $POLARIS_DATA/v2/products/mars_*/.

Byte counts are what the archives' own listings reported on 2026-11-16/17 (PDS Geosciences directory listing of
mgs-m-mola-5-megdr-l3-v1/mgsl_300x; the USGS Astrogeology S3 bucket listing of mosaic/mars2020_trn/). Every source is
public, no login.

Datums (read from the labels; the CTX one is settled by data, see science/worlds/mars/dem.py):
  * MOLA MEGDR megr*: PLANETARY RADIUS - 3 396 000 m (int16 m, OFFSET 3396000 in the label).
  * MOLA MEGDR megt*: topography = radius - areoid (int16 m); mega*: areoid radius - 3 396 000 m (4/16 ppd only).
  * MOLA MEGDR megc*: number of MOLA shots per pixel (data-density honesty layer).
  * CTX DEMs (Mars 2020): float32 m; the file names say MOLA topography (areoid heights, "DeltaGeoid"), the XML prose says
    "refer to the Mars 2020 IAU Sphere 3396190 m". Not assumed: tested against MEGDR radius and topography.

Import-safe: no network, no third-party packages.
"""
from __future__ import annotations

from typing import Dict, List

from tools.globe.products import LIC_NASA_PDS, FileSpec, Product

LISTED_UTC = "2026-11-17"

PDS_MEGDR = "https://pds-geosciences.wustl.edu/mgs/mgs-m-mola-5-megdr-l3-v1/mgsl_300x"
USGS_TRN = "https://asc-pds-services.s3.us-west-2.amazonaws.com/mosaic/mars2020_trn"

ACK_MOLA = ("Smith, D. E., Neumann, G., Arvidson, R. E., Guinness, E. A., Slavney, S. (2003), Mars Global Surveyor Laser "
            "Altimeter Mission Experiment Gridded Data Record, MGS-M-MOLA-5-MEGDR-L3-V1.0, NASA Planetary Data System. "
            "Smith, D. E., et al. (2001), Mars Orbiter Laser Altimeter: experiment summary after the first year of global "
            "mapping of Mars, JGR 106(E10), 23689-23722.")
ACK_CTX_SCI = ("Mars 2020 Science Investigation CTX DEM mosaic (urn:nasa:pds:mars2020_ctx_basemap_2021), JPL/USGS; cite "
               "Mangold, N., et al. (2021), Perseverance rover reveals an ancient delta-lake system and flood deposits at "
               "Jezero crater, Mars, Science 374, 711-717, doi:10.1126/science.abl4051. CTX: NASA/JPL/MSSS.")
ACK_CTX_TRN = ("Fergason, R. L., Hare, T. M., Mayer, D. P., Galuszka, D. M., Redding, B. L., Smith, E. D., Shinaman, J. R., "
               "Cheng, Y., Otero, R. E. (2020), Mars 2020 Terrain Relative Navigation Flight Product Generation: Digital "
               "Terrain Model and Orthorectified Image Mosaics, LPSC 51, #2020; USGS Astrogeology, doi:10.5066/P906QQT8. "
               "CTX: NASA/JPL/MSSS.")
LIC_USGS_MARS = ("USGS Astrogeology Science Center distribution of NASA Mars Reconnaissance Orbiter CTX products: U.S. "
                 "Government work / public domain in the U.S.; CTX data credit NASA/JPL/Malin Space Science Systems.")


def _megdr(sub: str, names: List[tuple]) -> List[FileSpec]:
    out: List[FileSpec] = []
    for name, size in names:
        out.append(FileSpec(f"{PDS_MEGDR}/{sub}/{name}.img", size, f"{sub}/{name}.img"))
        out.append(FileSpec(f"{PDS_MEGDR}/{sub}/{name}.lbl", None, f"{sub}/{name}.lbl"))
    return out


PRODUCTS: Dict[str, Product] = {}


def _add(p: Product) -> None:
    PRODUCTS[p.product_id] = p


_add(Product(
    "mars_mola_megdr_004", "MOLA MEGDR 4 ppd global: radius, topography, areoid, shot counts", None,
    "https://pds-geosciences.wustl.edu/missions/mgs/megdr.html", "PDS Geosciences Node (mgsl_300x/meg004)",
    "MGS-M-MOLA-5-MEGDR-L3-V1.0 (files dated 2003-03-31, labels 2006-10-13)", "global", "4 px/deg (~14.8 km)",
    "simple cylindrical 0-360 E, 90 N top; int16 m; radius - 3 396 000 m", LIC_NASA_PDS, ACK_MOLA, 1, "download",
    "Global relief bound (curvature limit) and areoid consistency check.",
    _megdr("meg004", [("megr90n000cb", 2073600), ("megt90n000cb", 2073600), ("mega90n000cb", 2073600),
                      ("megc90n000cb", 2073600)])))

_add(Product(
    "mars_mola_megdr_016", "MOLA MEGDR 16 ppd global: radius, topography, areoid", None,
    "https://pds-geosciences.wustl.edu/missions/mgs/megdr.html", "PDS Geosciences Node (mgsl_300x/meg016)",
    "MGS-M-MOLA-5-MEGDR-L3-V1.0", "global", "16 px/deg (~3.7 km)",
    "simple cylindrical 0-360 E, 90 N top; int16 m", LIC_NASA_PDS, ACK_MOLA, 2, "download",
    "Far-field fill beyond the 128 ppd tile; areoid at 16 ppd.",
    _megdr("meg016", [("megr90n000eb", 33177600), ("megt90n000eb", 33177600), ("mega90n000eb", 33177600)])))

_add(Product(
    "mars_mola_megdr_128_44n000", "MOLA MEGDR 128 ppd tile 0-44 N, 0-90 E (Jezero): radius, topography, shot counts", None,
    "https://pds-geosciences.wustl.edu/missions/mgs/megdr.html", "PDS Geosciences Node (mgsl_300x/meg128)",
    "MGS-M-MOLA-5-MEGDR-L3-V1.0", "0-44 N, 0-90 E", "128 px/deg (~463 m)",
    "simple cylindrical tile; int16 m; radius - 3 396 000 m", LIC_NASA_PDS, ACK_MOLA, 1, "download",
    "Near/far terrain at Jezero; the areoid at 128 ppd is megr - megt + 3 396 000 m (derived, not a product file).",
    _megdr("meg128", [("megr44n000hb", 129761280), ("megt44n000hb", 129761280), ("megc44n000hb", 64880640)])))

_add(Product(
    "mars_ctx_jezero_sci_20m", "Mars 2020 Science Investigation CTX DEM mosaic of Jezero crater, 20 m", None,
    "https://astrogeology.usgs.gov/search/map/mars_2020_science_investigation_ctx_dem_mosaic",
    "USGS Astrogeology (S3 mosaic bucket, mars2020_trn/CTX/ScienceInvestigationMaps_JPL)", "PDS4 v1.0 (2021)",
    "76.997-78.583 E, 17.581-19.290 N", "20 m/px",
    "equirectangular lat_ts 18.4663, sphere 3 396 190 m; float32 m (datum tested in dem.py)", LIC_USGS_MARS, ACK_CTX_SCI, 1,
    "download", "Near field for the Jezero rim site (whole crater).",
    [FileSpec(f"{USGS_TRN}/CTX/ScienceInvestigationMaps_JPL/M20_JezeroCrater_CTXDEM_20m.tif", 90345300,
              "M20_JezeroCrater_CTXDEM_20m.tif"),
     FileSpec(f"{USGS_TRN}/CTX/ScienceInvestigationMaps_JPL/M20_JezeroCrater_CTXDEM_20m.xml", None,
              "M20_JezeroCrater_CTXDEM_20m.xml")]))

_add(Product(
    "mars_ctx_jezero_trn_20m", "Mars 2020 Terrain Relative Navigation CTX DTM mosaic, 20 m (landing-ellipse region)", None,
    "https://astrogeology.usgs.gov/search/map/mars_2020_terrain_relative_navigation_ctx_dtm_mosaic",
    "USGS Astrogeology (S3 mosaic bucket, mars2020_trn/CTX)", "JEZ_ctx_B_soc_008 (2020-07-24)",
    "77.160-77.699 E, 18.211-18.721 N", "20 m/px", "equirectangular lat_ts 0, sphere 3 396 190 m; float32 m",
    LIC_USGS_MARS, ACK_CTX_TRN, 2, "download", "Independent CTX DTM (product member and datum cross-check).",
    [FileSpec(f"{USGS_TRN}/CTX/JEZ_ctx_B_soc_008_DTM_MOLAtopography_DeltaGeoid_20m_Eqc_latTs0_lon0.tif", 9662387,
              "JEZ_ctx_B_soc_008_DTM_MOLAtopography_DeltaGeoid_20m_Eqc_latTs0_lon0.tif"),
     FileSpec(f"{USGS_TRN}/CTX/JEZ_ctx_B_soc_008_DTM_MOLAtopography_DeltaGeoid_20m_Eqc_latTs0_lon0_pds3.lbl", None,
              "JEZ_ctx_B_soc_008_DTM_MOLAtopography_DeltaGeoid_20m_Eqc_latTs0_lon0_pds3.lbl"),
     FileSpec(f"{USGS_TRN}/CTX/JEZ_ctx_B_soc_008_DTM_MOLAtopography_DeltaGeoid_20m_Eqc_latTs0_lon0.xml", None,
              "JEZ_ctx_B_soc_008_DTM_MOLAtopography_DeltaGeoid_20m_Eqc_latTs0_lon0.xml")]))

_add(Product(
    "mars_naif_pck", "NAIF generic PCK pck00011.tpc (IAU 2015 rotation models incl. Mars periodic terms) and pck00010.tpc",
    None, "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/", "NAIF (JPL)", "pck00011 (2022), pck00010 (2011)",
    "all bodies", "-", "text kernels", "NAIF SPICE kernels: public (JPL/NASA).",
    "Acton, C. H. (1996), Ancillary data services of NASA's Navigation and Ancillary Information Facility, PSS 44, 65-70; "
    "Archinal, B. A., et al. (2018), Report of the IAU WGCCRE: 2015, Celest. Mech. Dyn. Astron. 130, 22.", 1, "download",
    "Rotation models for the frame tie (evaluated by science/worlds/pck.py); also the MESSENGER pck00010_msgr_v23.",
    [FileSpec("https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/pck00011.tpc", None, "pck00011.tpc"),
     FileSpec("https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/pck00010.tpc", None, "pck00010.tpc"),
     FileSpec("https://naif.jpl.nasa.gov/pub/naif/pds/data/mess-e_v_h-spice-6-v1.0/messsp_1000/data/pck/"
              "pck00010_msgr_v23.tpc", None, "pck00010_msgr_v23.tpc")]))

# Catalogued, not downloaded
_add(Product(
    "mars_hirise_jezero_trn_1m", "Mars 2020 TRN HiRISE DTM mosaic tiles, 1 m (C, CR_NORTH, CR_SOUTH, DL, E, N, W)", None,
    "https://astrogeology.usgs.gov/search/map/mars_2020_terrain_relative_navigation_hirise_dtm_mosaic",
    "USGS Astrogeology (S3 mosaic bucket, mars2020_trn/HiRISE)", "2020", "Jezero landing ellipse (crater floor, delta)",
    "1 m/px", "equirectangular, sphere 3 396 190 m", LIC_USGS_MARS, ACK_CTX_TRN, 0, "not-downloaded",
    "7 tiles, 72-132 MB each (757 MB). They cover the landing ellipse on the crater floor, not the rim site, so they cannot "
    "change the rim skyline beyond what the 20 m CTX DEM resolves at > 5 km; next step for a floor site."))
_add(Product(
    "mars_mola_megdr_128_rest", "MOLA MEGDR 128 ppd: the other 15 tiles x 3 layers", None,
    "https://pds-geosciences.wustl.edu/missions/mgs/megdr.html", "PDS Geosciences Node", "-", "88 S - 88 N", "463 m",
    "-", LIC_NASA_PDS, ACK_MOLA, 0, "not-downloaded", "4.9 GB; only the Jezero tile is needed; any other site fetches its own tile."))


def download_plan() -> List[Product]:
    return sorted([p for p in PRODUCTS.values() if p.status == "download" and p.priority > 0],
                  key=lambda p: (p.priority, p.product_id))


def get(product_id: str) -> Product:
    return PRODUCTS[product_id]
