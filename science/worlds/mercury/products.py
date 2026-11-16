"""Mercury data catalogue (R6, prompt §3.2). Same `Product`/`FileSpec` records as tools/globe/products.py, so the S2 fetcher
(tools.globe.fetch.fetch_product) downloads them unchanged and appends the same manifest lines to
$POLARIS_DATA/v2/manifest.jsonl; files land under $POLARIS_DATA/v2/products/mercury_*/.

Byte counts are what the archives' own listings reported on 2026-11-16 (PDS Geosciences directory listings, the USGS
Astrogeology S3 bucket listing, the Zenodo record API, HTTP Content-Length for PGDA). Every source is public, no login.

Datums read from the labels (do not assume one radius for every product):
  * MLA GDR v2 hdem_75n_250m: HEIGHT = DN * 0.5 m relative to OFFSET 2 440 000 m; projection sphere 2 439.4 km.
  * MLA GDR v1 hdem_*: same team format, OFFSET read from each label (msgr_dem_mla_np_v01: 2 439 400 m).
  * USGS DEM 665 m v2: ISIS mapping on a 2 439 400 m sphere; DN * 0.5 m.
  * PGDA 88 south-pole DEM: file name says ref 2439.4 km.
  * PGDA 85 Prokofiev stack: DEM in km (readme); reference radius from the ISIS label.

Import-safe: no network, no third-party packages.
"""
from __future__ import annotations

from typing import Dict, List

from tools.globe.products import LIC_NASA_PDS, FileSpec, Product

LISTED_UTC = "2026-11-16"

PDS_MLA_V2 = "https://pds-geosciences.wustl.edu/messenger/mess-e_v_h-mla-3_4-cdr_rdr-data-v2/messmla_2101/gdr"
PDS_MLA_V1 = "https://pds-geosciences.wustl.edu/messenger/mess-e_v_h-mla-3_4-cdr_rdr-data-v1/messmla_2001/gdr"
USGS = "https://asc-pds-services.s3.us-west-2.amazonaws.com/mosaic"   # planetarymaps.usgs.gov/mosaic/ redirects here
PGDA = "https://pgda.gsfc.nasa.gov/data"
ZENODO_SP = "https://zenodo.org/records/19740142/files"

LIC_USGS_MERCURY = ("USGS Astrogeology Science Center distribution of NASA MESSENGER products: U.S. Government work / public "
                    "domain in the U.S.; MESSENGER data credit NASA/Johns Hopkins University Applied Physics Laboratory/"
                    "Carnegie Institution of Washington.")
LIC_PGDA = ("NASA Goddard PGDA public data product (U.S. Government work); the product page asks users to cite the "
            "reference given in the acknowledgement.")
LIC_CC_BY = "Creative Commons Attribution 4.0 International (CC-BY-4.0), Zenodo record 10.5281/zenodo.19740142."

ACK_MLA = ("MESSENGER Mercury Laser Altimeter gridded data records, PDS data sets MESS-E/V/H-MLA-4-GDR-V2.0 and -V1.0 "
           "(MESSENGER MLA team, D. E. Smith, NASA GSFC), NASA Planetary Data System Geosciences Node. Zuber, M. T., et al. "
           "(2012), Topography of the northern hemisphere of Mercury from MESSENGER laser altimetry, Science 336, 217-220. "
           "MESSENGER: NASA/JHU APL/Carnegie Institution of Washington.")
ACK_USGS_DEM = ("Becker, K. J., Robinson, M. S., Becker, T. L., Weller, L. A., Edmundson, K. L., Neumann, G. A., Perry, M. E., "
                "Solomon, S. C. (2016), First global digital elevation model of Mercury, LPSC XLVII, abstract 2959. USGS "
                "Astrogeology Science Center; MESSENGER data NASA/JHU APL/Carnegie Institution of Washington.")
ACK_MDIS = ("MESSENGER MDIS basemap mosaics (PDS MESS-H-MDIS-5-RDR-BDR-V1.0 and related), NASA/JHU APL/Carnegie Institution "
            "of Washington; Denevi, B. W., et al. (2018), Calibration, projection, and final image products of MESSENGER's "
            "Mercury Dual Imaging System, Space Sci. Rev. 214, 2. Distributed by USGS Astrogeology Science Center.")
