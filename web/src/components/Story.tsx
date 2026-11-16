import { usePolaris } from '../store/store';
import { useView } from '../store/view';
import { fmtRidgeDistance } from '../bundle/evidence';
import { useCoverageSidecar } from '../bundle/coverageSidecar';

/**
 * Story (landing, Penumbra V3 boards "Landing"): a short editorial entry with a clear path into the live application.
 * Every number is read at runtime from a traceable source: the certainty sidecar (batch CSVs, a-science 971df9a), the
 * coverage sidecar (batch coverage_gauge.json) and the loaded science bundle. Nothing is typed in by hand; a missing source
 * shows "—". The terrain images are our own renders of the real PGDA 78 Site04 DEM with an illustrative Sun angle.
 */
const HERO_SITE = 'site04_roi3';
type Row = { mast_m: number; metric: string; min: number; max: number; nominal: number; median: number; p10: number; p90: number; pass: string; n_clones: number };

const pct = (x: number | undefined) => (x === undefined || !Number.isFinite(x) ? '—' : x.toFixed(1));
const range = (a?: Row) => (a ? (a.min === a.max ? `${pct(a.min)} %` : `${pct(a.min)}–${pct(a.max)} %`) : '—');

export function Story({ onEnter, onEvidence, onGuide }: { onEnter: () => void; onEvidence: () => void; onGuide?: () => void }) {
  const side = usePolaris((s) => s.certaintySidecar);
  const cov = useCoverageSidecar();
  const v = useView();
  const site = side?.sites?.[HERO_SITE];
  const rows = ((site?.certainty_curve as Row[] | undefined) ?? []).slice().sort((a, b) => a.mast_m - b.mast_m);
  const at = (m: number, metric: string) => rows.find((r) => r.mast_m === m && r.metric === metric);
  const sun1 = at(1, 'sun_centre_pct');
  const both1 = at(1, 'both_centre_pct');
  const cert = site?.all_maps_100pct_sun_mast_m ?? null;
  const both10 = at(10, 'both_centre_pct');
  const c = cov?.sites[HERO_SITE];
  const ds = v && v.dataset.siteId === HERO_SITE ? v.dataset : null;
  const ridge = ds?.derived?.attribution?.ridges.find((r) => r.hours.sun.lost > 0) ?? null;
  const sunMasts = rows.filter((r) => r.metric === 'sun_centre_pct');
  const nMaps = sun1?.n_clones;

  // certainty chart: one whisker per SAMPLED mast (ordinal axis: nothing implied between heights)
  const W = 520;
  const H = 260;
  const M = { l: 40, r: 16, t: 20, b: 34 };
  const xs = sunMasts.map((r) => r.mast_m);
  const x = (m: number) => M.l + 10 + (xs.indexOf(m) / Math.max(xs.length - 1, 1)) * (W - M.l - M.r - 20);
  const yMin = 80;
  const y = (p: number) => M.t + ((100 - Math.max(p, yMin)) / (100 - yMin)) * (H - M.t - M.b);

  // dot-range chart for 1 m (summary quantiles only: the sidecar carries min, p10, median, p90, max, nominal)
  const DW = 1100;
  const dx = (p: number) => 20 + ((p - 84) / (100 - 84)) * (DW - 40);

  return (
    <div className="story" data-testid="story">
      <section className="hero" aria-label="POLARIS X">
        <img src="penumbra/hero.webp" alt="Our render of NASA PGDA 78 Site04 terrain at the lunar south pole, with a low Sun on the horizon" />
        <div className="fade-top" />
        <div className="fade-bottom" />
        <div className="hero-copy">
          <div className="lab">NASA Space Apps 2026 · lunar south pole</div>
          <h1>
            The light at the
            <br />
            edge of the Moon
          </h1>
          <p>
            Will a lander keep the Sun and see the Earth? POLARIS X tests a landing site against {nMaps ?? 'the'} evaluated alternate NASA terrain realizations and
            shows how far that answer can be trusted.
          </p>
          <div className="cta">
            <button type="button" className="btn pri" onClick={onEnter} data-testid="story-enter">
              Open the explorer
            </button>
            {onGuide && (
              <button type="button" className="btn" onClick={onGuide} data-testid="story-guide">
                Guided demo
              </button>
            )}
            <button type="button" className="btn" onClick={onEvidence}>
              How we know
            </button>
          </div>
        </div>
        <div className="strip" data-testid="story-strip">
          <div>
            <div className="v sun">{range(sun1)}</div>
            <div className="d">Sun visible · 1 m mast · Site04 ROI3 · {nMaps ?? '—'} realizations (batch sweep)</div>
          </div>
          <div>
            <div className="v">{cert !== null ? `${cert} m` : '—'}</div>
            <div className="d">lowest sampled mast with the Sun 100 % on every tested realization</div>
          </div>
          <div>
            <div className="v earth">{range(both1)}</div>
            <div className="d">Sun and Earth together · 1 m mast</div>
          </div>
          <div>
            <div className="v">{c ? `${c.sun_pct.toFixed(1)} %` : '—'}</div>
            <div className="d">of window hours whose Sun horizon lies in the varied tile (coverage)</div>
          </div>
        </div>
        <p className="render-cap">Our render of the NASA PGDA 78 Site04 5 m DEM. Sun angle chosen for the picture, not a solver time step.</p>
      </section>

      <section className="chapter">
        <div>
          <div className="k">01 · The question</div>
          <h2>A lander at the pole lives on light it cannot count on.</h2>
          <p className="lead">
            Near the south pole the Sun never climbs more than a degree or two. A small rise close by can hide it for hours. The terrain models that decide this have
            errors of their own, so one map gives one answer, and we do not know if it is the right one.
          </p>
        </div>
        <div className="facts">
          <span className="lab">The site</span>
          <div className="v">
            {ds
              ? `${Math.abs(ds.site.latitudePlanetocentricDeg).toFixed(5)}° S · ${Math.abs(ds.site.longitudeEastDeg).toFixed(5)}° W`
              : 'Site04 ROI3'}
          </div>
          <div className="d">{ds ? `${ds.site.name}, NASA PGDA 78 candidate region` : 'open the explorer to load the bundle'}</div>
          <span className="lab">The blocker</span>
          <div className="v">{ridge ? `${fmtRidgeDistance(ridge)} away · az ${ridge.azimuthDeg[0].toFixed(0)}–${ridge.azimuthDeg[1].toFixed(0)}°` : '—'}</div>
          <div className="d">
            {ridge
              ? `${ridge.reliefM !== undefined ? `a rise ${ridge.reliefM.toFixed(1)} m above the site ground; ` : ''}${ridge.hours.sun.lost.toFixed(0)} Sun-blocked hourly samples attributed to it at the 1 m mast (bundle attribution, repo solver)`
              : 'from the bundle’s Ridge of Record'}
          </div>
        </div>
      </section>

      <section className="chapter one-col">
        <div className="k">02 · Twenty maps, twenty answers</div>
        <h2>The answer depends on which map is right.</h2>
        <p className="lead">
          NASA's PGDA 78 product includes alternate realizations of this terrain that reflect its elevation uncertainty; we evaluated {nMaps ?? 'several'} of them. At a 1 m
          mast the Sun stays up between {range(sun1)} of the two weeks, depending on the realization. They do not exhaust what the real ground could be.
        </p>
        <div className="figure">
          {sun1 ? (
            <svg viewBox={`0 0 ${DW} 120`} className="chart" role="img" aria-label={`Sun visible at a 1 m mast across ${nMaps} evaluated terrain realizations: ${range(sun1)}, nominal DEM ${pct(sun1.nominal)} %`}>
              <line x1={20} x2={DW - 20} y1={80} y2={80} className="axis-zero" />
              {[84, 88, 92, 96, 100].map((t) => (
                <g key={t}>
                  <line x1={dx(t)} x2={dx(t)} y1={80} y2={86} stroke="rgba(236,231,221,.4)" />
                  <text x={dx(t)} y={104} className="tick" textAnchor="middle">
                    {t} %
                  </text>
                </g>
              ))}
              <line x1={dx(sun1.min)} x2={dx(sun1.max)} y1={56} y2={56} stroke="var(--bone)" strokeWidth={2} />
              <rect x={dx(sun1.p10)} y={46} width={dx(sun1.p90) - dx(sun1.p10)} height={20} fill="var(--slate)" stroke="var(--bone)" />
              <line x1={dx(sun1.median)} x2={dx(sun1.median)} y1={44} y2={68} stroke="var(--bone)" strokeWidth={2} />
              <circle cx={dx(sun1.nominal)} cy={56} r={8} fill="none" stroke="var(--solar)" strokeWidth={2} />
              <text x={dx(sun1.min)} y={30} className="tick" textAnchor="middle">
                lowest {pct(sun1.min)}
              </text>
              <text x={dx(sun1.max)} y={30} className="tick" textAnchor="middle">
                highest {pct(sun1.max)}
              </text>
              <text x={dx(sun1.nominal)} y={14} textAnchor="middle" style={{ fill: 'var(--solar)', font: '500 12px var(--f-mono)' }}>
                nominal map {pct(sun1.nominal)}
              </text>
            </svg>
          ) : (
            <p className="note">The certainty sidecar did not load, so no range is shown.</p>
          )}
          <p className="source-line">
            Box = 10th–90th percentile of the {nMaps ?? '—'} realizations, line = median, whiskers = lowest and highest, ring = nominal map. Batch sweep CSV (a-science 971df9a) ·
            SOURCE-BASED, UNVALIDATED
          </p>
        </div>
      </section>

      <section className="wide-photo" aria-label="The ridge that decides">
        <img src="penumbra/wall.webp" alt="Our render of a slope in NASA Site04 terrain, half in shadow" />
        <div className="copy">
          <div className="k" style={{ font: '500 11px var(--f-sans)', letterSpacing: '0.14em', textTransform: 'uppercase', color: 'var(--solar)' }}>
            03 · The ridge that decides
          </div>
          <h2 style={{ font: '400 clamp(40px,4.4vw,60px)/1.02 var(--f-serif)', margin: '12px 0 0', textTransform: 'none', letterSpacing: '-0.01em' }}>A rise about as tall as a person.</h2>
          <p style={{ margin: '22px 0 0', fontSize: 18, lineHeight: 1.6, color: '#C9C4BA' }}>
            {ridge
              ? `At a 1 m mast the bundle attributes every Sun-blocked hourly sample (${ridge.hours.sun.lost}) to one rise ${ridge.reliefM !== undefined ? `${ridge.reliefM.toFixed(1)} m high, ` : ''}${fmtRidgeDistance(ridge)} from the lander, inside the area the alternate realizations vary. That is why they disagree.`
              : 'At a 1 m mast every hour without Sun is decided by terrain a few metres from the lander, inside the area the alternate realizations vary.'}
          </p>
        </div>
        <p className="cap">Our render of the real 5 m Site04 DEM, Sun angle illustrative. The rise itself is far smaller than this view can show.</p>
      </section>

      <section className="chapter">
        <div>
          <div className="k">04 · Raise the mast</div>
          <h2>{cert !== null ? `At ${cert} m, every map keeps the Sun.` : 'Raise the mast.'}</h2>
          <p className="lead">Lifting the solar panel clears the rise. The lowest sampled height that keeps the Sun on every map is the Certainty Height.</p>
          <p className="sub">
            Earth is harder: even at 10 m the Sun and Earth are both in view {both10 ? range(both10) : '—'} of the window. Team requirement: Sun ≥ 70 %, Sun and
            Earth ≥ 40 % (a team choice, not a NASA standard).
          </p>
        </div>
        <div className="figure" style={{ marginTop: 0 }}>
          {sunMasts.length ? (
            <svg viewBox={`0 0 ${W} ${H}`} className="chart" role="img" aria-label="Sun visible percent by sampled mast height: range across maps and nominal value">
              {[80, 90, 100].map((t) => (
                <g key={t}>
                  <line x1={M.l} x2={W - M.r} y1={y(t)} y2={y(t)} className="grid" />
                  <text x={M.l - 8} y={y(t) + 4} className="tick" textAnchor="end">
                    {t}
                  </text>
                </g>
              ))}
              {sunMasts.map((r) => (
                <g key={r.mast_m}>
                  <line x1={x(r.mast_m)} x2={x(r.mast_m)} y1={y(r.min)} y2={y(r.max)} className="whisker" />
                  <circle cx={x(r.mast_m)} cy={y(r.nominal)} r={4} fill="var(--basalt)" stroke="var(--bone)" strokeWidth={1.5} />
                  <text x={x(r.mast_m)} y={H - 12} className="tick" textAnchor="middle">
                    {r.mast_m}
                  </text>
                </g>
              ))}
              {cert !== null && xs.includes(cert) && (
                <g>
                  <line x1={x(cert)} x2={x(cert)} y1={M.t - 6} y2={H - M.b} stroke="var(--solar)" strokeDasharray="3 3" />
                  <text x={x(cert) + 8} y={y(100) + 18} style={{ fill: 'var(--solar)', font: '500 12px var(--f-mono)' }}>
                    {cert} m · {sun1?.n_clones ?? ''} of {sun1?.n_clones ?? ''} at 100 %
                  </text>
                </g>
              )}
            </svg>
          ) : (
            <p className="note">The certainty sidecar did not load.</p>
          )}
          <p className="source-line">Sun visible %, sampled masts only (m) · bar = range over maps, dot = nominal · batch sweep CSV · SOURCE-BASED, UNVALIDATED</p>
        </div>
      </section>

      <section className="chapter">
        <div>
          <div className="k">05 · Receipts</div>
          <h2>Every number can show where it came from.</h2>
          <dl className="receipts">
            <dt>terrain</dt>
            <dd>NASA PGDA 78 Site04 5 m DEM and the 20 evaluated alternate realizations; PGDA 90 80 m far field</dd>
            <dt>Sun and Earth</dt>
            <dd>JPL Horizons, 1 h steps, 14–28 Nov 2026</dd>
            <dt>coverage</dt>
            <dd>{c ? `Sun ${c.sun_pct.toFixed(1)} % · Earth ${c.earth_pct.toFixed(1)} % of hours controlled inside the clone tile` : '—'}</dd>
            <dt>checked against</dt>
            <dd>NASA PGDA 69 long-term maps (see Evidence)</dd>
            <dt>status</dt>
            <dd style={{ color: 'var(--bone)' }}>SOURCE-BASED · UNVALIDATED</dd>
          </dl>
          <div className="cta" style={{ marginTop: 36 }}>
            <button type="button" className="btn pri" onClick={onEnter}>
              Open the explorer
            </button>
            <button type="button" className="btn" onClick={onEvidence}>
              Open the evidence
            </button>
          </div>
        </div>
        <div className="facts" style={{ border: 0, padding: 0 }}>
          <img src="penumbra/map.webp" alt="Our overhead render of the Site04 DEM tile" style={{ width: '100%', display: 'block' }} />
          <div className="d">Site04 tile from above, our render. Region outlines are not drawn until the bundle carries their pixel positions.</div>
        </div>
      </section>

      <footer className="story-foot">
        <div>
          <strong>POLARIS X</strong>
          <div>NASA Space Apps Challenge 2026</div>
        </div>
        <p style={{ margin: 0 }}>Data: NASA PGDA products 69, 78 and 90; JPL Horizons. Not affiliated with or endorsed by NASA. No NASA insignia used.</p>
        <p style={{ margin: 0 }}>AI disclosure: AI tools helped write code, renders and this design; the team checks every number against its batch results.</p>
      </footer>
    </div>
  );
}
