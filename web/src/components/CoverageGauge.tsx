import { useMemo } from 'react';
import { controllingCells } from '../bundle/evidence';
import type { View } from '../store/view';
import { useCoverageSidecar } from '../bundle/coverageSidecar';
import { usePolaris } from '../store/store';

/**
 * Coverage Gauge: how much of the terrain that actually controls the horizon is covered by the
 * uncertainty models (the PGDA 78 5 m clones cover only a local tile; distant 80 m terrain is not
 * represented by any clone). A low value must qualify any "robust across every clone" claim.
 *
 * Preferred source: derived.coverage (controlling-cell-hours inside the clone footprint, the same
 * near critical margins, and unknown/truncated hours). Fallback: a display tally of blocked bundle
 * samples by the DEM layer that set their horizon (near 5 m tile vs far 80 m layer), which is the raw
 * ingredient of the gauge but not the solver's hour-weighted, near-critical measure.
 */
const pct = (f: number | null | undefined) => (f === null || f === undefined || !Number.isFinite(f) ? '—' : `${(f * 100).toFixed(0)}%`);

function Gauge({ label, inside, critical, unknown, testId }: { label: string; inside: number | null; critical: number | null; unknown: number | null; testId: string }) {
  const w = 220;
  const a = inside === null ? 0 : Math.max(0, Math.min(1, inside));
  const u = unknown === null ? 0 : Math.max(0, Math.min(1 - a, unknown));
  return (
    <div className="gauge" data-testid={testId} data-inside={inside === null ? '' : a.toFixed(3)}>
      <div className="gauge-head">
        <strong>{label}</strong>
        <span className={a >= 0.9 ? 'ok' : a >= 0.5 ? 'warn-text' : 'bad'}>{pct(inside)} inside clone footprint</span>
      </div>
      <svg viewBox={`0 0 ${w} 14`} className="gauge-bar" role="img" aria-label={`${label}: ${pct(inside)} of controlling terrain inside the clone footprint, ${pct(unknown)} unknown`}>
        <rect x={0} y={2} width={w} height={10} className="g-outside" />
        <rect x={0} y={2} width={w * a} height={10} className="g-inside" />
        <rect x={w * (1 - u)} y={2} width={w * u} height={10} className="g-unknown" />
      </svg>
      <div className="gauge-foot muted small">
        near-critical samples inside: {pct(critical)} · outside footprint: {pct(inside === null ? null : 1 - a - u)} · horizon unknown: {pct(unknown)}
      </div>
    </div>
  );
}

/** Penumbra coverage ring: the batch Coverage Gauge (sidecar), drawn as two concentric arcs (Sun solid, Earth dashed). */
function Rings({ sun, earth }: { sun: number; earth: number }) {
  const arc = (p: number, r: number, cls: string, dash?: string) => {
    const L = 2 * Math.PI * r;
    return (
      <g>
        <circle cx={80} cy={80} r={r} fill="none" stroke="var(--raised)" strokeWidth={10} />
        <circle cx={80} cy={80} r={r} fill="none" className={cls} strokeWidth={10} strokeDasharray={dash ?? `${((p / 100) * L).toFixed(1)} ${L.toFixed(1)}`} transform="rotate(-90 80 80)" />
      </g>
    );
  };
  const r2 = 46;
  const L2 = 2 * Math.PI * r2;
  return (
    <svg viewBox="0 0 160 160" width={150} height={150} role="img" aria-label={`Coverage: Sun ${sun.toFixed(1)} percent, Earth ${earth.toFixed(1)} percent of hours controlled inside the clone tile`}>
      {arc(sun, 64, 'ring-sun')}
      {arc(earth, r2, 'ring-earth', `${((earth / 100) * L2).toFixed(1)} ${L2.toFixed(1)}`)}
      <style>{'.ring-sun{stroke:var(--solar)}.ring-earth{stroke:var(--earth)}'}</style>
    </svg>
  );
}