ACK_PGDA85 = ("Barker, M. K., Chabot, N. L., Mazarico, E., Siegler, M., Martinez-Camacho, J. M., Hamill, C., Bertone, S. "
              "(2022), New Constraints on the Volatile Deposit in Mercury's North Polar Crater, Prokofiev, PSJ 3, 188 "
              "(citation requested on NASA PGDA product 85). Radar layer from Arecibo data of Harmon et al. (2011), "
              "Icarus 211, 37-50, as resampled in that product.")
ACK_PGDA88 = ("Bertone, S., Mazarico, E., Barker, M. K., Siegler, M. A., Martinez Camacho, J. M., Hamill, C. D., "
              "Glatzenberg, A. K., Chabot, N. L. (2026), Supplementary material to: Highly resolved topography and "
              "illumination at Mercury south pole from MESSENGER MDIS-NAC, v1.1.0, Zenodo, "
              "https://doi.org/10.5281/zenodo.19740142 (NASA PGDA product 88).")
ACK_PGDA64 = ("Deutsch, A. N., Neumann, G. A., Head, J. W. (2017), New evidence for surface water ice in small-scale cold "
              "traps and in three large craters at the north polar region of Mercury from the Mercury Laser Altimeter, "
              "GRL 44 (citation requested on NASA PGDA product 64, G. A. Neumann).")


def _pds3(base: str, sub: str, names: List[tuple]) -> List[FileSpec]:
    """PDS Geosciences MLA GDR image files with their detached PDS3 .lbl and PDS4 .xml labels (sizes from the listing)."""
    out: List[FileSpec] = []
    for name, size, lbl, xml in names:
        out.append(FileSpec(f"{base}/{sub}/{name}.img", size, f"{sub}/{name}.img"))
        out.append(FileSpec(f"{base}/{sub}/{name}.lbl", lbl, f"{sub}/{name}.lbl"))
        out.append(FileSpec(f"{base}/{sub}/{name}.xml", xml, f"{sub}/{name}.xml"))
    return out


def _usgs(names: List[tuple]) -> List[FileSpec]:
    out: List[FileSpec] = []
    for name, size, md5 in names:
        out.append(FileSpec(f"{USGS}/{name}", size, name, md5_url=f"{USGS}/{name}.md5" if md5 else None))
    return out


PRODUCTS: Dict[str, Product] = {}


def _add(p: Product) -> None:
    PRODUCTS[p.product_id] = p


_add(Product(
    "mercury_mla_gdr_v2", "MESSENGER MLA GDR v2: north-polar DEM 75-90 N, 250 m/px (hdem_75n_250m)", None,
    "https://pds-geosciences.wustl.edu/missions/messenger/mla.htm", "PDS Geosciences Node (messmla_2101)",
    "MESS-E/V/H-MLA-4-GDR-V2.0, product V1.0 created 2017-03-01 (MLA data through orbit year 4)",
    "75-90 N", "250 m/px", "polar stereographic on a 2 439.4 km sphere (true at pole); heights m above 2 440.0 km (OFFSET)",
    LIC_NASA_PDS, ACK_MLA, 1, "download",
    "No MISSING_CONSTANT: GMT 'surface' interpolates between tracks, so every pixel has a value; the v1 shot-count grids "
    "(hdec_*) are the only record of which pixels hold data.",
    _pds3(PDS_MLA_V2, "img", [("hdem_75n_250m", 52428800, 4503, 10721)])))

_add(Product(
    "mercury_mla_gdr_v1", "MESSENGER MLA GDR v1: north DEMs 250/500/1000 m, 64/16 ppd global, NP DEM v01, shot counts", None,
    "https://pds-geosciences.wustl.edu/missions/messenger/mla.htm", "PDS Geosciences Node (messmla_2001)",
    "MESS-E/V/H-MLA-4-GDR-V1.0 (files dated 2016-04-22)",
    "45-90 N (polar), global (cylindrical; MLA data only in the north)", "250 m - 16 ppd",
    "polar stereographic / simple cylindrical; heights relative to the OFFSET in each label",
    LIC_NASA_PDS, ACK_MLA, 2, "download", "",
    _pds3(PDS_MLA_V1, "img", [
        ("hdem_45n_1000m", 33554432, 4488, 10728), ("hdem_45n_500m", 134217728, 4485, 10722),
        ("hdem_45n_250m", 536870912, 4490, 10724), ("hdem_64", 318504960, 4623, 10862), ("hdem_16", 19906560, 4613, 10321),
        ("msgr_dem_mla_np_v01", 46080000, 4732, 11006), ("msgr_dem_mla_np_count_v01", 46080000, 3857, 9915),
        ("hdec_45n_250m", 536870912, 3840, 9869), ("hdec_64", 318504960, 3750, 9764)])))

