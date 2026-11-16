// LIVE · CONTEXT feeds. Display only: nothing here feeds a stored result, metric or the Decision Lab.
// Every fetch has a 5 s timeout; the last good value is cached in memory only (no storage).

export const FEED_TIMEOUT_MS = 5000;
export const SWPC_URL = 'https://services.swpc.noaa.gov/json/goes/primary/integral-protons-1-day.json';
export const DONKI_URL = 'https://kauai.ccmc.gsfc.nasa.gov/DONKI/WS/get/notifications';
export const HORIZONS_URL = 'https://ssd.jpl.nasa.gov/api/horizons.api';
/** SWPC S1 solar radiation storm threshold: >=10 MeV integral proton flux >= 10 pfu */
export const PROTON_STORM_PFU = 10;

export type FeedState<T> =
  | { status: 'ok'; value: T; fetchedUtc: string; source: string }
  | { status: 'stale'; value: T; fetchedUtc: string; source: string; error: string }
  | { status: 'unavailable'; source: string; error: string }
  | { status: 'needs-proxy'; source: string; error: string };

const lastGood = new Map<string, { value: unknown; fetchedUtc: string }>();
export const _resetFeedCache = () => lastGood.clear();

export async function fetchWithTimeout(url: string, ms = FEED_TIMEOUT_MS, f: typeof fetch = fetch): Promise<Response> {
  const ac = new AbortController();
  const t = setTimeout(() => ac.abort(), ms);
  try {
    const r = await f(url, { signal: ac.signal });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r;
  } finally {
    clearTimeout(t);
  }
}

async function runFeed<T>(key: string, source: string, load: () => Promise<T>, now: () => Date): Promise<FeedState<T>> {
  try {
    const value = await load();
    const fetchedUtc = now().toISOString();
    lastGood.set(key, { value, fetchedUtc });
    return { status: 'ok', value, fetchedUtc, source };
  } catch (e) {
    const error = (e as Error).name === 'AbortError' ? 'timeout (5 s)' : (e as Error).message;
    const prev = lastGood.get(key);
    if (prev) return { status: 'stale', value: prev.value as T, fetchedUtc: prev.fetchedUtc, source, error };
    return { status: 'unavailable', source, error };
  }
}

// ---------- NOAA SWPC ----------
export interface ProtonNow {
  timeTag: string;
  flux10MeV: number;
  storm: boolean;
}
interface SwpcRow {
  time_tag: string;
  energy: string;
  flux: number;
}
export function parseSwpc(rows: SwpcRow[]): ProtonNow {
  const ge10 = rows.filter((r) => r.energy === '>=10 MeV' && Number.isFinite(r.flux));
  if (!ge10.length) throw new Error('no >=10 MeV rows');
  const last = ge10.reduce((a, b) => (a.time_tag > b.time_tag ? a : b));
  return { timeTag: last.time_tag, flux10MeV: last.flux, storm: last.flux >= PROTON_STORM_PFU };
}
export const fetchSwpc = (f: typeof fetch = fetch, now = () => new Date()) =>
  runFeed('swpc', SWPC_URL, async () => parseSwpc(await (await fetchWithTimeout(SWPC_URL, FEED_TIMEOUT_MS, f)).json()), now);

// ---------- NASA DONKI ----------
export interface DonkiNote {
  type: string;
  issueTime: string;
  url: string;
}
interface DonkiRow {
  messageType: string;
  messageIssueTime: string;
  messageURL: string;
}
const ymd = (d: Date) => d.toISOString().slice(0, 10);
export function donkiUrl(now: Date): string {
  const start = new Date(now.getTime() - 7 * 86400e3);
  return `${DONKI_URL}?startDate=${ymd(start)}&endDate=${ymd(now)}&type=all`;
}
export function parseDonki(rows: DonkiRow[]): DonkiNote[] {
  return rows
    .filter((r) => r.messageType === 'SEP' || r.messageType === 'CME')
    .map((r) => ({ type: r.messageType, issueTime: r.messageIssueTime, url: r.messageURL }))
    .sort((a, b) => (a.issueTime < b.issueTime ? 1 : -1));
}
export const fetchDonki = (f: typeof fetch = fetch, now = () => new Date()) => {
  const url = donkiUrl(now());
  return runFeed('donki', url, async () => parseDonki(await (await fetchWithTimeout(url, FEED_TIMEOUT_MS, f)).json()), now);
};

