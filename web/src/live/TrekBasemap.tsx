// NASA Moon Trek WMTS basemap: DISPLAY ONLY. Imagery context around the site; never used as terrain,
// never feeds a result. Registration to the bundle grid is assumed (both south-polar stereographic,
// R = 1737.4 km) and NOT validated.
// Layer + tile matrix read from the layer's WMTSCapabilities.xml (TileMatrixSet default028mm):
//   level-0 ScaleDenominator 3.0578404017857101E+07, TopLeftCorner (-1095930, 1095930), 256 px tiles.

export const TREK_LAYER = 'LRO_NAC_AvgMosaic_SPole855_1mp';
const TREK_BASE = `https://trek.nasa.gov/tiles/Moon/SP/${TREK_LAYER}/1.0.0//default/default028mm`;
const SD0 = 3.0578404017857101e7;
const X0 = -1095930;
const Y0 = 1095930;
const TILE = 256;

export const trekResolution = (z: number) => (SD0 * 0.00028) / 2 ** z; // m per px

export function trekTileOf(x: number, y: number, z: number) {
  const span = TILE * trekResolution(z);
  const fc = (x - X0) / span;
  const fr = (Y0 - y) / span;
  return { row: Math.floor(fr), col: Math.floor(fc), fx: fc - Math.floor(fc), fy: fr - Math.floor(fr) };
}

export const trekTileUrl = (z: number, row: number, col: number) => `${TREK_BASE}/${z}/${row}/${col}.png`;

/** 3x3 tiles centred on the tile holding (x, y) in polar-stereographic metres, site marked with a ring. */
export function TrekBasemap({ x, y, z = 11, label }: { x: number; y: number; z?: number; label: string }) {
  const { row, col, fx, fy } = trekTileOf(x, y, z);
  const size = 3 * TILE;
  const scale = 300 / size;
  const span = 3 * TILE * trekResolution(z);
  const cells = [];
  for (let dr = -1; dr <= 1; dr++)
    for (let dc = -1; dc <= 1; dc++)
      cells.push(
        <img
          key={`${dr},${dc}`}
          src={trekTileUrl(z, row + dr, col + dc)}
          alt=""
          width={TILE * scale}
          height={TILE * scale}
          style={{ position: 'absolute', left: (dc + 1) * TILE * scale, top: (dr + 1) * TILE * scale }}
        />,
      );
  return (
    <figure style={{ margin: '8px 0 0' }} aria-label={`Moon Trek basemap around ${label}, display only`}>
      <div style={{ position: 'relative', width: 300, height: 300, overflow: 'hidden', background: '#000' }}>
        {cells}
        <div
          data-testid="trek-site"
          style={{ position: 'absolute', width: 12, height: 12, marginLeft: -6, marginTop: -6, borderRadius: '50%',
            border: '2px solid #ffcc33', left: (TILE + fx * TILE) * scale, top: (TILE + fy * TILE) * scale }}
        />
      </div>
      <figcaption style={{ fontSize: 11, opacity: 0.75 }}>
        NASA Moon Trek WMTS · {TREK_LAYER} · ~{(span / 1000).toFixed(1)} km across · display only, registration unvalidated
      </figcaption>
    </figure>
  );
}
