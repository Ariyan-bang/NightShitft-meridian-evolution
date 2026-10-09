# Meridian open issues

Exported from the tracker 2026-10-09.  Only open items are listed.

| ID      | Opened     | Component | Severity | Summary |
|---------|------------|-----------|----------|---------|
| MRD-77  | 2012-03-14 | ingest    | major    | Collector shells out to `sqlite3` instead of linking the library. Same in the Java layer. Was meant to be temporary. |
| MRD-91  | 2013-01-08 | analytics | minor    | Soil parameters are hard coded in `deck.py`. The 2008 schema has nowhere to put them. |
| MRD-118 | 2014-06-30 | model     | major    | cropmod assumes daily records are in ascending DOY order and does not check. Out of order decks give silently wrong water balance. |
| MRD-143 | 2016-09-02 | analytics | critical | Output parser must read by column. A whitespace split drops days when SW overflows its field. Took two seasons to find. Fixed in the parser, not in the model. |
| MRD-166 | 2017-11-21 | services  | major    | `ForecastHandler` and `SeriesHandler` build SQL by string concatenation from query parameters. Currently mitigated only by the portal being internal. |
| MRD-181 | 2019-04-03 | dashboard | minor    | Console has no build step, so no charting library. The DOM bar chart in `dashboard.js` was a stopgap. |
| MRD-201 | 2020-08-17 | analytics | major    | cropmod reads and writes fixed filenames in its CWD, so runs cannot be parallelised. The nightly batch takes four hours. |
| MRD-204 | 2021-02-11 | model     | major    | `WATBAL` and `GROWTH` compute the water stress fraction differently. WATBAL uses SW/SWMAX; GROWTH uses SW/(AWC*100). These disagree whenever rooting depth is not 1000 mm. |
| MRD-219 | 2023-06-05 | dashboard | major    | The 2023 rewrite in `ui-next/` covers 3 of 11 screens and is stalled. Both consoles are deployed. |
| MRD-227 | 2024-10-30 | ingest    | minor    | Station id is space padded in the frame and trimmed by hand in `tsstore.c`. Ids containing trailing spaces are indistinguishable from padded ids. |
| MRD-231 | 2025-03-12 | model     | major    | Request from Agronomy to port cropmod off Fortran. No validation harness exists, so nobody has been able to say what "the same answer" would mean. |
| MRD-238 | 2025-11-14 | reporting | major    | The report writer selects the current forecast per station with `MAX(run_at)` compared as text. A manual backfill written in a different timestamp format sorts wrong, so a report can print an older run as the one "in force". |
| MRD-239 | 2026-03-18 | model     | major    | Optional nutrient path forms crop N demand in g N m-2 but soil pools are kg N ha-1; `NUTRIENT` converts with NAREA=10.0 while `NUPTAKE` uses GM2_TO_KGHA=100.0. The two disagree by 10x. Latent: the nutrient path is off by default. |
| MRD-240 | 2026-03-25 | model     | minor    | `NBALANCE` reconstructs its own layered water profile and duplicates SOILWAT's cascade in CASCADE_FLUX; the two can drift if SOILWAT's rule changes and CASCADE_FLUX is not updated. |
| MRD-241 | 2026-04-15 | model     | major    | A port-target kernel for MRD-231 now exists (pure `nmin_kernel` with documented I/O and a MERIDIAN_TRACE fixture emitter), but nothing yet wires the captured traces into a pass/fail validation harness. |
| MRD-242 | 2026-04-29 | ingest    | major    | MRD2 parser checks the CRC over bytes 0..47 (the channel block) instead of the full 0..49 region, so corruption of the version or flags byte is undetected and such frames are accepted. Latent: the default spool is all MRD1. |
| MRD-243 | 2026-05-06 | ingest    | minor    | `mrd_framedump` recomputes the MRD2 CRC over 0..49 while the parser checks only 0..47, so the debug tool and the collector disagree on otherwise well-formed MRD2 frames. |
| MRD-244 | 2026-05-20 | analytics | major    | Opt-in parallel orchestrator collects completed runs into a dict keyed by station id only, so a station with more than one year loses all but the last-completing year on persist. Latent: the default batch is serial. |
| MRD-245 | 2026-06-03 | analytics | minor    | Soil-parameter config loader (`soilconf.py`) is opt-in and not wired into the nightly path; MRD-91 stays open until the default run reads it and the hard-coded dict in `deck.py` is retired. |
| MRD-246 | 2026-06-17 | analytics | minor    | `anomaly2` output QC is advisory only and not run by the nightly batch; a suspect forecast is still persisted and can be reported before anyone scans it. |
| MRD-247 | 2026-07-08 | services  | major    | `ForecastCache` serves a stale per-station summary on `/api/v2/forecast` after a new run: `invalidate(stn,year)` removes a composite key the entries are never stored under (they are keyed by station only), so eviction is a no-op until the TTL expires. Latent: only the v2 path uses the cache. |
| MRD-248 | 2026-07-15 | services  | minor    | Two route-mapping styles now coexist: the hand-rolled `Router` for the 2019-21 contexts and the reflective `@Endpoint`/`Dispatcher` for v2. Consolidation filed, not scheduled. |
| MRD-249 | 2026-07-22 | services  | minor    | `/api/v2/stations` metadata (display name, latitude, region) is a hard-coded in-class catalogue; a seventh site would need a code change, not config. |
| MRD-250 | 2026-08-12 | reporting | major    | `reports/selection.current_forecast` orders runs by comparing `run_at` as text (the MRD-238 hazard re-seeded in the new Python selection path). An off-format backfill sorts wrong, so a newer backfill is picked as an older run. Latent on ISO-stamped data. |
| MRD-251 | 2026-08-19 | reporting | minor    | The JSON and CSV exports share no schema contract; a consumer must infer the structure per report. A documented export schema/version is wanted. |
| MRD-252 | 2026-09-09 | ui-next   | major    | `ui-next/src/api/forecastClient.ts` duplicates `dashboard/js/api.js` and has drifted: it picks the current run by greatest year and formats yield to 2 dp, where the legacy console takes the last-returned run and formats to 3 dp, so the two consoles report a different "current" yield for the same station. |
| MRD-253 | 2026-09-16 | ui-next   | minor    | QC thresholds are hand-copied into `ui-next/src/util/quality.ts` from `dashboard/js/views/quality.js`, and `dashboard/js/views/trends.js` re-implements the Compare yield roll-up; the same rule now lives in three places across the two consoles. |
