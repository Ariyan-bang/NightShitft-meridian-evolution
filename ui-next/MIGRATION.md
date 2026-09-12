# ui-next migration status

**5 / 11 screens migrated.** Parked at 3 / 11 from 2023-09; resumed in the
2026 evolution, which added Anomalies and Compare.

Tracker: **MRD-219** — *"The 2023 rewrite in `ui-next/` covers 3 of 11 screens
and is stalled. Both consoles are deployed."* Partially addressed 2026-02; the
count is now 5 of 11 and both consoles remain deployed.

This document is the human-readable half of the ledger in
`src/config/roadmap.ts`. When you change a screen's status, change it in that
file **and** here, and keep the headline count above in sync. (The code prints
a dev-console warning if the "done" count stops being 5.)

## Timeline

| Date       | Event |
|------------|-------|
| 2023-06    | Migration kicked off. Vite/React scaffold, API client, Stations screen. |
| 2023-07    | Forecast screen + hand-rolled SVG chart. Health screen started. |
| 2023-08    | Health screen finished (3rd screen). Eight remaining screens stubbed and scoped. |
| 2023-09    | Team reassigned to the ingest backpressure incident (MRD-201 fallout). **Migration parked.** |
| 2024 →     | No owner assigned. Both consoles remain deployed. |
| 2026-02    | Evolution resumed. Anomalies (4th) and Compare (5th) migrated — the two screens whose data the existing endpoints already served. **5 of 11.** |

## Status by screen

| # | Screen         | Route        | Status | Legacy source                     |
|---|----------------|--------------|--------|-----------------------------------|
| 1 | Stations       | `/stations`  | ✅ done | `dashboard` #stations table       |
| 2 | Forecast       | `/forecast`  | ✅ done | `dashboard` #forecast/#series + chart |
| 3 | Health         | `/health`    | ✅ done | *(new — no legacy equivalent)*    |
| 4 | Anomalies      | `/anomalies` | ✅ done | `dashboard` anomalies tab         |
| 5 | Compare        | `/compare`   | ✅ done | `dashboard` compare view          |
| 6 | Data Quality   | `/quality`   | ⛔ stub | `dashboard` QA panel              |
| 7 | Ingest Monitor | `/ingest`    | ⛔ stub | `dashboard` collector status      |
| 8 | Model Runs     | `/runs`      | ⛔ stub | `dashboard` batch history         |
| 9 | Audit Log      | `/audit`     | ⛔ stub | `dashboard` audit tab             |
| 10| Settings       | `/settings`  | ⛔ stub | `dashboard` preferences           |
| 11| About          | `/about`     | ⛔ stub | `dashboard` footer                |

Done: **5** · Stub: **6** · Total: **11**.

## Migrated in the 2026 evolution

- **Anomalies** — the `GET /api/anomalies` endpoint it was originally scoped
  against never arrived, so the flags are derived client-side from the shared
  agronomy thresholds, the same way the legacy console does. Those thresholds
  are **hand-copied** into `src/util/quality.ts` from
  `dashboard/js/views/quality.js`; a revision has to be made in both consoles.
- **Compare** — multi-station yield table plus a small-multiple `SeriesChart`
  overlay. Forecast data is fetched through a **second** forecast client,
  `src/api/forecastClient.ts`, rather than the canonical `endpoints.ts`. That
  client has drifted from the legacy console's `dashboard/js/api.js` in two
  documented ways (current-run selection and yield formatting), so the two
  consoles can show a different "current" yield for the same station. See the
  header of `forecastClient.ts` and **MRD-241**.

## Why each remaining screen is blocked

- **Data Quality** — would surface gap/outlier flags. No endpoint, no owner.
- **Ingest Monitor** — collector telemetry (`ingest/`). Blocked on a
  `GET /api/ingest/status` endpoint.
- **Model Runs** — nightly batch history (relates to MRD-201). Needs
  `GET /api/runs`. Stub only.
- **Audit Log** — operator action log. Deferred behind an auth story that also
  never landed.
- **Settings** — API base / poll interval / units. The form is rendered but
  wired to nothing (deliberately disabled). Needs a persistence layer.
- **About** — technically a stub, but it grew into the migration's own status
  page: it renders the roadmap ledger from `roadmap.ts` and cannot lie about
  progress. The one "stub" that is worth visiting.

## Debt taken on to ship the first three screens

These were conscious shortcuts, recorded so the next owner isn't surprised:

1. **No OpenAPI / generated types.** `src/api/types.ts` is hand-copied from the
   Java handlers. A service shape change won't be caught until runtime.
2. **No data cache.** `useAsync` is a bespoke request-state hook. `react-query`
   was the plan; it never landed. Several stub screens assume a cache exists.
3. **Hand-rolled chart.** `SeriesChart.tsx` is dependency-free SVG. `recharts`
   was the plan; it never landed. It is, however, a real chart — unlike the
   legacy console's DOM-`<div>` bars (MRD-181).
4. **No tests.** No test runner is configured. `npm run lint` is a stub that
   exits 0.
5. **No production API templating.** The legacy console rewrites its base URL
   with a `sed` at release time; the equivalent pipeline stage for ui-next was
   never written. Set `VITE_API_BASE` by hand.

## To resume the migration

1. Pick an owner. That is the actual blocker; everything else is downstream.
2. Add the missing service endpoints (Anomalies, Data Quality, Ingest, Runs,
   Audit) — see the `TODO(ui-next)` list at the bottom of
   `src/api/endpoints.ts`.
3. Introduce `react-query` and migrate the three real screens onto it before
   adding a fourth, so the cache exists when the stubs need it.
4. Generalise `SeriesChart` (or swap in `recharts`) before building Compare.
5. Only then decommission the legacy console — and not before all 11 screens
   are green here.

---
*Do not delete the legacy console (`dashboard/`) while this reads 5 / 11.*
