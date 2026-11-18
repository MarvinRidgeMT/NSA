import { useEffect, useId, useRef, useState, type ClipboardEvent, type FormEvent, type ReactNode, type Ref } from 'react';
import { HonestyTag, IconArrow, IconClose } from './parts';
import {
  cellOf,
  fmtDistance,
  fmtLatLon,
  loadSpotManifest,
  lookupCell,
  nearestSite,
  parseLatLon,
  pct1,
  splitPair,
  MATCH_FIELD,
  tileLoader,
  type Around,
  type Coverage,
  type SpotManifest,
  type SpotSite,
  type SpotValues,
  type TileGetter,
} from './spotCheck';

/**
 * S13 "Check a spot" (18 Nov 2026; layout changed the same day): a box centred at the bottom of the globe takes a latitude and
 * longitude, and a click on the Moon drops a point. Either way a marker goes down and a card opens beside it with what the
 * files say there, one source per row and no overall yes or no.
 *
 * Every number shown comes from a file: the site rows from the bundle and the certainty sidecar (passed in by SimpleApp, the
 * same values the pins show), the NASA rows from the PGDA 69 web copy (spotCheck.ts), distances from the two coordinates on
 * the map's sphere. There is no warning threshold: the card always shows the cell's value and the range of the cells around it.
 */
export interface SpotCardSite extends SpotSite {
  /** the 14-day result at this site from the certainty sidecar, as words; null = the sidecar has no rows for it */
  result: { verdict: string; sun: string; both: string | null; mastM: number; variants: number } | null;
  /** why there is no result, when there is none */
  why: string;
}

interface Checked {
  lat: number;
  lon: number;
  /** for a clicked point: radians of Moon under one screen pixel at the click; null for typed coordinates */
  radPerPx: number | null;
  cov: Coverage;
  values: SpotValues | null;
  failed: string | null;
}
export type SpotError = { field: 'lat' | 'lon' | 'both' | 'none'; message: string };

export const IconSpot = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" aria-hidden="true" focusable="false">
    <circle cx="8" cy="8" r="3.25" />
    <path d="M8 1.5v2.5M8 12v2.5M1.5 8H4M12 8h2.5" />
  </svg>
);
const IconZoom = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" aria-hidden="true" focusable="false">
    <circle cx="7" cy="7" r="4.25" />
    <path d="M10.2 10.2l3.3 3.3M7 5.25v3.5M5.25 7h3.5" />
  </svg>
);

/** "6.3–85.2 % within one 60 m cell": the lowest and highest of the cells that touch the point's own cell */
const rangeText = (m: SpotManifest, a: Around) => (a.cells === 0 ? 'no data around it' : `${pct1(m, a.min)}–${pct1(m, a.max)} % within one ${m.grid.cellM} m cell`);
const valueText = (m: SpotManifest, raw: number) => (raw === m.grid.nodata ? 'no data' : `${pct1(m, raw)} %`);

/**
 * The check itself: the two boxes' text, the NASA map copy (fetched on the first use of the box or the first click on the Moon,
 * not before), the lookup in flight and its answer. `onPoint` tells the globe where the marker goes (null = none) and
 * `onAnswer` that a point is being checked, so its card should open.
 */
