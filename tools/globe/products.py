"""POLARIS X v2 whole-Moon terrain catalogue (S2, prompt section 2.1 and data rules section 0.4).

Every product in the section 2.1 table has an entry here, including those that are NOT downloaded (with the reason).
File lists are exact archive paths with the byte counts the archive's own directory listing reported on
2026-11-16 (UTC 07:00-08:00); `tools/globe/fetch.py --check` re-verifies them with HEAD requests before downloading.

Nothing here is validated science: these are inputs. Labels, datums and frames are recorded so the pyramid (S3)
can convert them, and each conversion must carry its own test there.

Import-safe: no network, no third-party packages.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

LISTED_UTC = "2026-11-16"  # date the directory listings below were read

# ---- archive roots ------------------------------------------------------------------------------------------------
PDS_LOLA = "https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx"
IMBRIUM = "http://imbrium.mit.edu"  # LOLA science team PDS data node (MIT); linked from the PGDA pages
USGS_MOSAIC = "https://asc-pds-services.s3.us-west-2.amazonaws.com/mosaic"  # planetarymaps.usgs.gov/mosaic/ redirects here

# ---- licence / acknowledgement wording (exact text the archive or product page asks for, see docs/v2/PRODUCTS.md) --
LIC_NASA_PDS = ("NASA Planetary Data System archive data: U.S. Government work, no copyright restriction in the U.S.; "
                "PDS asks users to cite the data set (bundle DOI) and the producing team.")
ACK_LOLA_RDR = ("Smith, D.E.; Neumann, G.A. (2023). Lunar Reconnaissance Orbiter LOLA Processed Data (RDR) Bundle, "
                "urn:nasa:pds:lro_lola_rdr v1.0. NASA Planetary Data System. https://doi.org/10.17189/tnyt-7007. "
                "LOLA data courtesy of the LRO LOLA Science Team, NASA Goddard Space Flight Center.")
ACK_SLDEM2015 = ("Barker, M. K., Mazarico, E., Neumann, G. A., Zuber, M. T., Haruyama, J., Smith, D. E. \"A new lunar "
                 "digital elevation model from the Lunar Orbiter Laser Altimeter and SELENE Terrain Camera,\" Icarus, "
                 "Volume 273, p. 346-355. http://dx.doi.org/10.1016/j.icarus.2015.07.039 (citation requested on NASA "
                 "PGDA product 54). SELENE/Kaguya Terrain Camera data: JAXA/SELENE.")
ACK_PGDA67 = ("Please cite Barker et al. (2016), Icarus 273, 346-355, http://dx.doi.org/10.1016/j.icarus.2015.07.039 "
              "(citation requested on NASA PGDA product 67, Slope and Azimuth from SLDEM2015, E. Mazarico).")
ACK_PGDA70 = ("Please acknowledge Rosenburg et al. (2011) if you use these data products: Rosenburg, M. A., et al., "
              "\"Global surface slopes and roughness of the Moon from the Lunar Orbiter Laser Altimeter\", 2011, JGR, "
              "116, E2 (E02001), http://dx.doi.org/10.1029/2010JE003716 (NASA PGDA product 70).")
LIC_USGS = ("USGS Astrogeology Science Center distribution of a NASA/ASU product: U.S. Government work / public domain in "
            "the U.S.; LROC images: credit NASA/GSFC/Arizona State University.")
ACK_WAC = ("LROC WAC global morphologic mosaic 100 m (June 2013): NASA/GSFC/Arizona State University (LROC Science "
           "Operations Center); distributed by USGS Astrogeology Science Center. Speyerer, E. J., et al. (2011), "
           "LPSC XLII, abstract 2387; Wagner, R. V., et al. (2015), LPSC XLVI, abstract 1473.")


@dataclass(frozen=True)
class FileSpec:
    url: str
    bytes: Optional[int]          # size from the archive listing; None = unknown (filled from Content-Length)
    relpath: str                  # path under $POLARIS_DATA/v2/products/<product_id>/
    md5_url: Optional[str] = None  # archive-published checksum sidecar, if any (USGS .md5)


@dataclass
class Product:
    product_id: str
    title: str
    source_id: Optional[int]      # docs/v2/SOURCE_IDS.json band value; None = not a height layer
    landing_page: str
    archive: str
    product_version: str
    coverage: str
    resolution: str
    datum_frame: str
    licence: str
    acknowledgement: str
    priority: int                 # tonight's download order (1 first); 0 = catalogue only
    status: str                   # "download" | "have" | "not-downloaded"
    reason: str = ""              # why not downloaded / notes
    files: List[FileSpec] = field(default_factory=list)

    @property
    def total_bytes(self) -> int:
        return sum(f.bytes or 0 for f in self.files)


def _pds(sub: str, names: List[Tuple[str, Optional[int]]], labels: Tuple[str, ...] = (".lbl", ".xml")) -> List[FileSpec]:
    """PDS Geosciences LOLA files plus their detached PDS3 (.lbl) and PDS4 (.xml) labels."""
    out: List[FileSpec] = []
    for name, size in names:
        out.append(FileSpec(f"{PDS_LOLA}/{sub}/{name}", size, f"{sub.split('/data/', 1)[-1]}/{name}"))
        stem = name.rsplit(".", 1)[0]
        for ext in labels:
            out.append(FileSpec(f"{PDS_LOLA}/{sub}/{stem}{ext}", None, f"{sub.split('/data/', 1)[-1]}/{stem}{ext}"))
    return out


def _rel(url: str, root: str) -> str:
    return url[len(root):].lstrip("/")


# ---- 1. LOLA global gridded LDEM (cylindrical, float) --------------------------------------------------------------
_GDR_CYL_F = "data/lola_gdr/cylindrical/float_img"
LOLA_GLOBAL = _pds(_GDR_CYL_F, [("ldem_16_float.img", 66355200),
                                ("ldem_64_float.img", 1061683200),
                                ("ldem_128_float.img", 4246732800)])

# ---- 2. LOLA polar LDEMs, finest public polar stereographic product per latitude ring (float) ----------------------
_GDR_POL_F = "data/lola_gdr/polar/float_img"
_POLAR = []
for _hemi in ("s", "n"):
    _POLAR += [(f"ldem_875{_hemi}_5m_float.img", 3681091584),   # |lat| >= 87.5, 5 m
               (f"ldem_85{_hemi}_10m_float.img", 3681091584),   # |lat| >= 85, 10 m
               (f"ldem_80{_hemi}_20m_float.img", 3696640000),   # |lat| >= 80, 20 m
               (f"ldem_75{_hemi}_30m_float.img", 3720024064),   # |lat| >= 75, 30 m
               (f"ldem_60{_hemi}_60m_float.img", 3853926400)]   # |lat| >= 60, 60 m
LOLA_POLAR = _pds(_GDR_POL_F, _POLAR)

# ---- 3a. PGDA 70 slopes + Hurst exponent (LOLA EXTRAS/FRACTAL on the LOLA node) ------------------------------------
_FR = f"{IMBRIUM}/EXTRAS/FRACTAL"
PGDA70 = [FileSpec(f"{_FR}/README_FRACTAL.TXT", 1278, "README_FRACTAL.TXT")]
for _n, _s in (("HE_8", 8294400), ("MAS_57M_16", 33177600), ("MAS_225M_16", 33177600), ("MAS_560M_16", 33177600)):
    PGDA70 += [FileSpec(f"{_FR}/IMG/{_n}.IMG", _s, f"IMG/{_n}.IMG"), FileSpec(f"{_FR}/IMG/{_n}.LBL", None, f"IMG/{_n}.LBL")]

# ---- 3b. LOLA gridded roughness / slope products (PDS LOLA GDR LDRM, LDSM, LDRC) -----------------------------------
_GDR_CYL_I = "data/lola_gdr/cylindrical/img"
_GDR_POL_I = "data/lola_gdr/polar/img"
LOLA_ROUGH = _pds(_GDR_CYL_I, [("ldrm_16.img", 33177600), ("ldsm_16.img", 33177600), ("ldrc_32.img", 132710400),
                               ("ldrm_32_n.img", 132710400), ("ldrm_32_25.img", 132710400),
                               ("ldrm_32_50.img", 132710400), ("ldrm_32_75.img", 132710400)])
LOLA_ROUGH += _pds(_GDR_POL_I, [("ldrm_75s_240m.img", 29062688), ("ldrm_75n_240m.img", 29062688),
                                ("ldsm_75s_240m.img", 29062688), ("ldsm_75n_240m.img", 29062688),
                                ("ldrm_85s_40m.img", 115034112), ("ldrm_85n_40m.img", 115034112),
                                ("ldsm_85s_40m.img", 115034112), ("ldsm_85n_40m.img", 115034112)])

# ---- 4. PGDA 67 SLDEM2015 slope + azimuth (64 ppd global tonight; finer kept in the catalogue) ---------------------
_SL = f"{IMBRIUM}/DATA/SLDEM2015_SLOPE/GLOBAL/FLOAT_IMG"
_AZ = f"{IMBRIUM}/DATA/SLDEM2015_AZIMUTH/GLOBAL/FLOAT_IMG"
PGDA67 = []
for _root, _kind in ((_SL, "SL"), (_AZ, "AZ")):
    _n = f"SLDEM2015_64_{_kind}_90S_90N_000_360"
    PGDA67 += [FileSpec(f"{_root}/{_n}.IMG", 1061683200, _rel(f"{_root}/{_n}.IMG", f"{IMBRIUM}/DATA")),
               FileSpec(f"{_root}/{_n}.LBL", None, _rel(f"{_root}/{_n}.LBL", f"{IMBRIUM}/DATA"))]
PGDA67_128 = []
for _root, _kind in ((_SL, "SL"), (_AZ, "AZ")):
    _n = f"SLDEM2015_128_{_kind}_90S_90N_000_360"
    PGDA67_128 += [FileSpec(f"{_root}/{_n}.IMG", 4246732800, _rel(f"{_root}/{_n}.IMG", f"{IMBRIUM}/DATA")),
                   FileSpec(f"{_root}/{_n}.LBL", None, _rel(f"{_root}/{_n}.LBL", f"{IMBRIUM}/DATA"))]

# ---- 5. SLDEM2015 512 ppd float tiles (32 tiles, 60S-60N) ----------------------------------------------------------
_SLD = "data/sldem2015/tiles/float_img"
_SLD_TILES = []
for _lat in ("00n_30n", "30n_60n", "30s_00s", "60s_30s"):
    for _lon in ("000_045", "045_090", "090_135", "135_180", "180_225", "225_270", "270_315", "315_360"):
        _SLD_TILES.append((f"sldem2015_512_{_lat}_{_lon}_float.img", 1415577600))
SLDEM2015_512 = _pds(_SLD, _SLD_TILES, labels=(".lbl",))
SLDEM2015_512 += _pds("data/sldem2015/global/float_img", [("sldem2015_data_quality_float.img", 172800)], labels=(".lbl",))

# ---- 6. LROC WAC global morphologic mosaic, 100 m (USGS Astrogeology GeoTIFF) --------------------------------------
_W = "Lunar_LRO_LROC-WAC_Mosaic_global_100m_June2013"
WAC_100M = [FileSpec(f"{USGS_MOSAIC}/{_W}.tif", 5959263751, f"{_W}.tif", md5_url=f"{USGS_MOSAIC}/{_W}.tif.md5"),
            FileSpec(f"{USGS_MOSAIC}/{_W}.tif.md5", 85, f"{_W}.tif.md5"),
            FileSpec(f"{USGS_MOSAIC}/{_W}.lbl", 1666, f"{_W}.lbl"),
            FileSpec(f"{USGS_MOSAIC}/{_W}_pds3.lbl", 2545, f"{_W}_pds3.lbl"),
            FileSpec(f"{USGS_MOSAIC}/{_W}.cub.xml", 11058, f"{_W}.cub.xml")]

_LOLA_FRAME = ("LOLA GDR *_FLOAT: PC_REAL float32 HEIGHT in KILOMETRES relative to OFFSET 1737.4 km (label UNIT = "
               "KILOMETER; multiply by 1000 for metres); MOON_ME (mean Earth/polar axis of DE421); east-positive "
               "longitude; see each .lbl for projection offsets and scale")

PRODUCTS: Dict[str, Product] = {}


def _add(p: Product) -> None:
    assert p.product_id not in PRODUCTS, p.product_id
    PRODUCTS[p.product_id] = p


_add(Product("lola_ldem_global", "LOLA gridded global LDEM (cylindrical) 16/64/128 ppd, float", 8,
             f"{PDS_LOLA}/data/lola_gdr/cylindrical/", "PDS Geosciences Node (LOLA RDR bundle urn:nasa:pds:lro_lola_rdr)",
             "LRO-L-LOLA-3-RDR-V1.0 / PDS4 bundle v1.0 (files dated 2017-09-06 to 2019-03-04)", "global",
             "16, 64, 128 ppd (1895, 474, 237 m/px at the equator)", _LOLA_FRAME, LIC_NASA_PDS, ACK_LOLA_RDR,
             1, "download", "", LOLA_GLOBAL))
_add(Product("lola_ldem_polar", "LOLA polar stereographic LDEMs, finest public post per ring (both poles), float", 7,
             f"{PDS_LOLA}/data/lola_gdr/polar/", "PDS Geosciences Node (LOLA RDR bundle)",
             "LRO-L-LOLA-3-RDR-V1.0 (N files 2016-08-31, S files 2017-06-02)", "|lat| >= 60 (rings 60/75/80/85/87.5)",
             "60 m (>=60), 30 m (>=75), 20 m (>=80), 10 m (>=85), 5 m (>=87.5)",
             _LOLA_FRAME + "; polar stereographic on the 1,737,400 m sphere, true scale at the pole",
             LIC_NASA_PDS, ACK_LOLA_RDR, 2, "download",
             "45S/N 100 m and coarser posts of each ring are not downloaded (superseded by the finer post)", LOLA_POLAR))
_add(Product("pgda70_roughness", "PGDA 70 lunar median absolute slope (57/225/560 m baselines) and Hurst exponent", None,
             "https://pgda.gsfc.nasa.gov/products/70", "LOLA node, MIT (imbrium.mit.edu/EXTRAS/FRACTAL)",
             "files dated 2011-05-16 (LOLA data through LRO_NO_13); EXTRAS: unsupported by the LOLA team", "global",
             "MAS 16 ppd, Hurst 8 ppd", "simple cylindrical, MOON_ME", LIC_NASA_PDS, ACK_PGDA70, 3, "download",
             "statistics for VISUAL sub-resolution roughness only (section 2.3)", PGDA70))
_add(Product("lola_roughness_gdr", "LOLA gridded roughness / slope (LDRM, LDSM, LDRC) - the 'LOLA RMHE' maps", None,
             f"{PDS_LOLA}/data/lola_gdr/", "PDS Geosciences Node (LOLA RDR bundle)",
             "LRO-L-LOLA-3-RDR-V1.0 (2012-06 and 2019-09 files)", "global (16/32 ppd) + polar 75/85 rings",
             "16-32 ppd; polar 240 m / 40 m", "see .lbl (int16 with SCALING_FACTOR)", LIC_NASA_PDS, ACK_LOLA_RDR, 3,
             "download", "interpreted as the 'LOLA RMHE' (RMS height) products named in the prompt: LDRM = RMS "
             "roughness (m), LDSM = bidirectional slope (deg), LDRC = roughness count", LOLA_ROUGH))
_add(Product("pgda67_slope_azimuth_64", "PGDA 67 slope and azimuth from SLDEM2015, 64 ppd global", None,
             "https://pgda.gsfc.nasa.gov/products/67", "LOLA node, MIT (imbrium.mit.edu/DATA/SLDEM2015_SLOPE, _AZIMUTH)",
             "files dated 2017-07-10, labels 2018-07-11", "pole to pole", "64 ppd (baseline = pixel)",
             "simple cylindrical, MOON_ME", LIC_NASA_PDS, ACK_PGDA67, 4, "download",
             "128/256/512 ppd versions are catalogued but not fetched tonight (4.2 / 17 / 68 GB per layer)", PGDA67))
_add(Product("sldem2015_512", "SLDEM2015 (LOLA + Kaguya TC) 512 ppd float tiles", 6,
             "https://pgda.gsfc.nasa.gov/products/54", "PDS Geosciences Node (LOLA RDR bundle, sldem2015 collection)",
             "SLDEM2015 (Barker et al. 2016), tiles dated 2015-07-14", "60S-60N", "512 ppd (59.2 m/px at the equator)",
             _LOLA_FRAME, LIC_NASA_PDS, ACK_SLDEM2015, 5, "download", "", SLDEM2015_512))
_add(Product("lroc_wac_100m", "LROC WAC global morphologic mosaic 100 m (June 2013)", None,
             "https://astrogeology.usgs.gov/search/map/moon_lro_lroc_wac_global_morphology_mosaic_100m",
             "USGS Astrogeology (planetarymaps.usgs.gov/mosaic, S3 asc-pds-services)", "June 2013 (USGS copy 2022-11-08)",
             "global", "100 m/px (303.2333 ppd), 8-bit", "simple cylindrical on the 1,737,400 m sphere, east-positive, "
             "longitude domain -180..180", LIC_USGS, ACK_WAC, 6, "download", "albedo/texture: VISUAL only", WAC_100M))
_add(Product("pgda67_slope_azimuth_128", "PGDA 67 slope and azimuth from SLDEM2015, 128 ppd global", None,
             "https://pgda.gsfc.nasa.gov/products/67", "LOLA node, MIT", "files dated 2017-07-10", "pole to pole",
             "128 ppd", "simple cylindrical, MOON_ME", LIC_NASA_PDS, ACK_PGDA67, 7, "download",
             "optional extra if time and budget remain", PGDA67_128))

# ---- catalogue-only entries (section 2.1 rows not downloaded tonight) ----------------------------------------------
_add(Product("pgda90_polar", "PGDA 90 LOLA south polar 20/40/80 m", 5, "https://pgda.gsfc.nasa.gov/products/90",
             "NASA PGDA", "see existing docs/DATA_PROVENANCE.md", "south pole", "20/40/80 m", "polar stereographic",
             LIC_NASA_PDS, "see docs/DATA_PROVENANCE.md", 0, "have",
             "already in the cache (data/external/pgda90, 80 m COG read by range requests)"))
_add(Product("pgda78_sites", "PGDA 78 LOLA 5 m site tiles + clones", 3, "https://pgda.gsfc.nasa.gov/products/78",
             "NASA PGDA", "see existing docs/DATA_PROVENANCE.md", "south-pole sites", "5 m", "polar stereographic",
             LIC_NASA_PDS, "see docs/DATA_PROVENANCE.md", 0, "have", "already in the cache (data/cache/p78, data/external/pgda78)"))
_add(Product("kaguya_tc_dtm", "Kaguya TC DTMs (JAXA SLDEM2013 / TC DTM MAP; USGS ASP TC DTMs)", 4,
             "https://darts.isas.jaxa.jp/planet/pdap/selene/", "JAXA DARTS (SELENE archive); USGS Astrogeology", "see PRODUCTS.md",
             "near-global", "TC ~10 m images; DTMs posted ~7.4 m (TC DTM MAP 4096 ppd) / 35 m (USGS ASP)", "see PRODUCTS.md",
             "JAXA SELENE data policy (see PRODUCTS.md)", "JAXA SELENE wording NOT verified (DARTS rejects scripted requests)", 0,
             "not-downloaded", "~0.8 TB class: stream per tile on demand (section 2.1); not mirrored tonight"))
_add(Product("lroc_nac_dtm", "LROC NAC DTMs (PDS SDNDTM / ASPDTM)", 1, "https://wms.lroc.asu.edu/lroc/rdr_product_select",
             "LROC SOC / PDS Imaging", "see PRODUCTS.md", "hundreds of sites", "2-5 m", "see per-DTM label",
             "NASA/GSFC/Arizona State University", "see PRODUCTS.md", 0, "not-downloaded",
             "per-site on demand (S4 / S6); not bulk-mirrored"))
_add(Product("gsfc_sfs", "GSFC shape-from-shading polar DEMs (Zenodo 10.5281/zenodo.17954508)", 2,
             "https://doi.org/10.5281/zenodo.17954508", "Zenodo", "see PRODUCTS.md", "selected polar regions", "5 m (some finer)",
             "polar stereographic, +proj=stere +lat_0=-90 +lon_0=0 +R=1737400 (per region GeoTIFF)",
             "CC-BY-4.0 (Zenodo record v1.0.0, 2025-12-16)", "Bertone, S., McKenna, T. E., Barker, M. K., Mazarico, E., "
             "Beyer, R. A., Petro, N. (2025), Zenodo, doi:10.5281/zenodo.17954508", 0, "not-downloaded",
             "13 region zips, 26,559,680,857 B total; per-region on demand; region 6 used for display only"))
_add(Product("ch2_tmc2_dem", "Chandrayaan-2 TMC-2 DEMs (ISRO PRADAN)", None, "https://pradan.issdc.gov.in/",
             "ISRO ISSDC PRADAN", "n/a", "partial", "~10 m class", "n/a", "ISRO PRADAN terms (registration)", "n/a", 0,
             "not-downloaded", "not downloaded: needs an account the user has not approved"))
_add(Product("cnsa_change_dem", "CNSA Chang'e DEMs (Lunar and Planetary Data Release System)", None,
             "https://moon.bao.ac.cn/", "CNSA / NAOC GRAS", "n/a", "global/partial", "20-50 m (CE-2)", "n/a",
             "CNSA data release terms (registration)", "n/a", 0, "not-downloaded",
             "not downloaded: needs an account the user has not approved"))
_add(Product("lroc_nac_images", "LROC NAC images", None, "https://wms.lroc.asu.edu/lroc", "LROC SOC / PDS Imaging",
             "n/a", "local", "~0.5-2 m", "n/a", "NASA/GSFC/Arizona State University", "n/a", 0, "not-downloaded",
             "imagery is S6's catalogue (tools/imagery); fetched per scene on demand"))


def download_plan(include_optional: bool = True) -> List[Product]:
    """Products to fetch tonight, in priority order."""
    ps = [p for p in PRODUCTS.values() if p.status == "download" and p.priority > 0]
    if not include_optional:
        ps = [p for p in ps if p.product_id != "pgda67_slope_azimuth_128"]
    return sorted(ps, key=lambda p: p.priority)


def get(product_id: str) -> Product:
    return PRODUCTS[product_id]