_add(Product(
    "mercury_usgs_dem_665m_v2", "USGS MESSENGER global DEM 665 m v2 (MDIS stereo, Becker et al. 2016)", None,
    "https://astrogeology.usgs.gov/search/map/mercury_messenger_global_dem_665m", "USGS Astrogeology (S3 mosaic bucket)",
    "v2 (bucket object dated 2022-11-10)", "global", "665 m/px (64 ppd)",
    "equirectangular, 0-360 E, sphere 2 439 400 m; int16 DN * 0.5 m", LIC_USGS_MERCURY, ACK_USGS_DEM, 3, "download", "",
    _usgs([("Mercury_Messenger_USGS_DEM_Global_665m_v2.tif", 530934581, True),
           ("Mercury_Messenger_USGS_DEM_Global_665m_v2.lbl", 1317, False),
           ("Mercury_Messenger_USGS_DEM_Global_665m_v2_pds3.lbl", 2145, False)])))

_add(Product(
    "mercury_pgda85_prokofiev", "PGDA 85: Prokofiev hybrid MLA+SfS DEM 125 m with illumination, thermal, ice and radar layers",
    None, "https://pgda.gsfc.nasa.gov/products/85", "NASA GSFC PGDA", "as posted (Barker et al. 2022)",
    "83.5-87 N, 40-83 E", "125 m/px", "polar stereographic (ISIS label); DEM band in km", LIC_PGDA, ACK_PGDA85, 1, "download",
    "Band 12 'radar3b' = Arecibo radar reflectance resampled to 125 m: the only public georeferenced radar-bright raster found.",
    [FileSpec(f"{PGDA}/Barker_Prokofiev/Barker_Prokofiev_stack_125mpp.cub", 55545856, "Barker_Prokofiev_stack_125mpp.cub"),
     FileSpec(f"{PGDA}/Barker_Prokofiev/Barker_Prokofiev_raw.zip", 43044279, "Barker_Prokofiev_raw.zip"),
     FileSpec(f"{PGDA}/Barker_Prokofiev/Barker_Prokofiev_stack_125mpp_readme.pdf", None,
              "Barker_Prokofiev_stack_125mpp_readme.pdf")]))

_add(Product(
    "mercury_pgda88_south_pole", "PGDA 88: Mercury south-polar SfS DEM 250 m, PSR mask, slope (Zenodo v1.1.0)", None,
    "https://pgda.gsfc.nasa.gov/products/88", "Zenodo 10.5281/zenodo.19740142", "v1.1.0 (2026-04-24)",
    "75-90 S", "250 m/px", "polar stereographic; heights relative to 2 439.4 km (file names)", LIC_CC_BY, ACK_PGDA88, 4,
    "download", "Zenodo md5: DEM 8d5f9f89..., filled 668b8446..., mask 7de9a86b..., slope 5f7f120d..., minus_USGS 5fe5bce0...",
    [FileSpec(f"{ZENODO_SP}/{n}?download=1", s, n) for n, s in [
        ("HDEM_75S250M_ref2439p4km.tif", 125070336), ("HDEM_75S250M_ref2439p4km_filled.tif", 127807485),
        ("HDEM_75S250M_mask.tif", 118071), ("HSLP_75S250M_ref2439p4km.tif", 155628078),
        ("HDEM_75S250M_minus_USGS.tif", 148618035)]]))

