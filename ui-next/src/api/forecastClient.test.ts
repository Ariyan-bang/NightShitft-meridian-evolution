// src/api/forecastClient.test.ts
// 2026-02 — specs for the forecast roll-up helpers, and a pin on the drift.
//
// Written for Vitest, which is still not installed (see MIGRATION.md, debt
// item 4). `npm test` does not run them yet. They are kept as an executable
// spec — in particular the "drift" block below PINS the two places this client
// diverges from the legacy console so the divergence is intentional and
// greppable, not an accident waiting to be "fixed" in one console only.

import { describe, it, expect } from 'vitest';
import {
  currentForecastRun,
  defaultSeriesYear,
  yieldSpread,
  formatYield,
} from './forecastClient';
import type { ForecastRow } from './types';

function run(year: number, yield_t: number, run_at: string): ForecastRow {
  return { stnid: 'GUELPH', year, yield_t, ndays: 120, model: 'cropmod-1.4', run_at };
}

describe('currentForecastRun', () => {
  it('returns null for empty / null input', () => {
    expect(currentForecastRun(null)).toBeNull();
    expect(currentForecastRun([])).toBeNull();
  });

  it('picks the greatest numeric year', () => {
    const rows = [run(2021, 4.1, '2021-07-01T02:00:00'), run(2023, 4.4, '2023-07-01T02:00:00')];
    expect(currentForecastRun(rows)?.year).toBe(2023);
  });

  it('breaks a year tie on the later run_at', () => {
    const rows = [run(2023, 4.4, '2023-07-01T02:00:00'), run(2023, 4.6, '2023-07-02T02:00:00')];
    expect(currentForecastRun(rows)?.yield_t).toBe(4.6);
  });
});

describe('yieldSpread', () => {
  it('reports min / max / current and a year-ordered history', () => {
    const rows = [run(2022, 5.0, '2022-07-01T02:00:00'), run(2021, 3.0, '2021-07-01T02:00:00')];
    const s = yieldSpread(rows);
    expect(s.min).toBe(3.0);
    expect(s.max).toBe(5.0);
    expect(s.current).toBe(5.0);
    expect(s.currentYear).toBe(2022);
    expect(s.history).toEqual([3.0, 5.0]); // oldest-year first
    expect(s.runs).toBe(2);
  });
});

// --- DRIFT PINS: do not "fix" one console without the other ---------------
describe('drift from the legacy console (intentional, documented)', () => {
  it('selects the current run by MAX YEAR, not by last-returned row', () => {
    // The legacy console takes rows[rows.length - 1] as current. Here a
    // backfilled older run is returned last; the two consoles disagree.
    const rows = [
      run(2023, 4.4, '2023-07-01T02:00:00'),
      run(2021, 3.1, '2026-01-15T09:00:00'), // backfill, returned last
    ];
    expect(currentForecastRun(rows)?.year).toBe(2023); // this client
    expect(rows[rows.length - 1].year).toBe(2021); // the legacy rule
    expect(defaultSeriesYear(rows)).toBe(2023);
  });

  it('formats yield to TWO decimals with a unit (legacy uses three, no unit)', () => {
    expect(formatYield(4.4021)).toBe('4.40 t/ha');
    // legacy Meridian.Fmt.yield_t(4.4021) === '4.402'
  });

  it('formats a missing yield as an em dash', () => {
    expect(formatYield(null)).toBe('—');
    expect(formatYield(NaN)).toBe('—');
  });
});
