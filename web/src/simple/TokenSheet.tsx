/**
 * Simple-mode token sheet (S1, 16 Nov 2026). Hidden reference page at ?mode=simple&sheet=1; nothing links to it.
 * Token values are read from the CSS at run time, so the sheet cannot drift from styles.css. Contrast ratios are computed
 * here from those values. The sample components show real values from the certainty sidecar (web/public/certainty/sidecar.json)
 * and the showcase gallery (web/public/showcase/gallery.json); if a file does not load, the sample says so and shows no number.
 */
import { useEffect, useLayoutEffect, useRef, useState, type PointerEvent } from 'react';
import { parseSidecar, type CertaintySidecar } from '../bundle/certaintySidecar';
import { HonestyTag, HoverLabel, IconArrow, IconSun, ObjectCard, SitePin, SoundControl } from './parts';

type Row = { mast_m: number; metric: string; min: number; max: number; nominal: number; n_clones: number };
type GalleryItem = { site: string; siteName: string; label: string; file: string };

const COLOURS: [token: string, name: string, use: string][] = [
  ['--c-base', 'Base', 'Page and sky'],
  ['--c-raised', 'Raised', 'Glass tint, top bar'],
  ['--c-nested', 'Nested', 'Panel inside a panel'],
  ['--c-bone', 'Bone', 'Primary text'],
  ['--c-ash', 'Ash', 'Secondary text'],
  ['--c-dust', 'Dust', 'Marks on base only'],
  ['--c-amber', 'Amber', 'Sun, primary action, focus'],
  ['--c-earth', 'Earth', 'Earth'],
  ['--c-alert', 'Alert', 'Blocked: marks, large text'],
  ['--c-alert-ink', 'Alert ink', 'Blocked: small text'],
  ['--c-selenite', 'Selenite', 'Geometry, ridges'],
];
const TEXT_COLOURS = ['--c-bone', '--c-ash', '--c-dust', '--c-amber', '--c-earth', '--c-alert', '--c-alert-ink', '--c-selenite'];
const TYPE = ['xs', 'sm', 'base', 'md', 'lg', 'xl', '2xl', '3xl', '4xl'];
const SPACE = ['1', '2', '3', '4', '6', '8', '12', '16'];
const MOTION: [dur: string, ease: string, use: string][] = [
  ['--dur-press', '--ease-enter', 'Press and hover feedback'],
  ['--dur-anim', '--ease-standard-curve', 'Panels, cards'],
  ['--dur-camera', '--ease-standard-curve', 'Camera pills'],
  ['--dur-major', '--ease-standard-curve', 'Fly-to'],
];
const OTHER = ['--radius-subtle', '--glass-bg', '--glass-border', '--glass-blur', '--glass-dim', '--glass-pad', '--shadow-elevation', '--ctl-sm', '--ctl-md', '--ctl-lg', '--ctl-input', '--focus-ring', '--pin-gain', '--pin-ring-per-pt'];

type Rgba = [number, number, number, number];
function parseColour(v: string): Rgba | null {
  const s = v.trim();
  const hex = /^#([0-9a-f]{6})$/i.exec(s);
  if (hex) return [0, 2, 4].map((i) => parseInt(hex[1].slice(i, i + 2), 16)).concat(1) as Rgba;
  const fn = /^rgba?\(([^)]+)\)$/i.exec(s);
  if (!fn) return null;
  const p = fn[1].split(/[\s,/]+/).filter(Boolean).map(Number);
  return p.length >= 3 && p.every(Number.isFinite) ? [p[0], p[1], p[2], p[3] ?? 1] : null;
}
const over = (top: Rgba, under: Rgba): Rgba => [0, 1, 2].map((i) => top[i] * top[3] + under[i] * (1 - top[3])).concat(1) as Rgba;
const lum = (c: Rgba) =>
  [0.2126, 0.7152, 0.0722].reduce((sum, w, i) => {
    const x = c[i] / 255;
    return sum + w * (x <= 0.04045 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4);
  }, 0);