_add(Product(
    "mercury_mdis_polar_250m", "MDIS polar mosaics 250 m (north and south, 2013)", None,
    "https://astrogeology.usgs.gov/search?target=mercury", "USGS Astrogeology (S3 mosaic bucket)", "2013 release",
    "polar caps", "250 m/px", "ISIS cubes", LIC_USGS_MERCURY, ACK_MDIS, 5, "download", "VISUAL only.",
    _usgs([("Mercury_MESSENGER_mosaic_npole_250m_2013.cub", 74980795, True),
           ("Mercury_MESSENGER_mosaic_spole_250m_2013.cub", 74980799, True)])))

_add(Product(
    "mercury_mdis_bdr_166m", "MDIS BDR global monochrome basemap 166 m (256 ppd)", None,
    "https://astrogeology.usgs.gov/search/map/mercury_messenger_mdis_basemap_bdr_mosaic_global_166m",
    "USGS Astrogeology (S3 mosaic bucket)", "MDIS_BDR_256PPD_GLOBAL_8BIT v1 (bucket object 2022-11-10)", "global", "166 m/px",
    "simple cylindrical -180..180, sphere 2 439 400 m; uint8", LIC_USGS_MERCURY, ACK_MDIS, 6, "download",
    "VISUAL albedo for Blender/R3 (not used by the solver).",
    _usgs([("Mercury_MESSENGER_MDIS_Basemap_BDR_Mosaic_Global_166m.tif", 4247470901, True),
           ("Mercury_MESSENGER_MDIS_Basemap_BDR_Mosaic_Global_166m.lbl", 1853, False),
           ("Mercury_MESSENGER_MDIS_Basemap_BDR_Mosaic_Global_166m_pds3.lbl", 2706, False)])))

_add(Product(
    "mercury_mdis_color_665m", "MDIS enhanced-colour global basemap 665 m", None,
    "https://astrogeology.usgs.gov/search?target=mercury", "USGS Astrogeology (S3 mosaic bucket)", "bucket object 2022-11-10",
    "global", "665 m/px", "simple cylindrical", LIC_USGS_MERCURY, ACK_MDIS, 7, "download", "VISUAL only.",
    _usgs([("Mercury_MESSENGER_MDIS_Basemap_EnhancedColor_Mosaic_Global_665m.tif", 796539539, True),
           ("Mercury_MESSENGER_MDIS_Basemap_EnhancedColor_Mosaic_Global_665m.lbl", 1921, False)])))

_add(Product(
    "mercury_mla_radr_v4", "PGDA 64: recalibrated MLA reflectance (RADR v4)", None, "https://pgda.gsfc.nasa.gov/products/64",
    "NASA GSFC PGDA", "RADR v4", "north polar region (tracks)", "track data", "MLA RDR geometry", LIC_PGDA, ACK_PGDA64, 8,
    "download", "1064 nm reflectance context for the ice layer; not used by the solver.",
    [FileSpec(f"{PGDA}/MLA/RADR_V4.zip", 600721740, "RADR_V4.zip")]))

# Catalogued, not downloaded
_add(Product(
    "mercury_mdis_loi_166m", "MDIS LOI global basemap 166 m", None, "https://astrogeology.usgs.gov/search?target=mercury",
    "USGS Astrogeology", "2022-11-10", "global", "166 m/px", "simple cylindrical", LIC_USGS_MERCURY, ACK_MDIS, 0,
    "not-downloaded", "4.25 GB; same use as the BDR basemap (VISUAL); not needed for any computed number."))
_add(Product(
    "mercury_radar_bright_global", "Global georeferenced radar-bright polar deposit map (Arecibo, Harmon et al. 2011)", None,
    "https://photojournal.jpl.nasa.gov/catalog/PIA16514", "none found", "-", "both poles", "~1.5 km", "-", "-", "-", 0,
    "not-downloaded",
    "Searched 2026-11-16 (PDS Geosciences, PGDA, USGS bucket, web): only figure images (e.g. PIA16514) are public, "
    "not data. Not digitised from figures. The ice layer is the PGDA 85 Prokofiev radar band only."))


def download_plan() -> List[Product]:
    return sorted([p for p in PRODUCTS.values() if p.status == "download" and p.priority > 0],
                  key=lambda p: (p.priority, p.product_id))


def get(product_id: str) -> Product:
    return PRODUCTS[product_id]


def product_dir(root: str, product_id: str) -> str:
    import os
    return os.path.join(root, "v2", "products", product_id)
