// src/util/quality.test.ts
// 2026-02 — specs for the client-side quality flags.
//
// Written for Vitest, which is not installed (see MIGRATION.md, debt item 4).
// Pins the thresholds and the flag logic against the legacy console's ruleset,
// since the two consoles carry their own copy and must agree.

import { describe, it, expect } from 'vitest';
import { deriveFlags, annotate, flagCounts, RULES } from './quality';
import type { SeriesRow } from '../api/types';

function row(partial: Partial<SeriesRow>): SeriesRow {
  return { doy: 100, sw: 120, et: 4, drain: 1, biom: 2000, lai: 3, ...partial };
}

describe('deriveFlags', () => {
  it('flags nothing for an in-bounds row', () => {
    expect(deriveFlags(row({}), null)).toEqual([]);
  });

  it('flags soil water out of range at either end', () => {
    expect(deriveFlags(row({ sw: -1 }), null)).toContain('sw-range');
    expect(deriveFlags(row({ sw: RULES.swMax + 1 }), null)).toContain('sw-range');
  });

  it('flags ET above the 2019 ceiling of 12', () => {
    expect(deriveFlags(row({ et: 12.5 }), null)).toContain('et-range');
    expect(deriveFlags(row({ et: 12 }), null)).not.toContain('et-range');
  });

  it('flags negative drainage', () => {
    expect(deriveFlags(row({ drain: -0.1 }), null)).toContain('drain-neg');
  });

  it('flags LAI out of range', () => {
    expect(deriveFlags(row({ lai: 9.1 }), null)).toContain('lai-range');
  });

  it('flags a >15% day-over-day biomass drop, needing the previous row', () => {
    expect(deriveFlags(row({ biom: 800 }), 1000)).toContain('biom-drop'); // -20%
    expect(deriveFlags(row({ biom: 900 }), 1000)).not.toContain('biom-drop'); // -10%
    expect(deriveFlags(row({ biom: 800 }), null)).not.toContain('biom-drop'); // no prev
  });
});

describe('annotate', () => {
  it('carries biomass across rows for the drop rule and marks suspect', () => {
    const series = [row({ doy: 1, biom: 1000 }), row({ doy: 2, biom: 700 })];
    const flagged = annotate(series);
    expect(flagged[0].suspect).toBe(false);
    expect(flagged[1].suspect).toBe(true);
    expect(flagged[1].flags).toContain('biom-drop');
  });

  it('tallies flag counts across the series', () => {
    const series = [row({ doy: 1, et: 20 }), row({ doy: 2, drain: -1 }), row({ doy: 3 })];
    const counts = flagCounts(annotate(series));
    expect(counts['et-range']).toBe(1);
    expect(counts['drain-neg']).toBe(1);
    expect(counts['sw-range']).toBe(0);
  });
});