export function useSpotCheck(onPoint: (p: { lat: number; lon: number } | null) => void, onAnswer: () => void) {
  const [latText, setLatText] = useState('');
  const [lonText, setLonText] = useState('');
  const [error, setError] = useState<SpotError | null>(null);
  const [manifest, setManifest] = useState<SpotManifest | null>(null);
  const [mapFailed, setMapFailed] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState<Checked | null>(null);
  const tiles = useRef<TileGetter | null>(null);
  const loading = useRef<Promise<SpotManifest> | null>(null);
  const run = useRef(0);
  useEffect(() => () => void run.current++, []); // unmounted: a check still in flight is dropped when it returns

  const getManifest = () => {
    loading.current ??= loadSpotManifest().then((m) => {
      tiles.current = tileLoader(m);
      setManifest(m);
      return m;
    });
    return loading.current;
  };
  /** Fetch the map copy's manifest ahead of the first check (called when the box takes focus). */
  const warm = () => {
    getManifest().catch((e: unknown) => {
      loading.current = null;
      setMapFailed(e instanceof Error ? e.message : String(e));
    });
  };
  /** Drop whatever is shown or still loading: no answer, no marker. Every path that clears the answer goes through here. */
  const clear = () => {
    run.current++;
    setBusy(false);
    setRes(null);
    onPoint(null);
  };

  const check = async (lat: number, lon: number, radPerPx: number | null) => {
    const mine = ++run.current;
    setError(null);
    setRes(null);
    onPoint({ lat, lon });
    setBusy(true);
    onAnswer();
    let m: SpotManifest;
    try {
      m = await getManifest();
      setMapFailed(null);
    } catch (e) {
      loading.current = null;
      if (mine !== run.current) return;
      setMapFailed(e instanceof Error ? e.message : String(e));
      clear();
      return;
    }
    const cov = cellOf(m, lat, lon);
    let values: SpotValues | null = null;
    let failed: string | null = null;
    if (cov.kind === 'cell') {
      try {
        values = await lookupCell(m, tiles.current!, cov.row, cov.col);
      } catch (e) {
        failed = `This part of the NASA map copy could not be loaded (${e instanceof Error ? e.message : String(e)}), so no NASA value is shown. Nothing is substituted.`;
      }
    }
    if (mine !== run.current) return; // a newer check, an edit or a close has taken over
    setBusy(false);
    setRes({ lat, lon, radPerPx, cov, values, failed });
  };

  const fail = (p: SpotError) => {
    clear();
    setError(p);
  };
  /** Check what is typed in the boxes. Returns which box is wrong, if one is. */
  const submit = (): 'lat' | 'lon' | null => {
    // "lat, lon" typed (not pasted) into one box, the other left empty: same as a paste
    const pair = !lonText.trim() ? splitPair(latText) : !latText.trim() ? splitPair(lonText) : null;
    if (pair) {
      setLatText(pair[0]);
      setLonText(pair[1]);
    }
    const p = pair ? parseLatLon(pair[0], pair[1]) : parseLatLon(latText, lonText);
    if (!p.ok) {
      fail(p);
      return p.field === 'lon' ? 'lon' : 'lat';
    }
    void check(p.lat, p.lon, null);
    return null;
  };
  /** Pasted text: a "lat, lon" pair fills both boxes and is checked. Returns false when the text is not a pair. */
  const paste = (text: string): boolean => {
    const pair = splitPair(text);
    if (!pair) return false;
    setLatText(pair[0]);
    setLonText(pair[1]);
    const p = parseLatLon(pair[0], pair[1]);
    if (p.ok) void check(p.lat, p.lon, null);
    else fail(p);
    return true;
  };
  /**
   * Editing a box drops the answer on screen and any check still loading: either would be for coordinates that are no longer
   * in the form. The card closes and the marker lifts until Check is pressed again.
   */
  const edit = (which: 'lat' | 'lon', text: string) => {
    if (text === (which === 'lat' ? latText : lonText)) return;
    (which === 'lat' ? setLatText : setLonText)(text);
    if (busy || res) clear();
  };
  /** A click on the Moon: the boxes take the clicked coordinates (four decimals) and that exact text is what gets checked. */
  const drop = (lat: number, lon: number, radPerPx: number) => {
    const a = lat.toFixed(4);
    const b = lon.toFixed(4);
    setLatText(a);
    setLonText(b);
    void check(Number(a), Number(b), radPerPx);
  };
  return { latText, lonText, error, manifest, mapFailed, busy, res, warm, clear, submit, paste, edit, drop };
}
export type SpotCheckState = ReturnType<typeof useSpotCheck>;