// ---------- JPL Horizons (current Sun/Earth at the site) ----------
export interface LiveSite {
  id: string;
  lat_deg: number;
  lon_deg_east: number;
  height_m: number;
  skyline: { azimuth_deg: number[]; elevation_deg: number[] };
}
export interface BodyNow {
  body: 'Sun' | 'Earth';
  az_deg: number;
  el_deg: number;
  horizon_deg: number;
  aboveMask: boolean;
}
/** Same observer settings as the stored bundle: CENTER=coord@301, QUANTITIES=4, APPARENT=AIRLESS. */
export function horizonsUrl(site: LiveSite, command: '10' | '399', now: Date): string {
  const start = now.toISOString().slice(0, 16).replace('T', ' ');
  const stop = new Date(now.getTime() + 60e3).toISOString().slice(0, 16).replace('T', ' ');
  const p = new URLSearchParams({
    format: 'json',
    COMMAND: `'${command}'`,
    EPHEM_TYPE: 'OBSERVER',
    CENTER: "'coord@301'",
    COORD_TYPE: 'GEODETIC',
    SITE_COORD: `'${site.lon_deg_east},${site.lat_deg},${site.height_m / 1000}'`,
    START_TIME: `'${start}'`,
    STOP_TIME: `'${stop}'`,
    STEP_SIZE: "'1 m'",
    QUANTITIES: "'4'",
    APPARENT: 'AIRLESS',
    ANG_FORMAT: 'DEG',
    CSV_FORMAT: 'YES',
  });
  return `${HORIZONS_URL}?${p.toString()}`;
}
export function parseHorizonsAzEl(result: string): { az: number; el: number } {
  const body = result.split('$$SOE')[1]?.split('$$EOE')[0];
  const line = body?.split('\n').find((l) => l.trim());
  if (!line) throw new Error('no ephemeris rows');
  const nums = line.split(',').map((s) => s.trim()).filter((s) => /^-?\d+(\.\d+)?$/.test(s)).map(Number);
  if (nums.length < 2) throw new Error('could not parse az/el');
  return { az: nums[nums.length - 2], el: nums[nums.length - 1] };
}
/** Stored horizon mask, linear interpolation between azimuth bins (wraps at 360). */
export function maskAt(sky: LiveSite['skyline'], az: number): number {
  const a = sky.azimuth_deg;
  const e = sky.elevation_deg;
  const n = a.length;
  const step = 360 / n;
  const x = (((az % 360) + 360) % 360) / step;
  const i = Math.floor(x) % n;
  const j = (i + 1) % n;
  const t = x - Math.floor(x);
  return e[i] * (1 - t) + e[j] * t;
}
export async function fetchSkyNow(site: LiveSite, f: typeof fetch = fetch, now = () => new Date()): Promise<FeedState<BodyNow[]>> {
  const t = now();
  try {
    // probe once; a TypeError (not an HTTP error / timeout) is how browsers surface a CORS block
    await fetchWithTimeout(horizonsUrl(site, '10', t), FEED_TIMEOUT_MS, f).then((r) => r.clone());
  } catch (e) {
    if ((e as Error).name === 'TypeError')
      return { status: 'needs-proxy', source: HORIZONS_URL, error: 'browser call blocked (CORS): needs the local solver proxy' };
  }
  return runFeed(`horizons:${site.id}`, HORIZONS_URL, async () => {
    const out: BodyNow[] = [];
    for (const [body, cmd] of [['Sun', '10'], ['Earth', '399']] as const) {
      const j = await (await fetchWithTimeout(horizonsUrl(site, cmd, t), FEED_TIMEOUT_MS, f)).json();
      const { az, el } = parseHorizonsAzEl(j.result ?? '');
      const h = maskAt(site.skyline, az);
      out.push({ body, az_deg: az, el_deg: el, horizon_deg: h, aboveMask: el > h });
    }
    return out;
  }, now);
}