const ratio = (a: Rgba, b: Rgba) => {
  const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
};

function useTokens(names: string[]) {
  const ref = useRef<HTMLDivElement>(null);
  const [vals, setVals] = useState<Record<string, string>>({});
  useLayoutEffect(() => {
    if (!ref.current) return;
    const cs = getComputedStyle(ref.current);
    setVals(Object.fromEntries(names.map((n) => [n, cs.getPropertyValue(n).trim()])));
    // names is a module constant
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return [ref, vals] as const;
}

function useJson<T>(url: string, parse: (raw: unknown) => T | null) {
  const [state, set] = useState<{ data: T | null; failed: boolean }>({ data: null, failed: false });
  useEffect(() => {
    let live = true;
    fetch(url)
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => live && set({ data: parse(j), failed: parse(j) === null }))
      .catch(() => live && set({ data: null, failed: true }));
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url]);
  return state;
}

const fmtRange = (r?: Row) => (!r ? '—' : r.min === r.max ? `${r.min.toFixed(1)} %` : `${r.min.toFixed(1)}–${r.max.toFixed(1)} %`);
const spreadOf = (r?: Row) => (r ? Number((r.max - r.min).toFixed(1)) : null);

/** Every (site, mast) the sheet shows a pin for: the first sampled mast, and the mast where the Sun is 100 % in every variant. */
function pinRows(sc: CertaintySidecar) {
  return Object.entries(sc.sites).flatMap(([id, site]) => {
    const rows = site.certainty_curve as Row[];
    const masts = [...new Set([site.sampled_masts_m[0], site.all_maps_100pct_sun_mast_m].filter((m): m is number => typeof m === 'number'))];
    return masts.map((m) => ({ id, mast: m, sun: rows.find((r) => r.mast_m === m && r.metric === 'sun_centre_pct'), both: rows.find((r) => r.mast_m === m && r.metric === 'both_centre_pct'), cert: site.all_maps_100pct_sun_mast_m }));
  });
}

function Grade({ r }: { r: number }) {
  const grade = r >= 4.5 ? 'AA' : r >= 3 ? 'large' : 'fail';
  const word = grade === 'AA' ? 'text' : grade === 'large' ? 'large only' : 'no text';
  return (
    <span className="sheet-chip" data-grade={grade}>
      {r.toFixed(2)} · {word}
    </span>
  );
}

function MotionRow({ dur, ease, use, vals }: { dur: string; ease: string; use: string; vals: Record<string, string> }) {
  const [run, setRun] = useState(false);
  return (
    <div>
      <div>
        <b>{use}</b>
        <div className="sheet-code">
          {dur} {vals[dur]}
        </div>
      </div>
      <div className="sheet-row">
        <div className="sheet-track" data-run={run} style={{ flex: 1, minWidth: 160 }}>
          <i style={{ transition: `left var(${dur}) var(${ease})` }} />
        </div>
        <button type="button" className="s-btn s-btn--sm" onClick={() => setRun((x) => !x)}>
          Play
        </button>
      </div>
    </div>
  );
}

export default function TokenSheet() {
  const all = [...COLOURS.map((c) => c[0]), ...TYPE.flatMap((t) => [`--text-${t}`, `--text-${t}-lh`]), ...SPACE.map((s) => `--space-${s}`), ...MOTION.flatMap((m) => [m[0], m[1]]), ...OTHER];
  const [root, vals] = useTokens(all);
  const sidecar = useJson('certainty/sidecar.json', parseSidecar);
  const gallery = useJson<GalleryItem[]>('showcase/gallery.json', (raw) => {
    const items = (raw as { items?: GalleryItem[] } | null)?.items;
    return Array.isArray(items) ? items : null;
  });

  const pins = sidecar.data ? pinRows(sidecar.data) : [];
  // the sample card shows the site whose variants disagree most at its first sampled mast
  const lead = [...pins].sort((a, b) => (spreadOf(b.sun) ?? 0) - (spreadOf(a.sun) ?? 0))[0];
  const nameOf = (id: string) => gallery.data?.find((g) => g.site === id)?.siteName ?? id;
  const render = gallery.data?.find((g) => g.site === lead?.id && g.label === 'aerial') ?? gallery.data?.[0];
  const renderBg = render ? { backgroundImage: `url("showcase/${render.file}")` } : undefined;
  const renderCap = render ? `Blender render, display only · ${render.siteName}` : 'Render not loaded';

  // contrast grounds: solid tokens, plus the glass tint laid over full white after the panel's own dimming
  const c = (n: string) => parseColour(vals[n] ?? '');
  const glass = parseColour(vals['--glass-bg'] ?? '');
  const dim = Number(vals['--glass-dim']);
  const white: Rgba = [255 * dim, 255 * dim, 255 * dim, 1];
  const grounds: [string, Rgba | null][] = [
    ['Base', c('--c-base')],
    ['Raised', c('--c-raised')],
    ['Nested', c('--c-nested')],
    ['Glass on white terrain', glass && Number.isFinite(dim) ? over(glass, white) : null],
  ];

  const stage = useRef<HTMLDivElement>(null);
  const [pt, setPt] = useState<{ x: number; y: number } | null>(null);
  const onMove = (e: PointerEvent) => {
    const b = stage.current?.getBoundingClientRect();
    if (b && e.pointerType === 'mouse') setPt({ x: e.clientX - b.left + 14, y: e.clientY - b.top + 16 });
  };

  return (
    <div className="simple sheet" ref={root} data-testid="simple-sheet">
      <a className="skip" href="#sheet-main">
        Skip to content
      </a>
      <header className="sheet-wrap sheet-head">
        <h1 className="s-display">POLARIS X design system</h1>
        <p>Simple mode, section S1: every token and component the later sections build from. This page is hidden; nothing in the app links to it. Values are read from styles.css as you load the page.</p>
      </header>
      <nav className="sheet-nav" aria-label="Sections">
        <ul className="sheet-wrap">
          {['Colour', 'Contrast', 'Type', 'Spacing', 'Motion', 'Panels', 'Buttons', 'Inputs', 'Focus', 'Scene parts', 'Pins', 'Sound'].map((s) => (
            <li key={s}>
              <a href={`#${s.toLowerCase().replace(' ', '-')}`}>{s}</a>
            </li>
          ))}
        </ul>
      </nav>

      <main id="sheet-main" tabIndex={-1} className="sheet-wrap">
        <section className="sheet-sec" id="colour">
          <h2>Colour</h2>
          <p>Meaning is fixed: amber is the Sun, blue is Earth, alert is blocked and always comes with a word, selenite is geometry.</p>
          <div className="sheet-grid">
            {COLOURS.map(([t, name, use]) => (
              <div className="sheet-swatch" key={t}>
                <i style={{ background: `var(${t})` }} />
                <b>{name}</b>
                <code>
                  {t} {vals[t]}
                </code>
                <span>{use}</span>
              </div>
            ))}
          </div>
        </section>

        <section className="sheet-sec" id="contrast">
          <h2>Contrast</h2>
          <p>
            WCAG ratios, computed on this page from the tokens. The last column is the hardest case: a glass panel over sunlit terrain at full white. The panel dims
            what is behind it ({vals['--glass-dim']} brightness) before the tint, which is what keeps ash readable there. Body text needs 4.5; large text needs 3.
          </p>
          <div className="sheet-scroll">
            <table className="sheet-table">
              <thead>
                <tr>
                  <th scope="col">Text colour</th>
                  {grounds.map(([g]) => (
                    <th scope="col" key={g}>
                      {g}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {TEXT_COLOURS.map((t) => {
                  const fg = c(t);
                  return (
                    <tr key={t}>
                      <th scope="row">
                        <span className="sheet-row" style={{ gap: 8, flexWrap: 'nowrap' }}>
                          <span className="sheet-sample" style={{ color: `var(${t})`, background: 'var(--c-base)' }} aria-hidden="true">
                            Aa
                          </span>
                          {COLOURS.find((x) => x[0] === t)?.[1]}
                        </span>
                      </th>
                      {grounds.map(([g, bg]) => (
                        <td key={g}>{fg && bg ? <Grade r={ratio(fg, bg)} /> : '—'}</td>
                      ))}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>

        <section className="sheet-sec" id="type">
          <h2>Type</h2>
          <p>Instrument Serif for titles, Inter Tight for reading, JetBrains Mono for numbers, IDs and measurements only.</p>
          <div className="sheet-type">
            {[...TYPE].reverse().map((t) => {
              const px = parseFloat(vals[`--text-${t}`] ?? '');
              const face = px >= 24 ? 'var(--f-serif)' : 'var(--f-sans)';
              return (
                <div key={t}>
                  <span className="sheet-code">
                    --text-{t} {vals[`--text-${t}`]} / {vals[`--text-${t}-lh`]}
                  </span>
                  <p style={{ font: `400 var(--text-${t}) / var(--text-${t}-lh) ${face}` }}>Does a lander here keep the Sun?</p>
                </div>
              );
            })}
            <div>
              <span className="sheet-code">.s-data (mono, tabular)</span>
              <p className="s-data" style={{ fontSize: 'var(--text-xl)' }}>
                0123456789 · % m ° UTC
              </p>
            </div>
          </div>
        </section>

        <section className="sheet-sec" id="spacing">
          <h2>Spacing, radius, glass and control sizes</h2>
          <p>A {vals['--space-1']} base. Radius is {vals['--radius-subtle']} everywhere; nothing is pill-shaped.</p>
          <div className="sheet-space">
            {SPACE.map((s) => (
              <div key={s}>
                <span className="sheet-code">
                  --space-{s} {vals[`--space-${s}`]}
                </span>
                <i style={{ width: `var(--space-${s})` }} />
              </div>
            ))}
          </div>
          <h3 className="sheet-sub">Other tokens</h3>
          <div className="sheet-scroll">
            <table className="sheet-table">
              <tbody>
                {OTHER.map((t) => (
                  <tr key={t}>
                    <th scope="row" className="sheet-code">
                      {t}
                    </th>
                    <td className="num">{vals[t]}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="sheet-sec" id="motion">
          <h2>Motion</h2>
          <p>Controls answer in well under 300 ms; only the camera takes longer. With reduced motion switched on, every one of these is an instant cut.</p>
          <div className="sheet-motion">
            {MOTION.map(([d, e, use]) => (
              <MotionRow key={d} dur={d} ease={e} use={use} vals={vals} />
            ))}
          </div>
          <p className="sheet-code" style={{ marginTop: 'var(--space-4)' }}>
            --ease-standard-curve {vals['--ease-standard-curve']} · --ease-enter {vals['--ease-enter']}
          </p>
        </section>

        <section className="sheet-sec" id="panels">
          <h2>Panels</h2>
          <p>The same glass panel on the three grounds it has to survive. Ash text on the white ground is the pairing to check.</p>
          <div className="sheet-grounds">
            {(
              [
                ['sky', 'Black sky', undefined],
                ['render', renderCap, renderBg],
                ['white', 'Full white (worst case)', undefined],
              ] as const
            ).map(([g, cap, bg]) => (
              <div className="sheet-ground" data-ground={g} style={bg} key={g}>
                <span className="sheet-cap">{cap}</span>
                <div className="s-panel">
                  <h3 className="s-title">Glass panel</h3>
                  <p className="s-meta" style={{ marginTop: 6 }}>
                    Ash secondary text has to stay readable here, at this size, over any terrain.
                  </p>
                  <div className="s-panel-nested" style={{ marginTop: 16 }}>
                    <p className="s-meta">Nested panel, solid, for grouped controls.</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="sheet-sec" id="buttons">
          <h2>Buttons</h2>
          <p>{vals['--ctl-md']} by default, {vals['--ctl-sm']} in dense panels, {vals['--ctl-lg']} for the one main action and on phones. Each presses in slightly when clicked.</p>
          {(
            [
              [`Large, ${vals['--ctl-lg']}`, 's-btn--lg'],
              [`Default, ${vals['--ctl-md']}`, ''],
              [`Small, ${vals['--ctl-sm']}`, 's-btn--sm'],
            ] as const
          ).map(([cap, size]) => (
            <div key={cap}>
              <h3 className="sheet-sub">{cap}</h3>
              <div className="sheet-row">
                <button type="button" className={`s-btn s-btn--primary ${size}`}>
                  Enter
                  <IconArrow />
                </button>
                <button type="button" className={`s-btn ${size}`}>
                  Approach
                </button>
                <button type="button" className={`s-btn ${size}`} aria-pressed="true">
                  Mast-eye
                </button>
                <button type="button" className={`s-btn s-btn--quiet ${size}`}>
                  Reset
                </button>
                <button type="button" className={`s-btn s-btn--icon ${size}`} aria-label="Show the Sun">
                  <IconSun />
                </button>
                <button type="button" className={`s-btn ${size}`} disabled>
                  Disabled
                </button>
                <button type="button" className={`s-btn ${size}`} aria-busy="true">
                  Loading
                </button>
              </div>
            </div>
          ))}
        </section>

        <section className="sheet-sec" id="inputs">
          <h2>Inputs</h2>
          <p>{vals['--ctl-input']} high. The label is always visible; the placeholder is only an example.</p>
          <div className="sheet-fields">
            <div className="s-field">
              <label htmlFor="sh-utc">Go to a time (UTC)</label>
              <input id="sh-utc" className="s-input s-data" placeholder="YYYY-MM-DD HH:00" aria-describedby="sh-utc-help" />
              <span className="s-field-help" id="sh-utc-help">
                Only hours inside the mission window exist.
              </span>
            </div>
            <div className="s-field">
              <label htmlFor="sh-site">Site</label>
              <select id="sh-site" className="s-select" key={lead?.id} defaultValue={lead?.id}>
                {sidecar.data ? Object.keys(sidecar.data.sites).map((id) => <option key={id} value={id}>{nameOf(id)}</option>) : <option>Sidecar not loaded</option>}
              </select>
            </div>
            <div className="s-field">
              <label htmlFor="sh-err">Go to a time (UTC)</label>
              <input id="sh-err" className="s-input s-data" defaultValue="not a time" aria-invalid="true" aria-describedby="sh-err-msg" />
              <span className="s-field-error" id="sh-err-msg">
                That is not a time. Use the form YYYY-MM-DD HH:00.
              </span>
            </div>
            <div className="s-field">
              <label htmlFor="sh-dis">Disabled</label>
              <input id="sh-dis" className="s-input" placeholder="Not available" disabled />
            </div>
          </div>
        </section>

        <section className="sheet-sec" id="focus">
          <h2>Focus</h2>
          <p>A {vals['--focus-ring']} amber ring with a dark gap inside it, so it shows on black sky and on white terrain alike. Shown here forced on; press Tab anywhere to see it live.</p>
          <div className="sheet-focus" data-ground="base">
            <button type="button" className="s-btn sheet-ring">
              On base
            </button>
            <input className="s-input sheet-ring" style={{ width: 200 }} aria-label="Focused input on base" defaultValue="Focused input" />
          </div>
          <div className="sheet-focus" data-ground="white" style={{ marginTop: 16 }}>
            <button type="button" className="s-btn s-btn--primary sheet-ring">
              On white
            </button>
            <button type="button" className="s-btn sheet-ring" style={{ background: 'var(--c-raised)' }}>
              On white
            </button>
          </div>
        </section>

        <section className="sheet-sec" id="scene-parts">
          <h2>Scene parts</h2>
          <p>What you get when you point at and click an object in the 3D scene (section S12). The label follows the pointer; the card opens beside the object. Move the mouse over the picture.</p>
          <div className="sheet-stage" ref={stage} style={renderBg} onPointerMove={onMove} onPointerLeave={() => setPt(null)}>
            <HoverLabel name="Landing site" hint="Click to open" style={{ transform: pt ? `translate(${pt.x}px, ${pt.y}px)` : 'translate(24px, 24px)' }} />
            {lead ? (
              <ObjectCard
                kind={`Landing site · mast ${lead.mast} m`}
                title={nameOf(lead.id)}
                origin="right"
                honestyHref="?mode=expert#evidence"
                facts={[
                  { label: 'Sun in sight', value: fmtRange(lead.sun), sub: lead.sun ? `nominal ${lead.sun.nominal.toFixed(1)} %` : undefined, tone: 'sun' },
                  { label: 'Sun + Earth together', value: fmtRange(lead.both), sub: lead.both ? `nominal ${lead.both.nominal.toFixed(1)} %` : undefined, tone: 'earth' },
                  {
                    label: 'Certainty Height',
                    hint: lead.cert !== null ? 'Lowest sampled mast with the Sun 100 % in every variant' : 'No sampled mast keeps the Sun 100 % in every variant',
                    value: lead.cert !== null ? `${lead.cert} m` : '—',
                  },
                ]}
                note={lead.sun ? `Ranges are across ${lead.sun.n_clones} terrain variants. Geometric line of sight to the disc centre, not power or communications.` : undefined}
              />
            ) : (
              <div className="s-panel s-objcard">
                <p className="s-meta">{sidecar.failed ? 'The certainty sidecar did not load, so the sample card shows no values.' : 'Loading the certainty sidecar…'}</p>
              </div>
            )}
            <span className="sheet-cap">{renderCap}</span>
          </div>
        </section>

        <section className="sheet-sec" id="pins">
          <h2>Map pins and the variant shimmer</h2>
          <p>
            Shimmer = how much the terrain variants disagree (Sun in sight, max − min, from the certainty sidecar). The halo travels further the larger the spread, and a
            pin with zero spread is still. With reduced motion the same number becomes the width of a static ring.
          </p>
          <div className="sheet-pins">
            {pins.flatMap((p) =>
              [false, true].map((still) => {
                const pts = spreadOf(p.sun);
                return (
                  <div className="sheet-pin" key={`${p.id}-${p.mast}-${still}`}>
                    <span>{pts !== null && <SitePin label={`${nameOf(p.id)}, mast ${p.mast} m, spread ${pts} points`} spreadPts={pts} still={still} />}</span>
                    <div>
                      <b>{pts !== null ? `${pts.toFixed(1)}-point spread` : '—'}</b>
                      <small>
                        {nameOf(p.id)} · {p.mast} m
                      </small>
                      <small>{still ? 'Reduced motion: static ring' : 'Shimmer'}</small>
                    </div>
                  </div>
                );
              }),
            )}
            {!pins.length && <p className="s-meta">{sidecar.failed ? 'The certainty sidecar did not load, so no pins are shown.' : 'Loading the certainty sidecar…'}</p>}
          </div>
          <div className="sheet-row" style={{ marginTop: 24 }}>
            <HonestyTag />
            <span className="sheet-cap">Source: certainty/sidecar.json</span>
          </div>
        </section>

        <section className="sheet-sec" id="sound">
          <h2>Sound</h2>
          <p>There is no sound at launch. The control is visible and reachable by keyboard, and says so when you point at it or focus it.</p>
          <div className="sheet-row" style={{ gap: 48, paddingBottom: 48 }}>
            <SoundControl />
            <span className="s-tipwrap">
              <button type="button" className="s-btn s-btn--sm s-btn--quiet" aria-disabled="true">
                Tooltip shown
              </button>
              <span className="s-tip" data-open="true">
                Sound coming later
              </span>
            </span>
          </div>
        </section>
      </main>
    </div>
  );
}
