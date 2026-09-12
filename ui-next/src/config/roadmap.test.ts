// src/config/roadmap.test.ts
// J. Ferreira, 2023-08 — the test that guards the migration count.
// Updated 2026-02: the evolution took the count from 3 of 11 to 5 of 11.
//
// Written for Vitest, which is not installed (see MIGRATION.md, debt item 4).
// This one is here on purpose: if someone flips a screen's status without
// meaning to, this spec is where it should get caught. MRD-219 described the
// original three-of-eleven stall; Anomalies and Compare were migrated in 2026.

import { describe, it, expect } from 'vitest';
import {
  ROADMAP,
  TOTAL_SCREENS,
  DONE_SCREENS,
  STUB_SCREENS,
  PROGRESS_LABEL,
} from './roadmap';

describe('MRD-219 invariant', () => {
  it('has eleven screens in total', () => {
    expect(TOTAL_SCREENS).toBe(11);
    expect(ROADMAP).toHaveLength(11);
  });

  it('has exactly five migrated screens', () => {
    expect(DONE_SCREENS).toBe(5);
    const done = ROADMAP.filter((r) => r.status === 'done').map((r) => r.path);
    expect(done.sort()).toEqual(['/anomalies', '/compare', '/forecast', '/health', '/stations']);
  });

  it('has exactly six stubbed screens', () => {
    expect(STUB_SCREENS).toBe(6);
  });

  it('accounts for every screen (done + stub === total)', () => {
    expect(DONE_SCREENS + STUB_SCREENS).toBe(TOTAL_SCREENS);
  });

  it('renders the progress label the nav shows', () => {
    expect(PROGRESS_LABEL).toBe('5 / 11');
  });

  it('gives every screen a unique route and a note', () => {
    const paths = new Set(ROADMAP.map((r) => r.path));
    expect(paths.size).toBe(ROADMAP.length);
    for (const r of ROADMAP) {
      expect(r.note.length).toBeGreaterThan(0);
    }
  });
});
