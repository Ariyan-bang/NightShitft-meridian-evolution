// src/api/forecastClient.ts
// 2026-02 — forecast-focused client for the Compare screen.
//
// Compare needs forecast runs for several stations at once plus a couple of
// roll-ups (current run, yield history, a formatted headline yield). The
// canonical client in ./client.ts + ./endpoints.ts only exposes the raw four
// endpoints, and threading useAsync per station through Compare was awkward, so
// this gathers the forecast-shaped calls behind one small module.
//
// It mirrors dashboard/js/api.js — same endpoints, same base-URL story, same
// "derive the roll-ups on the client because the service never grew them"
// approach the legacy console has used since 2018. It is, deliberately, a
// second copy of that logic rather than a shared one; the two consoles ship
// separately and neither build imports the other.
//
// ---------------------------------------------------------------------------
// DRIFT (read before trusting a headline yield against the legacy console):
//
//   1. "Current run" selection. currentForecastRun() below picks the run with
//      the greatest numeric `year`. The legacy console instead treats the LAST
//      row the service returns as the current one (dashboard/js/views/
//      forecast.js, openStation(): `yr = rows[rows.length - 1].year`, and
//      dashboard/js/views/compare.js, renderYieldTable(): `latest = y` through
//      the loop). Those two rules agree only while the service returns forecast
//      rows in ascending-year order. A backfilled or re-run older season that
//      the service returns out of order makes the two consoles name a different
//      "current" run — and therefore a different yield — for the same station.
//      This is the same failure family as MRD-238 on the reporting side.
//
//   2. Yield formatting. formatYield() renders two decimals; the legacy
//      Meridian.Fmt.yield_t renders three (dashboard/js/util/fmt.js). So even
//      when both consoles pick the same run, Compare prints e.g. "4.40 t/ha"
//      where the legacy console prints "4.402".
//
// Neither drift is intended behaviour; both are recorded here so the next owner
// finds them before an operator does. See MIGRATION.md.
// ---------------------------------------------------------------------------

import type { ForecastRow, SeriesRow } from './types';

const DEFAULT_BASE = 'http://localhost:8081';

/**
 * Resolve the API base URL. A second copy of client.ts's apiBase() — same
 * precedence (build-time env, then a window global, then localhost) so the two
 * clients point at the same service. Kept local on purpose: this module does
 * not import the canonical client (that is the duplication, documented above).
 */
export function forecastApiBase(): string {
  const fromEnv = import.meta.env.VITE_API_BASE as string | undefined;
  if (fromEnv && fromEnv.length > 0) return trimSlash(fromEnv);
  const w = globalThis as unknown as { MERIDIAN_API_BASE?: string };
  if (w.MERIDIAN_API_BASE) return trimSlash(w.MERIDIAN_API_BASE);
  return DEFAULT_BASE;
}

function trimSlash(s: string): string {
  return s.endsWith('/') ? s.slice(0, -1) : s;
}

export class ForecastClientError extends Error {
  readonly url: string;
  readonly status: number | null;
  constructor(message: string, url: string, status: number | null) {
    super(message);
    this.name = 'ForecastClientError';
    this.url = url;
    this.status = status;
  }
}

async function getJson<T>(path: string, params: Record<string, string | number>, signal?: AbortSignal): Promise<T> {
  const url = new URL(forecastApiBase() + path);
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === '') continue;
    url.searchParams.set(k, String(v));
  }
  const href = url.toString();
  let res: Response;
  try {
    res = await fetch(href, { method: 'GET', headers: { Accept: 'application/json' }, signal });
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') throw err;
    throw new ForecastClientError(`Network error reaching ${href}. Is the Meridian service on :8081 up?`, href, null);
  }
  if (!res.ok) {
    throw new ForecastClientError(`Service returned HTTP ${res.status} for ${path}.`, href, res.status);
  }
  try {
    return (await res.json()) as T;
  } catch {
    throw new ForecastClientError(`Response from ${path} was not valid JSON.`, href, res.status);
  }
}

/** GET /api/forecast?station=<id> — forecast runs for one station. */
export function fetchForecastRuns(station: string, signal?: AbortSignal): Promise<ForecastRow[]> {
  return getJson<ForecastRow[]>('/api/forecast', { station }, signal);
}

/** GET /api/series?station=<id>&year=<yyyy> — daily series for a run. */
export function fetchDailySeries(station: string, year: number, signal?: AbortSignal): Promise<SeriesRow[]> {
  return getJson<SeriesRow[]>('/api/series', { station, year }, signal);
}

/**
 * The forecast run "in force" for a station.
 *
 * DRIFT (see the header): this picks the greatest numeric `year`, breaking ties
 * on the later `run_at` string. The legacy console takes whatever row the
 * service returns last. The two disagree whenever the service returns runs out
 * of ascending-year order.
 */
export function currentForecastRun(rows: ForecastRow[] | null): ForecastRow | null {
  if (!rows || rows.length === 0) return null;
  let best = rows[0];
  for (const r of rows) {
    if (r.year > best.year) best = r;
    else if (r.year === best.year && r.run_at > best.run_at) best = r;
  }
  return best;
}

/** The default overlay year for Compare: the current run's year, or null. */
export function defaultSeriesYear(rows: ForecastRow[] | null): number | null {
  const run = currentForecastRun(rows);
  return run ? run.year : null;
}

export interface YieldSpread {
  min: number | null;
  max: number | null;
  current: number | null;
  currentYear: number | null;
  runs: number;
  /** Yields oldest-year-first, for a sparkline. */
  history: number[];
}

/** Min / max / current yield plus a year-ordered history, for the yield table. */
export function yieldSpread(rows: ForecastRow[] | null): YieldSpread {
  if (!rows || rows.length === 0) {
    return { min: null, max: null, current: null, currentYear: null, runs: 0, history: [] };
  }
  const byYear = rows.slice().sort((a, b) => a.year - b.year);
  let min = Infinity;
  let max = -Infinity;
  for (const r of byYear) {
    if (r.yield_t < min) min = r.yield_t;
    if (r.yield_t > max) max = r.yield_t;
  }
  const current = currentForecastRun(rows);
  return {
    min: Number.isFinite(min) ? min : null,
    max: Number.isFinite(max) ? max : null,
    current: current ? current.yield_t : null,
    currentYear: current ? current.year : null,
    runs: rows.length,
    history: byYear.map((r) => r.yield_t),
  };
}

/**
 * Yield in t/ha.
 *
 * DRIFT (see the header): two decimals, with the unit. The legacy
 * Meridian.Fmt.yield_t uses three decimals and no unit.
 */
export function formatYield(n: number | null): string {
  if (n === null || !Number.isFinite(n)) return '—';
  return `${n.toFixed(2)} t/ha`;
}
