import { useEffect, useState } from 'react';
import { TrekBasemap } from './TrekBasemap';
import { fetchDonki, fetchSkyNow, fetchSwpc, type BodyNow, type DonkiNote, type FeedState, type LiveSite, type ProtonNow } from './feeds';

// LIVE · CONTEXT panel. Display only; never writes to the store or to any stored result.

const fmt = (n: number, d = 2) => n.toFixed(d);

function Row<T>({ label, st, render }: { label: string; st: FeedState<T> | null; render: (v: T) => React.ReactNode }) {
  let body: React.ReactNode;
  let when = '…';
  if (!st) body = 'loading';
  else if (st.status === 'needs-proxy') body = 'needs the local solver proxy';
  else if (st.status === 'unavailable') body = `feed unavailable (${st.error})`;
  else {
    body = (
      <>
        {st.status === 'stale' && <strong data-testid="stale">stale · </strong>}
        {render(st.value)}
      </>
    );
    when = st.fetchedUtc;
  }
  return (
    <div role="row" data-feed={label} style={{ padding: '4px 0', borderTop: '1px solid rgba(255,255,255,.12)' }}>
      <div style={{ fontWeight: 600 }}>{label}</div>
      <div>{body}</div>
      <div style={{ opacity: 0.7, fontSize: 11 }}>
        fetched {when}
        {st && ` · ${st.source.split('?')[0]}`}
      </div>
    </div>
  );
}

export function NowPanel({ site, fetchImpl, now }: { site: LiveSite | null; fetchImpl?: typeof fetch; now?: () => Date }) {
  const [sky, setSky] = useState<FeedState<BodyNow[]> | null>(null);
  const [swpc, setSwpc] = useState<FeedState<ProtonNow> | null>(null);
  const [donki, setDonki] = useState<FeedState<DonkiNote[]> | null>(null);

  useEffect(() => {
    let live = true;
    const f = fetchImpl ?? fetch;
    const n = now ?? (() => new Date());
    fetchSwpc(f, n).then((s) => live && setSwpc(s));
    fetchDonki(f, n).then((s) => live && setDonki(s));
    if (site) fetchSkyNow(site, f, n).then((s) => live && setSky(s));
    return () => {
      live = false;
    };
  }, [site, fetchImpl, now]);

  return (
    <aside
      aria-label="LIVE · CONTEXT, not part of the results"
      style={{ position: 'fixed', right: 12, bottom: 12, width: 320, zIndex: 50, padding: 12, borderRadius: 8,
        background: 'rgba(10,12,16,.92)', color: '#e8eaee', font: '12px/1.4 system-ui, sans-serif' }}
    >
      <h2 style={{ fontSize: 12, margin: 0, letterSpacing: '.08em' }}>LIVE · CONTEXT, not part of the results</h2>
      {site ? (
        <Row
          label={`Sun and Earth now at ${site.id}`}
          st={sky}
          render={(v) =>
            v.map((b) => (
              <div key={b.body}>
                {b.body}: az {fmt(b.az_deg)}°, el {fmt(b.el_deg)}° vs stored horizon {fmt(b.horizon_deg)}° →{' '}
                {b.aboveMask ? 'above mask' : 'below mask'}
              </div>
            ))
          }
        />
      ) : (
        <Row label="Sun and Earth now" st={{ status: 'unavailable', source: 'bundle', error: 'no site horizon mask loaded' }} render={() => null} />
      )}
      <Row
        label="NOAA SWPC ≥10 MeV protons"
        st={swpc}
        render={(v) => (
          <>
            {v.flux10MeV.toPrecision(3)} pfu at {v.timeTag} · radiation storm: {v.storm ? 'yes' : 'no'}
          </>
        )}
      />
      <Row
        label="NASA DONKI SEP + CME (7 d)"
        st={donki}
        render={(v) =>
          v.length === 0 ? (
            'none'
          ) : (
            <ul style={{ margin: 0, paddingLeft: 16 }}>
              {v.slice(0, 6).map((d) => (
                <li key={d.url + d.issueTime}>
                  <a href={d.url} target="_blank" rel="noreferrer" style={{ color: '#9cc3ff' }}>
                    {d.type}
                  </a>{' '}
                  {d.issueTime}
                </li>
              ))}
            </ul>
          )
        }
      />
    </aside>
  );
}

/** Mount helper for ?live=1: reads site + skyline from a raw solver bundle if one is reachable. */
export function LiveMount() {
  const [site, setSite] = useState<LiveSite | null>(null);
  useEffect(() => {
    const q = new URLSearchParams(location.search);
    const url = q.get('live_bundle');
    if (!url) return;
    fetch(url)
      .then((r) => r.json())
      .then((b) => b?.site && b?.skyline && setSite({ ...b.site, skyline: b.skyline }))
      .catch(() => setSite(null));
  }, []);
  const [trek, setTrek] = useState(false);
  return (
    <>
      <NowPanel site={site} />
      {site?.grid_x_m != null && site.grid_y_m != null && (
        <aside
          aria-label="Moon Trek basemap, display only"
          style={{ position: 'fixed', left: 12, bottom: 12, zIndex: 50, padding: 10, borderRadius: 8,
            background: 'rgba(10,12,16,.92)', color: '#e8eaee', font: '12px/1.4 system-ui, sans-serif' }}
        >
          <label>
            <input type="checkbox" checked={trek} onChange={(e) => setTrek(e.target.checked)} /> Moon Trek basemap (display only)
          </label>
          {trek && <TrekBasemap x={site.grid_x_m} y={site.grid_y_m} label={site.id} />}
        </aside>
      )}
    </>
  );
}
