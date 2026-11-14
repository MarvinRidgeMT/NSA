import { create } from 'zustand';
import { BundleError, loadBundleBytes } from '../bundle/validate';
import { bracket, CoverageError } from '../bundle/sampling';
import type { BundleIndexEntry, LoadedBundle } from '../bundle/types';

/**
 * ONE store. UTC time, site (dataset) and scenario live here and nothing else
 * holds its own copy: every chart, strip, panel and the 3D view derive from it.
 */
export interface PolarisState {
  index: BundleIndexEntry[];
  loaded: LoadedBundle | null;
  loading: boolean;
  loadError: string | null;
  datasetIdx: number;
  scenarioId: string | null;
  utcMs: number | null;
  timeError: string | null;
  selectedFailureId: string | null;
  playing: boolean;

  setIndex: (e: BundleIndexEntry[]) => void;
  loadFromUrl: (url: string, name: string, origin: string) => Promise<void>;
  loadFromFile: (f: File) => Promise<void>;
  setSite: (i: number) => void;
  setScenario: (id: string) => void;
  setTime: (ms: number) => boolean;
  stepSample: (delta: number) => void;
  setSampleIndex: (i: number) => void;
  selectFailure: (id: string | null) => void;
  setPlaying: (p: boolean) => void;
}

function timesOf(s: PolarisState): number[] {
  return s.loaded?.times[s.datasetIdx] ?? [];
}

export const usePolaris = create<PolarisState>((set, get) => {
  const adopt = (lb: LoadedBundle) => {
    const ds = lb.bundle.datasets[0];
    set({
      loaded: lb,
      loading: false,
      loadError: null,
      datasetIdx: 0,
      scenarioId: ds.derived?.scenarios[0]?.id ?? null,
      utcMs: lb.times[0][0],
      timeError: null,
      selectedFailureId: null,
      playing: false,
    });
  };
  const failLoad = (e: unknown) =>
    set({ loading: false, loadError: e instanceof BundleError ? e.message : `Could not load bundle: ${(e as Error).message}` });

  return {
    index: [],
    loaded: null,
    loading: false,
    loadError: null,
    datasetIdx: 0,
    scenarioId: null,
    utcMs: null,
    timeError: null,
    selectedFailureId: null,
    playing: false,

    setIndex: (index) => set({ index }),

    loadFromUrl: async (url, name, origin) => {
      set({ loading: true, loadError: null });
      try {
        const r = await fetch(url);
        if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`);
        adopt(await loadBundleBytes(await r.arrayBuffer(), name, origin));
      } catch (e) {
        failLoad(e);
      }
    },

    loadFromFile: async (f) => {
      set({ loading: true, loadError: null });
      try {
        adopt(await loadBundleBytes(await f.arrayBuffer(), f.name, 'local file'));
      } catch (e) {
        failLoad(e);
      }
    },

    setSite: (i) => {
      const lb = get().loaded;
      if (!lb || i < 0 || i >= lb.bundle.datasets.length) return;
      const ds = lb.bundle.datasets[i];
      const times = lb.times[i];
      const cur = get().utcMs;
      const keep = cur !== null && cur >= times[0] && cur <= times[times.length - 1];
      set({
        datasetIdx: i,
        scenarioId: ds.derived?.scenarios[0]?.id ?? null,
        utcMs: keep ? cur : times[0],
        timeError: null,
        selectedFailureId: null,
      });
    },

    setScenario: (id) => set({ scenarioId: id, selectedFailureId: null }),

    /** Refuses (returns false, sets timeError) for any time outside coverage. */
    setTime: (ms) => {
      try {
        bracket(timesOf(get()), ms);
        set({ utcMs: ms, timeError: null });
        return true;
      } catch (e) {
        set({ timeError: e instanceof CoverageError ? `Refused: ${e.message}. The viewer never extrapolates.` : String(e) });
        return false;
      }
    },

    setSampleIndex: (i) => {
      const t = timesOf(get());
      if (!t.length) return;
      const k = Math.max(0, Math.min(t.length - 1, i));
      set({ utcMs: t[k], timeError: null });
    },

    stepSample: (delta) => {
      const s = get();
      const t = timesOf(s);
      if (!t.length || s.utcMs === null) return;
      const br = bracket(t, s.utcMs);
      const base = br.exact ?? (delta > 0 ? br.i0 : br.i1);
      get().setSampleIndex(base + delta);
    },

    selectFailure: (id) => {
      const s = get();
      if (!id) return set({ selectedFailureId: null });
      const sc = s.loaded?.bundle.datasets[s.datasetIdx].derived?.scenarios.find((x) => x.id === s.scenarioId);
      const f = sc?.failures.find((x) => x.id === id);
      if (!f) return;
      set({ selectedFailureId: id, playing: false });
      get().setSampleIndex(f.sampleIndex);
    },

    setPlaying: (playing) => set({ playing }),
  };
});