export function CoverageGauge({ v }: { v: View }) {
  // Merge note (15 Nov): prefer the batch Coverage Gauge sidecar when it covers this site (session A's
  // verified view); fall back to the bundle's derived.coverage, then to the display tally.
  const batch = useCoverageSidecar();
  const bc = batch?.sites[v.dataset.siteId] ?? null;
  const cov = bc ? null : (v.dataset.derived?.coverage ?? null);
  // E3 (15 Nov): the bundle's own derived.coverage, shown next to the batch sidecar when both exist (different sampling).
  const bundleCov = v.dataset.derived?.coverage ?? null;
  const altSun = bundleCov?.sun.allHoursInside ?? null;
  const altEarth = bundleCov?.earth.allHoursInside ?? null;
  // E4: all_hours_covered_frac = 0 for both bodies means no window hour's controlling horizon lies in the clone tile.
  const noCloneCoverage = altSun === 0 && altEarth === 0;
  const pct2 = (f: number) => `${(f * 100).toFixed(2)} %`;
  const side = usePolaris((st) => st.certaintySidecar);
  const pass1 = (side?.sites?.[v.dataset.siteId]?.certainty_curve as { mast_m: number; metric: string; pass: string }[] | undefined)?.find(
    (r) => r.mast_m === 1 && r.metric === 'sun_centre_pct',
  )?.pass;
  const nClones = (side?.sites?.[v.dataset.siteId]?.certainty_curve as { n_clones: number }[] | undefined)?.[0]?.n_clones;
  const ridges = v.dataset.derived?.attribution?.ridges ?? [];
  const farEarth = ridges.filter((r) => r.dem === 'far_80m').reduce((a, r) => a + r.hours.earth.lost, 0);
  const allEarth = ridges.reduce((a, r) => a + r.hours.earth.lost, 0);
  const sk = v.series?.skyline;
  const samples = v.series?.samples;
  const layers = v.dataset.sourceLayers ?? [];
  const nearLayer = layers.find((l) => l.role === 'near');
  const tally = useMemo(() => {
    if (cov || !sk?.critical || !samples || !nearLayer) return null;
    return (['sun', 'earth'] as const).map((k) => {
      const c = controllingCells(v.dataset.ephemeris.samples, samples[k], sk, k, v.times);
      let inside = 0;
      let unknown = c.nBlockedWithoutCell;
      let truncated = 0;
      for (const cell of c.cells) {
        if (cell.cell.dem === nearLayer.name) inside += cell.samples.length;
        if (cell.coverage.includes('truncated')) truncated += cell.samples.length;
      }
      unknown += truncated;
      return { key: k, nBlocked: c.nBlocked, inside: c.nBlocked ? inside / c.nBlocked : null, unknown: c.nBlocked ? unknown / c.nBlocked : null };
    });
  }, [cov, sk, samples, nearLayer, v.dataset.ephemeris.samples, v.times]);

  return (
    <section className="panel" aria-labelledby="cg-title" data-testid="coverage-gauge">
      <div className="panel-head">
        <h2 id="cg-title">Coverage gauge · do the clones cover the controlling terrain?</h2>
        <span className="muted">{cov ? `from bundle derived.coverage (${cov.method}; critical = |margin| < ${cov.criticalMarginDeg}°)` : tally ? 'display tally from bundle critical cells (not derived.coverage)' : 'not in bundle'}</span>
      </div>
      {bc && batch && (
        <div data-testid="coverage-batch">
          <div className="ring-row">
            <Rings sun={bc.sun_pct} earth={bc.earth_pct} />
            <div className="ring-facts">
              <div>
                <div className="v sun">{bc.sun_pct.toFixed(1)} %</div>
                <div className="d">of all window hours (Sun direction) whose horizon is set inside the clone tile, the terrain the alternate realizations vary</div>
              </div>
              <div>
                <div className="v earth">{bc.earth_pct.toFixed(1)} %</div>
                <div className="d">of all window hours (Earth direction)</div>
              </div>
            </div>
          </div>
            {pass1 && (
              <p className="cov-claim" data-testid="coverage-claim">
                {pass1} tested realizations meet the team's Sun ≥ 70 % requirement at 1 m. However, only {bc.sun_pct.toFixed(1)} % of the window's Sun-direction
                horizon is set by terrain those realizations vary.
              </p>
            )}
          {altSun !== null && altEarth !== null && (
            <p className="muted small" data-testid="coverage-bundle-alt">
              Bundle derived.coverage: Sun {pct2(altSun)}, Earth {pct2(altEarth)} (different sampling; see docs/SOLVER_RECONCILIATION.md)
            </p>
          )}
          <details className="dec-more">
            <summary>What coverage measures · definition and source</summary>
          <p className="source-line">
            Batch Coverage Gauge · {batch.definition} · {batch.source.path} (SHA-256 {batch.source.sha256.slice(0, 12)}…, {batch.source.repo_commit}) · {batch.status.replace(/_/g, ' ')}
          </p>
          <div className="cov-explain" data-testid="coverage-explain">
            <p>
              <strong>What is measured.</strong> For each hour of the window (nominal DEM, 1 m mast) the batch finds the terrain cell that sets the horizon in the
              target's direction and asks whether it lies inside the {(bc.tile_inscribed_radius_m / 1000).toFixed(1)} km tile where the {nClones ?? ''} alternate
              PGDA 78 realizations differ. Outside the tile the horizon comes from the shared 80 m regional DEM, identical in every realization, so agreement there carries no
              information about terrain uncertainty.
            </p>
            <p>
              <strong>Reading the two numbers below.</strong> The bundle tally counts only <em>blocked</em> samples
              {tally?.find((t) => t.key === 'sun')?.inside === 1 ? ': every Sun-blocked sample is controlled inside the tile, so the realizations do test the Sun losses' : ''}. The{' '}
              {bc.sun_pct.toFixed(1)} % covers <em>all</em> hours: the rest are decided by distant terrain no realization varies.
              {farEarth > 0 && ` ${farEarth} of the ${allEarth} Earth-blocked samples the bundle attributes to a ridge are set by terrain in the 80 m regional DEM, outside the tile.`}
            </p>
            <p className="muted small">Not modelled: terrain outside both DEMs' accuracy, the lander's own structure, and any realization beyond the ones evaluated.</p>
          </div>
          </details>
        </div>
      )}
      {noCloneCoverage && (
        <p className="warn" data-testid="coverage-no-clone">
          No clone coverage at this RoI: at every Sun and Earth azimuth reached in this window the bundle's controlling horizon comes from the 80 m regional DEM,
          outside the 5 m clone tile (derived.coverage all_hours_covered_frac = 0 for both). Clone agreement here says nothing about terrain uncertainty. See
          docs/SOLVER_RECONCILIATION.md §E4.
        </p>
      )}
      <details className="dec-more" open={!bc}>
        <summary>Per-sample tally from this bundle (blocked samples only)</summary>
      {cov ? (
        <>
          <Gauge label="Sun" inside={cov.sun.controllingHoursInside} critical={cov.sun.criticalHoursInside} unknown={cov.sun.unknownHours} testId="gauge-sun" />
          <Gauge label="Earth" inside={cov.earth.controllingHoursInside} critical={cov.earth.criticalHoursInside} unknown={cov.earth.unknownHours} testId="gauge-earth" />
          <p className="muted small">
            Footprint: {cov.footprint.dem}
            {cov.footprint.cloneIds ? ` · ${cov.footprint.cloneIds.length} realizations` : ''}. Hours weighted by the bundle's own sample spacing.
          </p>
        </>
      ) : tally ? (
        <>
          {tally.map((t) => (
            <Gauge key={t.key} label={t.key === 'sun' ? 'Sun' : 'Earth'} inside={t.inside} critical={null} unknown={t.unknown} testId={`gauge-${t.key}`} />
          ))}
          <p className="muted small">
            Share of blocked bundle samples whose horizon-setting cell lies in the near layer “{nearLayer!.name}” (the clone tile). Not hour-weighted, no near-critical split: those arrive with derived.coverage.
            {tally.every((t) => t.nBlocked === 0) && ' No blocked samples in this window, so coverage is moot here.'}
          </p>
        </>
      ) : (
        <p className="note">Coverage needs skyline critical cells with their DEM layer; this bundle has none. The viewer does not compute it.</p>
      )}
      </details>
      {(cov ? [cov.sun.controllingHoursInside, cov.earth.controllingHoursInside] : [...(tally ?? []).map((t) => t.inside), ...(bc ? [bc.sun_pct / 100, bc.earth_pct / 100] : [])]).some((f) => f !== null && Number.isFinite(f) && f < 0.5) && (
        <p className="warn" data-testid="coverage-warning">
          Below 50 %: the alternate terrain realizations vary less than half of the terrain that controls this result. Any "passes on every tested realization" claim must carry the coverage number next to it (team wording rule). Agreement across realizations is never a calibrated success probability.
        </p>
      )}
    </section>
  );
}
