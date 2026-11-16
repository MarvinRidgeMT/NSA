import { useMemo, useState } from 'react';
import { binForAzimuth, controllingCells, groupAdjacentCells, type Controlling } from '../bundle/evidence';
import type { Ridge } from '../bundle/types';
import { usePolaris } from '../store/store';
import { useRidgeFocus } from '../store/ridge';
import { fmtUtc, type View } from '../store/view';

/**
 * Ridge of Record: which terrain sets the horizon that blocks the Sun / Earth.
 *
 * Preferred source: derived.attribution (ridges with hours controlled / hours lost, runner-up gap,
 * elevation sigma), emitted by the science branch. Until a bundle carries it, the panel shows the
 * bundle's own per-bin critical cells: for every blocked sample the cell of the target's skyline bin,
 * tallied per cell. That tally counts bundle samples; it is not a solver "hours controlled" metric and
 * is labelled as such. Clicking a row seeks the shared clock to the first blocked sample and highlights
 * the bin in the horizon chart and the 3D panorama.
 */
const shortDem = (d?: string | null) => (d ? d.replace(/LOLA /, '').replace(/ \(PGDA product (\d+)\)/, ' · PGDA $1') : '—');
const rangeTxt = (r: { min: number; max: number } | number | undefined, unit: string, digits = 0) =>
  r === undefined ? '—' : typeof r === 'number' ? `${r.toFixed(digits)}${unit}` : r.min === r.max ? `${r.min.toFixed(digits)}${unit}` : `${r.min.toFixed(digits)}–${r.max.toFixed(digits)}${unit}`;

function NowLine({ v, tally }: { v: View; tally: Controlling }) {
  const sk = v.series?.skyline;
  const t = v[tally.target];
  if (!sk || t.visible !== false) return null;
  const bin = binForAzimuth(t.az, sk.azimuthDeg.length);
  const c = sk.critical?.[bin];
  return (
    <p className="now-ridge" data-testid={`ridge-now-${tally.target}`}>
      <strong>{tally.target === 'sun' ? 'Sun' : 'Earth'} blocked now</strong> at az {t.az.toFixed(1)}° (bin {bin}
      {sk.coverage?.[bin] === 'truncated' ? ', truncated bin: lower bound' : ''}):{' '}
      {(() => {
        const att = v.dataset.derived?.attribution;
        const ri = att?.perBin?.ridgeIdx?.[bin];
        const r = ri != null ? att?.ridges[ri] : undefined;
        return r ? <strong className="ridge-id" data-testid={`ridge-now-id-${tally.target}`}>{r.label ?? r.id} · </strong> : null;
      })()}
      {c && c.distance_m != null ? (
        <>
          horizon set by terrain {(c.distance_m / 1000).toFixed(2)} km away{c.height_m != null ? `, ${c.height_m.toFixed(0)} m` : ''} · {shortDem(c.dem)}
          {c.grid_x_m != null && c.grid_y_m != null ? ` · grid (${c.grid_x_m.toFixed(0)}, ${c.grid_y_m.toFixed(0)}) m` : ''}
        </>
      ) : (
        'no critical cell recorded for this bin'
      )}
    </p>
  );
}

