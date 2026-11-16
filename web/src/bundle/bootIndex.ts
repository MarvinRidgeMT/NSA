import type { BundleIndexEntry } from './types';

/**
 * Cold-launch loading of `bundles/index.json` (Final Apex P1, 15 Nov 2026).
 *
 * Every failure has its own message, because the remedy differs:
 *  - the page was opened as a file (file://), where browsers refuse fetch(): serve the folder instead;
 *  - the server answered 404: the build has no bundles (run `npm run sync-bundles`, or serve `web/dist`, not the repo root);
 *  - the server answered with HTML (a single-page fallback, or the wrong folder) instead of JSON;
 *  - the JSON is malformed, or lists no bundles.
 * There is never a fallback to a demo or another bundle: an empty or broken index is an error, shown with Retry.
 */
export type IndexProblem = 'file-protocol' | 'network' | 'http' | 'not-json' | 'bad-json' | 'bad-shape' | 'empty';

export class IndexError extends Error {
  constructor(
    readonly problem: IndexProblem,
    message: string,
    readonly url: string,
  ) {
    super(message);
  }
}

const FIX = 'Start the viewer with `npm run preview` (or `npm run dev`) inside `web/`, or open a bundle file below.';

/** Validate the body of bundles/index.json. Pure: unit-tested without a server. */
export function parseIndex(text: string, contentType: string | null, url: string): BundleIndexEntry[] {
  const head = text.trimStart().slice(0, 64).toLowerCase();
  if (head.startsWith('<!doctype') || head.startsWith('<html') || (contentType ?? '').includes('text/html'))
    throw new IndexError(
      'not-json',
      `The server answered ${url} with a web page, not the bundle index. It is probably serving the wrong folder (it must serve web/dist or web/public). ${FIX}`,
      url,
    );
  let j: unknown;
  try {
    j = JSON.parse(text);
  } catch (e) {
    throw new IndexError('bad-json', `bundles/index.json is not valid JSON (${(e as Error).message}). Run \`npm run sync-bundles\` to rewrite it.`, url);
  }
  const list = (j as { bundles?: unknown })?.bundles;
  if (!Array.isArray(list))
    throw new IndexError('bad-shape', 'bundles/index.json has no "bundles" list. Run `npm run sync-bundles` to rewrite it.', url);
  const ok = list.filter(
    (b): b is BundleIndexEntry => !!b && typeof (b as BundleIndexEntry).file === 'string' && /^[\w.-]+\.json$/.test((b as BundleIndexEntry).file),
  );
  if (ok.length !== list.length)
    throw new IndexError('bad-shape', `bundles/index.json has ${list.length - ok.length} entr${list.length - ok.length === 1 ? 'y' : 'ies'} without a plain .json file name.`, url);
  if (ok.length === 0) throw new IndexError('empty', `bundles/index.json lists no bundles. Run \`npm run sync-bundles\`, or open a bundle file below.`, url);
  return ok;
}

/** Fetch and validate the index. Never cached: a stale index after a rebuild was one cause of the old cold-launch error. */
export async function fetchIndex(href = 'bundles/index.json'): Promise<BundleIndexEntry[]> {
  const url = new URL(href, document.baseURI).href;
  if (location.protocol === 'file:')
    throw new IndexError(
      'file-protocol',
      `This page was opened directly from disk (file://), and browsers block it from reading bundles/index.json. ${FIX}`,
      url,
    );
  let r: Response;
  try {
    r = await fetch(href, { cache: 'no-store' });
  } catch (e) {
    throw new IndexError('network', `Could not reach ${url} (${(e as Error).message}). Is the viewer's server still running? ${FIX}`, url);
  }
  if (!r.ok)
    throw new IndexError(
      'http',
      r.status === 404
        ? `No bundles/index.json at ${url} (HTTP 404). Run \`npm run sync-bundles\` and rebuild, or serve web/dist rather than the repository root.`
        : `bundles/index.json: HTTP ${r.status} from ${url}.`,
      url,
    );
  return parseIndex(await r.text(), r.headers.get('content-type'), url);
}