/** The box at the bottom of the globe: "Check a spot: latitude, longitude" and a Check button. */
export function SpotBox({ spot, hint, hidden }: { spot: SpotCheckState; hint: ReactNode; hidden?: boolean }) {
  const id = useId();
  const latEl = useRef<HTMLInputElement>(null);
  const lonEl = useRef<HTMLInputElement>(null);
  const { error } = spot;
  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    const bad = spot.submit();
    if (bad) (bad === 'lon' ? lonEl : latEl).current?.focus();
  };
  const onPaste = (e: ClipboardEvent<HTMLInputElement>) => {
    if (spot.paste(e.clipboardData.getData('text'))) e.preventDefault();
  };
  const described = `${id}-help${error ? ` ${id}-err` : ''}`;
  const failed = spot.mapFailed && !spot.manifest;
  return (
    <div className="s-spot-dock" data-testid="spot-dock" hidden={hidden}>
      {hint}
      <form className="s-panel s-spot-box" onSubmit={onSubmit} onFocus={spot.warm} noValidate role="group" aria-labelledby={`${id}-t`} data-testid="spot-box" data-busy={spot.busy || undefined}>
        <span className="s-spot-box-title" id={`${id}-t`}>
          <IconSpot />
          Check a spot
        </span>
        <div className="s-field">
          <label htmlFor={`${id}-lat`}>Latitude</label>
          <input
            id={`${id}-lat`}
            ref={latEl}
            className="s-input s-data"
            data-testid="spot-lat"
            inputMode="text"
            autoComplete="off"
            spellCheck={false}
            placeholder="−89.5"
            value={spot.latText}
            aria-invalid={error?.field === 'lat' || error?.field === 'both' || undefined}
            aria-describedby={described}
            onChange={(e) => spot.edit('lat', e.target.value)}
            onPaste={onPaste}
          />
        </div>
        <div className="s-field">
          <label htmlFor={`${id}-lon`}>Longitude</label>
          <input
            id={`${id}-lon`}
            ref={lonEl}
            className="s-input s-data"
            data-testid="spot-lon"
            inputMode="text"
            autoComplete="off"
            spellCheck={false}
            placeholder="−137.4"
            value={spot.lonText}
            aria-invalid={error?.field === 'lon' || error?.field === 'both' || undefined}
            aria-describedby={described}
            onChange={(e) => spot.edit('lon', e.target.value)}
            onPaste={onPaste}
          />
        </div>
        <button type="submit" className="s-btn s-btn--primary" data-testid="spot-check" aria-busy={spot.busy || undefined}>
          Check
        </button>
        <p className="s-field-help s-spot-help" id={`${id}-help`}>
          Decimal degrees, south and west negative. Pasting “lat, lon” fills both.
        </p>
        {error && (
          <p className="s-field-error s-spot-error" id={`${id}-err`} role="alert" data-testid="spot-error">
            {error.message}
          </p>
        )}
        {failed && (
          <p className="s-field-error s-spot-error" role="alert" data-testid="spot-map-failed">
            The NASA map copy could not be loaded ({spot.mapFailed}), so nothing can be checked right now and nothing is substituted. Press Check to try again.
          </p>
        )}
      </form>
    </div>
  );
}

/**
 * The answer card that opens beside the dropped marker. Three separate rows; then what can be done from here: zoom the globe
 * in on the spot, and fly down to the terrain when the spot is a site we computed.
 */
