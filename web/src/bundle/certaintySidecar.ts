/**
 * Certainty Height sidecar (format polaris-certainty-sidecar-v1), written by tools/certainty/build_certainty_sidecar.py from
 * the committed batch sweep CSVs (a-science data/batch/2026-11-14/certainty_height*). Interim source for the Certainty Height
 * panel until the science branch writes A2 (`derived.certainty_curve`) into the bundles: a bundle's own block always wins.
 * The viewer copies these values; it computes none of them.
 */
import { normalizeCertainty } from './scienceV2';
import type { CertaintyCurve } from './types';

export interface CertaintySidecar {
  format: 'polaris-certainty-sidecar-v1';
  status: string;
  generated_by?: string;
  source: { what: string; repo_branch?: string; repo_commit?: string; solver_note?: string; files: { path: string; sha256: string }[] };
  requirements: unknown;
  agreement_tolerance_p: number;
  definitions?: Record<string, string>;
  sites: Record<string, { sampled_masts_m: number[]; certainty_curve: unknown; certainty_height_m: Record<string, number | null>; agreement_mast_m: number | null; all_maps_100pct_sun_mast_m: number | null }>;
}

export interface SidecarCurve {
  curve: CertaintyCurve;
  source: CertaintySidecar['source'];
  status: string;
  allMaps100PctSunMastM: number | null;
}

export function parseSidecar(raw: unknown): CertaintySidecar | null {
  const r = raw as CertaintySidecar | null;
  if (!r || r.format !== 'polaris-certainty-sidecar-v1' || !r.sites || typeof r.sites !== 'object' || !Array.isArray(r.source?.files)) return null;
  return r;
}

/** The sidecar's curve for one site id (e.g. "site04_roi3"), in the same normalized shape as a bundle's A2 block. */
export function sidecarCurveFor(sc: CertaintySidecar | null, siteId: string): SidecarCurve | null {
  const s = sc?.sites[siteId];
  if (!sc || !s) return null;
  const curve = normalizeCertainty(s.certainty_curve, s.certainty_height_m, sc.requirements);
  curve.method = 'polaris_batch mast sweep, nominal + 20 PGDA 78 clones (batch CSV, not this bundle\u2019s solver)';
  curve.agreementMastM = s.agreement_mast_m;
  curve.agreementToleranceP = sc.agreement_tolerance_p;
  return { curve, source: sc.source, status: sc.status, allMaps100PctSunMastM: s.all_maps_100pct_sun_mast_m };
}