export function RidgePanel({ v }: { v: View }) {
  const { setSampleIndex, selectBin, setTime } = usePolaris.getState();
  const selectedBin = usePolaris((s) => s.selectedBin);
  const { focus } = useRidgeFocus(v);
  const attribution = v.dataset.derived?.attribution ?? null;
  const sk = v.series?.skyline;
  const samples = v.series?.samples;
  const tallies = useMemo(() => {
    if (!sk || !samples) return null;
    return (['sun', 'earth'] as const).map((k) => controllingCells(v.dataset.ephemeris.samples, samples[k], sk, k, v.times));
  }, [sk, samples, v.dataset.ephemeris.samples, v.times]);
  const nBins = sk?.azimuthDeg.length ?? 0;

  const pickRidge = (r: Ridge) => {
    const idx = attribution ? attribution.ridges.indexOf(r) : -1;
    const ridgeBins = attribution?.perBin ? attribution.perBin.ridgeIdx.flatMap((x, b) => (x === idx ? [b] : [])) : [];
    const az = (r.azimuthDeg[0] + r.azimuthDeg[1]) / 2;
    selectBin(ridgeBins.length ? ridgeBins[Math.floor(ridgeBins.length / 2)] : nBins ? binForAzimuth(az, nBins) : null);
    const first = r.hours.earth.intervals?.[0]?.[0] ?? r.hours.sun.intervals?.[0]?.[0];
    if (first) return void setTime(Date.parse(first));
    // seek to the first sample the bundle marks blocked whose target bin belongs to this ridge (lookup, no computation)
    if (samples && nBins && ridgeBins.length) {
      const inRidge = new Set(ridgeBins);
      for (let i = 0; i < v.times.length; i++)
        for (const k of ['earth', 'sun'] as const)
          if (samples[k].visible[i] === false && inRidge.has(binForAzimuth(v.dataset.ephemeris.samples[i][k].az, nBins))) return void setSampleIndex(i);
    }
  };
  const ridgesShown = attribution
    ? [...attribution.ridges].sort((a, b) => Number(!!b.ofRecord) - Number(!!a.ofRecord) || b.hours.sun.lost + b.hours.earth.lost - (a.hours.sun.lost + a.hours.earth.lost) || b.hours.sun.controlled + b.hours.earth.controlled - (a.hours.sun.controlled + a.hours.earth.controlled))
    : [];
  const [showAll, setShowAll] = useState(false);

  return (
    <section className="panel" aria-labelledby="rr-title" data-testid="ridge-panel">
      <div className="panel-head">
        <h2 id="rr-title">Ridge of Record · what blocks the view</h2>
        <span className="muted">
          {attribution ? `from bundle derived.attribution (${attribution.method})` : sk?.critical ? 'from bundle critical cells · display tally of blocked samples (not a solver metric)' : 'not in bundle'}
          {selectedBin !== null && (
            <>
              {' '}
              ·{' '}
              <button type="button" className="btn btn-small" onClick={() => selectBin(null)}>
                clear highlight
              </button>
            </>
          )}
        </span>
      </div>
      {tallies?.map((t) => <NowLine key={t.target} v={v} tally={t} />)}
      {attribution ? (
        <>
        <table className="constraints">
          <thead>
            <tr>
              <th scope="col">Ridge</th>
              <th scope="col">Azimuth</th>
              <th scope="col">Distance</th>
              <th scope="col" title="ridge height minus the site ground height (bundle relief_m); absolute height in the tooltip">Height vs site</th>
              <th scope="col">Sun h controlled / lost</th>
              <th scope="col">Earth h controlled / lost</th>
              <th scope="col">Runner-up gap</th>
              <th scope="col">Source</th>
            </tr>
          </thead>
          <tbody>
            {ridgesShown.slice(0, showAll ? ridgesShown.length : 8).map((r) => (
              <tr key={r.id} className={focus?.ridge === r ? 'is-selected' : ''}>
                <th scope="row">
                  <button type="button" className="linkish" onClick={() => pickRidge(r)} data-testid="ridge-row">
                    {r.label ?? r.id}
                  </button>
                  {r.ofRecord && <span className="of-record" title="caused at least one Sun or Earth loss sample (bundle)"> of record</span>}
                </th>
                <td>
                  {r.azimuthDeg[0].toFixed(1)}–{r.azimuthDeg[1].toFixed(1)}°
                </td>
                <td>{rangeTxt(typeof r.distanceM === 'number' ? r.distanceM / 1000 : { min: r.distanceM.min / 1000, max: r.distanceM.max / 1000 }, ' km', 2)}</td>
                <td title={typeof r.heightM === 'number' ? `absolute ${r.heightM.toFixed(1)} m (DEM height above the reference radius)` : undefined} data-testid={`ridge-relief-${r.id}`}>
                  {r.reliefM !== undefined ? `${r.reliefM >= 0 ? '+' : '−'}${Math.abs(r.reliefM).toFixed(Math.abs(r.reliefM) < 100 ? 2 : 0)} m` : rangeTxt(r.heightM, ' m')}
                  {r.elevationSigmaM != null ? ` ±${r.elevationSigmaM.toFixed(1)}` : ''}
                </td>
                <td>
                  {r.hours.sun.controlled.toFixed(1)} / {r.hours.sun.lost.toFixed(1)}
                </td>
                <td>
                  {r.hours.earth.controlled.toFixed(1)} / {r.hours.earth.lost.toFixed(1)}
                </td>
                <td>{r.runnerUpGapDeg == null ? '—' : `${Math.abs(r.runnerUpGapDeg) >= 0.01 ? r.runnerUpGapDeg.toFixed(2) : Number(r.runnerUpGapDeg.toPrecision(2))}°`}</td>
                <td className="wrap">
                  {shortDem(r.dem)}
                  {r.resolutionM ? ` · ${r.resolutionM} m` : ''}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {ridgesShown.length > 8 && (
          <p className="muted small">
            {ridgesShown.filter((r) => r.ofRecord).length} ridges of record (caused a loss) among {ridgesShown.length} attributed clusters.{' '}
            <button type="button" className="btn btn-small" onClick={() => setShowAll(!showAll)} data-testid="ridge-show-all">
              {showAll ? 'show top 8' : `show all ${ridgesShown.length}`}
            </button>
          </p>
        )}
        </>
      ) : tallies ? (
        tallies.map((t) => (
          <div key={t.target} className="ridge-group">
            <h3>
              {t.target === 'sun' ? 'Sun' : 'Earth'} · {t.nBlocked} blocked sample{t.nBlocked === 1 ? '' : 's'} of {v.times.length}
              {t.nBlockedWithoutCell ? ` · ${t.nBlockedWithoutCell} without a recorded cell` : ''}
            </h3>
            {t.cells.length === 0 ? (
              <p className="muted">No blocked samples in this window.</p>
            ) : (
              <table className="constraints">
                <thead>
                  <tr>
                    <th scope="col">Controlling terrain (adjacent bundle critical cells)</th>
                    <th scope="col">Azimuth</th>
                    <th scope="col">Distance</th>
                    <th scope="col">Height</th>
                    <th scope="col">Blocked samples</th>
                    <th scope="col">Cells · bins</th>
                  </tr>
                </thead>
                <tbody>
                  {groupAdjacentCells(t.cells, nBins).slice(0, 8).map((g) => (
                    <tr key={g.id} className={g.bins.includes(selectedBin ?? -1) ? 'is-selected' : ''}>
                      <th scope="row">
                        <button
                          type="button"
                          className="linkish"
                          data-testid={`ridge-cell-${t.target}`}
                          onClick={() => {
                            const top = [...g.cells].sort((a, b) => b.samples.length - a.samples.length)[0];
                            selectBin(top.bins[0]);
                            setSampleIndex(top.firstIndex);
                          }}
                          title={`seek to ${fmtUtc(v.times[g.firstIndex])} and highlight the busiest bin`}
                        >
                          {shortDem(g.dem)}
                        </button>
                      </th>
                      <td>
                        {g.azimuthDeg[0].toFixed(1)}
                        {g.azimuthDeg[1] !== g.azimuthDeg[0] ? `–${g.azimuthDeg[1].toFixed(1)}` : ''}°
                      </td>
                      <td>{Number.isFinite(g.distanceM.min) ? (g.distanceM.min === g.distanceM.max ? `${(g.distanceM.min / 1000).toFixed(2)} km` : `${(g.distanceM.min / 1000).toFixed(2)}–${(g.distanceM.max / 1000).toFixed(2)} km`) : '—'}</td>
                      <td>{g.heightM ? (g.heightM.min === g.heightM.max ? `${g.heightM.min.toFixed(0)} m` : `${g.heightM.min.toFixed(0)}–${g.heightM.max.toFixed(0)} m`) : '—'}</td>
                      <td>
                        {g.samples} ({g.sampledHours.toFixed(0)} h sampled)
                      </td>
                      <td>
                        {g.cells.length} · {g.bins.length}
                        {g.truncated ? ' · truncated' : ''}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        ))
      ) : (
        <p className="note">This bundle has no skyline critical cells, so nothing can be attributed. The viewer does not compute horizons.</p>
      )}
      <p className="muted small">
        Hours are hourly bundle samples (1 h each); each blocked hour belongs to exactly one ridge, so loss hours do not overlap. Hours a ridge controls are not hours that would be recovered by removing it; any terrain-change counterfactual needs a solver recomputation. Runner-up gaps are tiny, so treat a ridge's distance as a range.
        {!attribution && sk?.critical && ' Rows merge adjacent skyline bins whose critical cells share a DEM layer (display grouping, totals unchanged); "blocked samples" counts bundle samples. Scientific ridge clustering and hours controlled/lost arrive with derived.attribution.'}
      </p>
    </section>
  );
}
