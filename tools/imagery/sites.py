"""The four current POLARIS sites (the Decision Lab's sites) for the imagery catalogue.

Coordinates are copied from research/long_features/code/sites.py ``R`` (PGDA product 78 ROI
polygon-vertex centroids; Site04 RoI 3 and Site01 RoI 6 equal science/sites.py). They are
SOURCE-BASED, UNVALIDATED against an independent site list. ``terrain`` is a site-level
descriptor taken from the site name, not a per-pixel terrain classification.
"""

SITES = {
    'site04_roi3': {'name': 'Shackleton rim, Site04 RoI 3', 'lat': -89.78012, 'lon': -156.32023,
                    'terrain': 'crater_rim'},
    'site01_roi6': {'name': 'Connecting Ridge, Site01 RoI 6', 'lat': -89.47409, 'lon': -137.3813,
                    'terrain': 'ridge'},
    'site07_roi1': {'name': 'Peak near Shackleton, Site07 RoI 1', 'lat': -88.8063, 'lon': 123.54887,
                    'terrain': 'massif_peak'},
    'site11_roi4': {'name': 'de Gerlache rim, Site11 RoI 4', 'lat': -88.70606, 'lon': -68.52994,
                    'terrain': 'crater_rim'},
}
SITE_ORDER = list(SITES)
COORD_SOURCE = 'research/long_features/code/sites.py R (PGDA 78 ROI centroids, Barker et al. 2021)'
BOX_HALF_M = 5_000.0  # 10 km x 10 km square in the south-polar stereographic grid

# NASA's current Artemis III candidate landing regions (28 Oct 2024 NASA release; restated by
# George, Rubio, Lawrence & Curell, LPSC 57 (2026) abstract 1901). No official numeric
# coordinates or outlines were found, so these are NOT queried (no boxes are invented).
ARTEMIS_III_REGIONS_2024 = ['Peak near Cabeus B', 'Haworth', 'Malapert Massif', 'Mons Mouton Plateau',
                            'Mons Mouton', 'Nobile Rim 1', 'Nobile Rim 2', 'de Gerlache Rim 2', 'Slater Plain']