export function SpotCard({
  spot,
  sites,
  match,
  windowText,
  cardRef,
  onZoom,
  onFly,
  onClose,
}: {
  spot: SpotCheckState;
  sites: SpotCardSite[];
  /** how close counts as "at" a computed site (spotCheck.matchDistanceM) and the bundle file it was read from; null = the bundle does not say */
  match: { stepM: number; withinM: number; file: string } | null;
  /** the window our own results cover, from the bundle's first and last sample */
  windowText: string | null;
  cardRef?: Ref<HTMLElement>;
  onZoom: (lat: number, lon: number) => void;
  /** fly down to this site's terrain */
  onFly: (siteId: string) => void;
  onClose: () => void;
}) {
  const id = useId();
  const { res, manifest: m, busy } = spot;
  const near = res && m ? nearestSite(m.grid.radiusM, sites, res.lat, res.lon) : null;
  const at = near && match && near.distM <= match.withinM ? near : null;
  const v = res?.values ?? null;
  // how coarse a click is: the ground under one screen pixel, on the map's sphere
  const pxKm = res && m && res.radPerPx !== null && res.radPerPx > 0 ? (res.radPerPx * m.grid.radiusM) / 1000 : null;
  const cells = v ? Math.min(v.sun.cells, v.earth.cells) : 0;
  const outside =
    !res || !m || res.failed || res.cov.kind === 'cell'
      ? null
      : res.cov.kind === 'outside-map'
        ? `NASA’s map covers ${Math.abs(m.grid.fullEdgeLatDeg)}° S to the pole. This point is at ${fmtLatLon(res.lat, res.lon).split(',')[0]}, outside it, so there is no NASA value to show.`
        : `This point is on NASA’s map, but this site carries only a square of it centred on the pole, ${((2 * m.copy.halfWidthM) / 1000).toFixed(1)} km on a side in the map’s grid: all of it south of ${Math.abs(m.copy.inscribedLatDeg).toFixed(2)}° S, and further out only toward the square’s corners. No NASA value is shown for it here.`;
  // where the step comes from, named on the card: the field and the loaded bundle's file
  const stepSource = match ? `half the ${fmtDistance(match.stepM)} step between the positions we computed (${MATCH_FIELD} in ${match.file})` : '';
  const terrainOnly = `Ground-level terrain exists only for the ${sites.length} sites we computed; this spot is not one of them.`;

  // one sentence for screen readers, said when a check finishes
  const spoken =
    !res || !m || busy
      ? ''
      : [
          `Checked ${fmtLatLon(res.lat, res.lon)}.`,
          at
            ? `Our results: ${fmtDistance(at.distM)} from ${at.site.name}. ${at.site.result ? `${at.site.result.verdict}. Sun in sight ${at.site.result.sun} at a ${at.site.result.mastM} metre mast.` : at.site.why}`
            : near
              ? `Our results: none for this spot. The nearest site we computed is ${near.site.name}, ${fmtDistance(near.distM)} away.`
              : 'Our results: none.',
          v ? `NASA long-term average: Sun ${valueText(m, v.sun.raw)} here, ${rangeText(m, v.sun)}. Earth ${valueText(m, v.earth.raw)} here, ${rangeText(m, v.earth)}.` : `NASA long-term average: ${res.failed ?? outside ?? ''}`,
          'Slope: not yet available.',
          at ? '' : terrainOnly,
        ]
          .filter(Boolean)
          .join(' ');

  return (
    <section className="s-panel s-gcard s-spot" ref={cardRef} aria-labelledby={`${id}-h`} data-testid="spot-card" data-busy={busy || undefined}>
      <div className="s-gcard-head">
        <h2 className="s-gcard-title" id={`${id}-h`}>
          Checked spot
        </h2>
        <button type="button" className="s-btn s-btn--sm s-btn--icon s-btn--quiet" aria-label="Close this card" data-testid="spot-close" onClick={onClose}>
          <IconClose />
        </button>
      </div>
      <p className="sr-only" role="status" data-testid="spot-spoken">
        {busy ? 'Checking…' : spoken}
      </p>
      {(!res || !m) && (
        <p className="s-spot-none" data-testid="spot-loading">
          Looking this spot up…
        </p>
      )}

      {res && m && (
        <div className="s-spot-answer" data-testid="spot-answer" data-lat={res.lat} data-lon={res.lon} data-coverage={res.failed ? 'failed' : res.cov.kind} data-row={v?.row} data-col={v?.col} data-sun-raw={v?.sun.raw} data-earth-raw={v?.earth.raw}>
          <p className="s-spot-point" data-testid="spot-point">
            <IconSpot />
            <span>
              <b>{fmtLatLon(res.lat, res.lon)}</b>
              {pxKm !== null && (
                <span className="s-spot-fine">
                  Placed by a click. At this zoom one screen pixel covers about {pxKm >= 1 ? pxKm.toFixed(1) : pxKm.toFixed(2)} km, so type the coordinates for an exact spot.
                </span>
              )}
            </span>
          </p>

          {/* ---- row 1: our own results ---- */}
          <section className="s-spot-row" aria-labelledby={`${id}-ours`} data-testid="spot-ours" data-match={at ? at.site.id : 'none'}>
            <h3 id={`${id}-ours`}>Our results</h3>
            <p className="s-spot-src">
              Our own calculation{windowText ? ` for ${windowText}` : ''}. Single sites only.
            </p>
            {at ? (
              <>
                <dl className="s-facts">
                  <div className="s-fact">
                    <dt>Nearest site</dt>
                    <dd>
                      <span className="s-spot-site" data-testid="spot-ours-site">
                        {at.site.name}
                      </span>
                      <span className="s-fact-sub" data-testid="spot-ours-distance">
                        {fmtDistance(at.distM)} from your point
                      </span>
                    </dd>
                  </div>
                  {at.site.result ? (
                    <>
                      <div className="s-fact" data-tone="sun">
                        <dt>
                          Sun in sight
                          <span className="s-fact-hint">{at.site.result.verdict}</span>
                        </dt>
                        <dd>
                          <span className="s-fact-value" data-testid="spot-ours-sun">
                            {at.site.result.sun}
                          </span>
                          <span className="s-fact-sub" data-testid="spot-ours-mast">
                            {at.site.result.mastM} m mast · {at.site.result.variants} terrain variants
                          </span>
                        </dd>
                      </div>
                      {at.site.result.both && (
                        <div className="s-fact" data-tone="earth">
                          <dt>Sun + Earth together</dt>
                          <dd>
                            <span className="s-fact-value" data-testid="spot-ours-both">
                              {at.site.result.both}
                            </span>
                            <span className="s-fact-sub">{at.site.result.mastM} m mast</span>
                          </dd>
                        </div>
                      )}
                    </>
                  ) : (
                    <div className="s-fact">
                      <dt>14-day result</dt>
                      <dd>
                        <span className="s-fact-sub" data-testid="spot-ours-none">
                          {at.site.why}
                        </span>
                      </dd>
                    </div>
                  )}
                </dl>
                <p className="s-spot-fine">
                  The site’s own result, not your point’s. Shown within {fmtDistance(match!.withinM)} of a site: {stepSource}. Line of sight to the disc centre, not power or communications.
                </p>
                {at.site.result && <HonestyTag href="?mode=expert#evidence" />}
              </>
            ) : (
              <p className="s-spot-none" data-testid="spot-ours-none">
                {near
                  ? match
                    ? `None for this spot. The nearest site we computed is ${near.site.name}, ${fmtDistance(near.distM)} away; a site’s result is shown only within ${fmtDistance(match.withinM)} of it: ${stepSource}.`
                    : `None for this spot. The nearest site we computed is ${near.site.name}, ${fmtDistance(near.distM)} away, and the loaded bundle does not say how far a site’s result may be carried.`
                  : 'None: no computed sites are loaded.'}
              </p>
            )}
          </section>

          {/* ---- row 2: NASA's long-term average ---- */}
          <section className="s-spot-row" aria-labelledby={`${id}-nasa`} data-testid="spot-nasa">
            <h3 id={`${id}-nasa`}>NASA long-term average</h3>
            <p className="s-spot-src" data-testid="spot-nasa-label">
              18.6-year average (NASA PGDA 69, Mazarico et al. 2011), not our 14-day window.
            </p>
            {v ? (
              <>
                <dl className="s-facts">
                  <div className="s-fact" data-tone="sun">
                    <dt>
                      Sun
                      <span className="s-fact-hint">{m.meaning.sunShort}</span>
                    </dt>
                    <dd>
                      <span className="s-fact-value">
                        <span data-testid="spot-nasa-sun">{valueText(m, v.sun.raw)}</span>
                        <span className="s-spot-here"> here</span>
                      </span>
                      <span className="s-fact-sub" data-testid="spot-nasa-sun-range">
                        {rangeText(m, v.sun)}
                      </span>
                    </dd>
                  </div>
                  <div className="s-fact" data-tone="earth">
                    <dt>
                      Earth
                      <span className="s-fact-hint">{m.meaning.earthShort}</span>
                    </dt>
                    <dd>
                      <span className="s-fact-value">
                        <span data-testid="spot-nasa-earth">{valueText(m, v.earth.raw)}</span>
                        <span className="s-spot-here"> here</span>
                      </span>
                      <span className="s-fact-sub" data-testid="spot-nasa-earth-range">
                        {rangeText(m, v.earth)}
                      </span>
                    </dd>
                  </div>
                </dl>
                <p className="s-spot-fine">
                  “Here” is the {m.grid.cellM} m cell that holds your point; the range is the lowest and highest of the {cells === 9 ? '3 × 3 cells' : `${cells} cells`} around it{cells === 9 ? '' : ' (the rest lie outside this site’s copy of the map)'}, so a move of one cell can change the answer that much. NASA’s values as published, {m.meaning.basis}: not checked by us, and not for a mast height.
                </p>
                <span className="s-honesty">NASA REFERENCE DATA</span>
              </>
            ) : (
              <p className="s-spot-none" data-testid="spot-nasa-none">
                {res.failed ?? outside}
              </p>
            )}
          </section>

          {/* ---- row 3: slope ---- */}
          <section className="s-spot-row" aria-labelledby={`${id}-slope`} data-testid="spot-slope">
            <h3 id={`${id}-slope`}>Slope</h3>
            <p className="s-spot-none">Not yet available. It needs a slope map made from the same terrain data, which is not in the files yet.</p>
          </section>

          {/* ---- what can be done from here: always in reach at the foot of the card ---- */}
          <div className="s-spot-foot">
            {!at && (
              <p className="s-spot-fine" data-testid="spot-terrain-note">
                {terrainOnly}
              </p>
            )}
            <div className="s-gcard-actions">
              <button type="button" className="s-btn s-btn--sm" data-testid="spot-zoom" onClick={() => onZoom(res.lat, res.lon)}>
                <IconZoom />
                Zoom in here
              </button>
              {at && (
                <button type="button" className="s-btn s-btn--sm s-btn--primary" data-testid="spot-fly" onClick={() => onFly(at.site.id)}>
                  Fly down to the terrain
                  <IconArrow />
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
