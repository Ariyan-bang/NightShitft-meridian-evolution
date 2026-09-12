// src/util/quality.ts
// 2026-02 — client-side quality flags for the Anomalies screen.
//
// The service has never carried a per-reading quality flag (the Anomalies
// screen was originally scoped against a GET /api/anomalies that the Java
// service never grew — see the TODO at the bottom of api/endpoints.ts). The
// legacy console solved this years ago by deriving the flags on the client from
// the agronomy group's physical bounds, so Anomalies does the same rather than
// wait on an endpoint that is not coming.
//
// The thresholds and the flag logic are a hand-transcription of
// dashboard/js/views/quality.js (Meridian.Quality.RULES) and the deriveFlags()
// in dashboard/js/api.js. They are copied, not shared — the two consoles build
// separately. If agronomy revises a bound, it must be changed in BOTH places.
// The values here match the legacy console as of the 2019-08 revision (ET
// ceiling raised 10 -> 12 after the drought-year calibration).

import type { SeriesRow } from '../api/types';

export interface QualityRules {
  swMin: number;
  swMax: number;
  etMin: number;
  etMax: number;
  drainMin: number;
  laiMin: number;
  laiMax: number;
  /** A day-over-day biomass drop beyond this fraction is suspect. */
  biomDropFrac: number;
}

/** Physical bounds, agronomy group 2017-03 memo, revised 2019-08. */
export const RULES: QualityRules = {
  swMin: 0,
  swMax: 400,
  etMin: 0,
  etMax: 12,
  drainMin: 0,
  laiMin: 0,
  laiMax: 9,
  biomDropFrac: 0.15,
};

export type FlagCode = 'sw-range' | 'et-range' | 'drain-neg' | 'lai-range' | 'biom-drop';

/** Human-readable descriptions, matching the legacy FLAG_LABELS. */
export const FLAG_LABELS: Record<FlagCode, string> = {
  'sw-range': 'Soil water out of range',
  'et-range': 'ET out of range',
  'drain-neg': 'Negative drainage',
  'lai-range': 'LAI out of range',
  'biom-drop': 'Biomass drop > 15%',
};

/** Stable display/filter order for the flag codes. */
export const FLAG_ORDER: FlagCode[] = ['sw-range', 'et-range', 'drain-neg', 'lai-range', 'biom-drop'];

/** Which series field a flag is attributed to, for per-field tallies. */
export const FLAG_FIELD: Record<FlagCode, keyof SeriesRow> = {
  'sw-range': 'sw',
  'et-range': 'et',
  'drain-neg': 'drain',
  'lai-range': 'lai',
  'biom-drop': 'biom',
};

/**
 * Derive the flags for one row given the previous row's biomass (for the
 * day-over-day drop rule). A faithful port of dashboard/js/api.js deriveFlags.
 */
export function deriveFlags(row: SeriesRow, prevBiom: number | null, rules: QualityRules = RULES): FlagCode[] {
  const flags: FlagCode[] = [];
  if (row.sw < rules.swMin || row.sw > rules.swMax) flags.push('sw-range');
  if (row.et < rules.etMin || row.et > rules.etMax) flags.push('et-range');
  if (row.drain < rules.drainMin) flags.push('drain-neg');
  if (row.lai < rules.laiMin || row.lai > rules.laiMax) flags.push('lai-range');
  if (prevBiom !== null && prevBiom > 0 && (prevBiom - row.biom) / prevBiom > rules.biomDropFrac) {
    flags.push('biom-drop');
  }
  return flags;
}

/** A series row annotated with its flags. */
export interface FlaggedRow extends SeriesRow {
  flags: FlagCode[];
  suspect: boolean;
}

/**
 * Annotate a whole series with flags. Mirrors MeridianApi.anomalies(): the
 * biomass-drop rule needs the previous row, so order matters — the series is
 * assumed to be in ascending DOY order (MRD-118).
 */
export function annotate(rows: SeriesRow[]): FlaggedRow[] {
  const out: FlaggedRow[] = [];
  let prevBiom: number | null = null;
  for (const r of rows) {
    const flags = deriveFlags(r, prevBiom);
    out.push({ ...r, flags, suspect: flags.length > 0 });
    prevBiom = r.biom;
  }
  return out;
}

/** Count how many rows trip each flag code. */
export function flagCounts(rows: FlaggedRow[]): Record<FlagCode, number> {
  const counts = { 'sw-range': 0, 'et-range': 0, 'drain-neg': 0, 'lai-range': 0, 'biom-drop': 0 };
  for (const r of rows) {
    for (const f of r.flags) counts[f] += 1;
  }
  return counts;
}
