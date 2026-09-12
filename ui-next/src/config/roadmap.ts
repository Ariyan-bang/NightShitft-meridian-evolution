// src/config/roadmap.ts
// J. Ferreira, 2023-08 — the migration ledger, in code.
//
// This is the single source of truth for "which screens are done". The nav
// (src/config/nav.ts) reads it, the About/Settings stubs read it, and
// MIGRATION.md is kept in sync with it by hand. If you change a screen's
// status, change it HERE and then update MIGRATION.md to match.
//
// Status: the 2023 team left this at 3 of 11 screens (see MRD-219). The 2026
// evolution picked it back up and migrated two more — Anomalies and Compare,
// the two whose data the existing endpoints already served — taking it to 5 of
// 11. The remaining six still depend on endpoints the Java service never grew.
//
//   MRD-219 (tracker): "The 2023 rewrite in ui-next/ covers 3 of 11 screens
//   and is stalled. Both consoles are deployed." — partially addressed 2026-02;
//   now 5 of 11. Both consoles remain deployed.

export type ScreenStatus = 'done' | 'stub' | 'not-started';

export interface RoadmapEntry {
  /** Route path segment. */
  path: string;
  /** Human label used in nav and headings. */
  label: string;
  status: ScreenStatus;
  /** The legacy screen this was meant to replace, if any. */
  legacy: string | null;
  /** Free note: why it is where it is. Shown on the stub pages. */
  note: string;
}

export const ROADMAP: RoadmapEntry[] = [
  {
    path: '/stations',
    label: 'Stations',
    status: 'done',
    legacy: 'dashboard #stations table',
    note: 'First screen migrated. Sortable/filterable, which the legacy grid was not.',
  },
  {
    path: '/forecast',
    label: 'Forecast',
    status: 'done',
    legacy: 'dashboard #forecast + #series + DOM bar chart',
    note: 'Second screen. Real SVG chart replaces the stopgap DOM bars (MRD-181).',
  },
  {
    path: '/health',
    label: 'Health',
    status: 'done',
    legacy: 'none — new in ui-next',
    note: 'Third screen. No legacy equivalent; added because the old console gave no signal when :8081 was down.',
  },
  {
    path: '/anomalies',
    label: 'Anomalies',
    status: 'done',
    legacy: 'dashboard anomalies tab',
    note: 'Fourth screen (2026). No /api/anomalies endpoint exists, so the flags are derived client-side from the shared agronomy thresholds, exactly as the legacy console does (util/quality.ts).',
  },
  {
    path: '/compare',
    label: 'Compare',
    status: 'done',
    legacy: 'dashboard compare view',
    note: 'Fifth screen (2026). Multi-station yield table + small-multiple SeriesChart overlay. Uses api/forecastClient.ts, which carries a documented drift from the legacy console.',
  },
  {
    path: '/quality',
    label: 'Data Quality',
    status: 'stub',
    legacy: 'dashboard QA panel',
    note: 'Would surface gap/outlier flags. No owner since 2023-09.',
  },
  {
    path: '/ingest',
    label: 'Ingest Monitor',
    status: 'stub',
    legacy: 'dashboard collector status',
    note: 'Collector telemetry (ingest/). Blocked on an /api/ingest/status endpoint.',
  },
  {
    path: '/runs',
    label: 'Model Runs',
    status: 'stub',
    legacy: 'dashboard batch history',
    note: 'Nightly batch history (MRD-201). Needs /api/runs. Not started beyond this stub.',
  },
  {
    path: '/audit',
    label: 'Audit Log',
    status: 'stub',
    legacy: 'dashboard audit tab',
    note: 'Operator action log. Deferred pending an auth story that also never landed.',
  },
  {
    path: '/settings',
    label: 'Settings',
    status: 'stub',
    legacy: 'dashboard preferences',
    note: 'API base, refresh interval, units. Placeholder only.',
  },
  {
    path: '/about',
    label: 'About',
    status: 'stub',
    legacy: 'dashboard footer',
    note: 'Build info + migration status. Reads this roadmap. Intentionally the most honest page.',
  },
];

// ---- Derived counts. Keep MIGRATION.md's headline in sync with these. ----

export const TOTAL_SCREENS = ROADMAP.length; // 11
export const DONE_SCREENS = ROADMAP.filter((s) => s.status === 'done').length; // 5
export const STUB_SCREENS = ROADMAP.filter((s) => s.status === 'stub').length; // 6

/** e.g. "5 / 11" */
export const PROGRESS_LABEL = `${DONE_SCREENS} / ${TOTAL_SCREENS}`;

/** Hard-coded sanity check. If someone flips a status without meaning to, this
 *  trips in dev. The count moved from 3 (the MRD-219 stall) to 5 in the 2026
 *  evolution; keep MIGRATION.md and this invariant in step. */
if (import.meta.env.DEV && DONE_SCREENS !== 5) {
  // eslint-disable-next-line no-console
  console.warn(
    `[ui-next] roadmap now reports ${DONE_SCREENS} done screens, not 5. ` +
      `The 2026 evolution took MRD-219 from 3 of 11 to 5 of 11; update MIGRATION.md if this was intentional.`,
  );
}

export const STALLED_SINCE = '2023-09';
export const STALL_REASON =
  'Team reassigned to the ingest backpressure incident (MRD-201 fallout); parked at 3 of 11 from 2023-09. The 2026 evolution resumed it to 5 of 11.';
