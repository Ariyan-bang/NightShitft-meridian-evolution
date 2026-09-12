// src/screens/CompareScreen.tsx
// 2026-02 — SCREEN 5 (migrated). Multi-station comparison.
//
// Migrates the legacy dashboard Compare tab (dashboard/js/views/compare.js).
// Operators kept opening two windows side by side to compare stations; this
// lines them up: a forecast-yield table (min / max / current + a trend
// sparkline) and, for one chosen year, each station's daily series as small
// multiples using the shared SeriesChart.
//
// The compare set lives in the query string (?stations=A,B,C) so a comparison
// can be deep-linked. It is NOT persisted to localStorage — the legacy console
// deliberately kept operator state out of shared terminals and this follows
// that (see dashboard/js/util/state.js).
//
// Forecast data comes through api/forecastClient.ts rather than the canonical
// endpoints module. That client carries two documented drifts from the legacy
// console (current-run selection and yield formatting) — see its header. This
// screen therefore shows the drifted values; a reviewer comparing it against
// the legacy Compare tab should expect them to differ.

import { useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { PageHead } from '../components/PageHead';
import { LoadingBlock } from '../components/Spinner';
import { ErrorBanner } from '../components/ErrorBanner';
import { EmptyState } from '../components/EmptyState';
import { DataTable, type Column } from '../components/DataTable';
import { Sparkline } from '../components/Sparkline';
import { SeriesChart } from '../components/SeriesChart';
import { useStations } from '../hooks/useStations';
import { useSeries } from '../hooks/useSeries';
import { useAsync } from '../hooks/useAsync';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { PROGRESS_LABEL } from '../config/roadmap';
import type { ForecastRow } from '../api/types';
import {
  fetchForecastRuns,
  yieldSpread,
  formatYield,
  currentForecastRun,
} from '../api/forecastClient';

/** Mirrors the legacy console's COMPARE_MAX so the table stays legible. */
const COMPARE_MAX = 6;

interface YieldTableRow {
  stnid: string;
  runs: number;
  min: number | null;
  max: number | null;
  current: number | null;
  currentYear: number | null;
  history: number[];
}

export function CompareScreen() {
  const [params, setParams] = useSearchParams();
  const setParam = params.get('stations') ?? '';
  const overlayParam = params.get('year');

  const compareSet = useMemo(
    () => setParam.split(',').map((s) => s.trim()).filter(Boolean).slice(0, COMPARE_MAX),
    [setParam],
  );
  const setKey = compareSet.join(',');

  const stations = useStations();

  // Load every selected station's forecast runs in parallel through the
  // forecast client. One fetcher for the whole set, re-run when the set changes.
  const forecasts = useAsync<Record<string, ForecastRow[]>>(
    async (signal) => {
      const pairs = await Promise.all(
        compareSet.map(async (stn): Promise<[string, ForecastRow[]]> => {
          try {
            return [stn, await fetchForecastRuns(stn, signal)];
          } catch {
            return [stn, []];
          }
        }),
      );
      return Object.fromEntries(pairs);
    },
    [setKey],
    compareSet.length > 0,
  );

  useDocumentTitle(compareSet.length ? `Compare · ${compareSet.join(', ')}` : 'Compare');

  function addStation(stn: string) {
    if (!stn || compareSet.includes(stn)) return;
    const next = [...compareSet, stn].slice(-COMPARE_MAX);
    setParams(nextParams(next, overlayParam));
  }
  function removeStation(stn: string) {
    setParams(nextParams(compareSet.filter((s) => s !== stn), overlayParam));
  }
  function clearSet() {
    setParams({});
  }
  function pickOverlayYear(y: number) {
    setParams(nextParams(compareSet, String(y)));
  }

  // Yield table rows, one per station, via the forecast client's roll-ups.
  const tableRows = useMemo<YieldTableRow[]>(() => {
    if (!forecasts.data) return [];
    return compareSet.map((stn) => {
      const spread = yieldSpread(forecasts.data?.[stn] ?? null);
      return {
        stnid: stn,
        runs: spread.runs,
        min: spread.min,
        max: spread.max,
        current: spread.current,
        currentYear: spread.currentYear,
        history: spread.history,
      };
    });
  }, [forecasts.data, compareSet]);

  // The union of years across the set, and a sensible default overlay year:
  // the most recent "current run" year in the set (per the forecast client).
  const overlayYears = useMemo(() => {
    if (!forecasts.data) return [];
    const set = new Set<number>();
    for (const stn of compareSet) {
      for (const r of forecasts.data[stn] ?? []) set.add(r.year);
    }
    return Array.from(set).sort((a, b) => b - a);
  }, [forecasts.data, compareSet]);

  const defaultOverlayYear = useMemo(() => {
    if (!forecasts.data) return null;
    let best: number | null = null;
    for (const stn of compareSet) {
      const run = currentForecastRun(forecasts.data[stn] ?? null);
      if (run && (best == null || run.year > best)) best = run.year;
    }
    return best;
  }, [forecasts.data, compareSet]);

  const overlayYear = overlayParam ? Number(overlayParam) : defaultOverlayYear;

  const available = (stations.data ?? []).filter((s) => !compareSet.includes(s.stnid));

  const columns: Column<YieldTableRow>[] = [
    { key: 'stnid', header: 'Station', render: (r) => <span className="mono">{r.stnid}</span> },
    { key: 'runs', header: 'Runs', numeric: true },
    { key: 'min', header: 'Min', numeric: true, render: (r) => formatYield(r.min), sortValue: (r) => r.min ?? -Infinity },
    { key: 'max', header: 'Max', numeric: true, render: (r) => formatYield(r.max), sortValue: (r) => r.max ?? -Infinity },
    {
      key: 'current',
      header: 'Current',
      numeric: true,
      render: (r) => formatYield(r.current),
      sortValue: (r) => r.current ?? -Infinity,
    },
    {
      key: 'currentYear',
      header: 'Yr',
      numeric: true,
      render: (r) => <span className="muted">{r.currentYear ?? '—'}</span>,
      sortValue: (r) => r.currentYear ?? 0,
    },
    {
      key: 'history',
      header: 'Trend',
      sortable: false,
      render: (r) => (r.history.length > 1 ? <Sparkline values={r.history} /> : <span className="muted">—</span>),
    },
  ];

  return (
    <>
      <PageHead
        title="Compare Stations"
        crumb={`ui-next · ${PROGRESS_LABEL} migrated`}
        actions={
          <div style={{ display: 'flex', gap: 8 }}>
            <select
              aria-label="Add station"
              value=""
              onChange={(e) => addStation(e.target.value)}
              disabled={!stations.data || compareSet.length >= COMPARE_MAX}
            >
              <option value="">+ add station…</option>
              {available.map((s) => (
                <option key={s.stnid} value={s.stnid}>
                  {s.stnid}
                </option>
              ))}
            </select>
            <button className="btn" onClick={clearSet} disabled={compareSet.length === 0}>
              Clear set
            </button>
          </div>
        }
      />

      {stations.status === 'error' && stations.error ? (
        <ErrorBanner error={stations.error} onRetry={stations.reload} />
      ) : null}

      {compareSet.length === 0 ? (
        <EmptyState
          title={`Select up to ${COMPARE_MAX} stations to compare.`}
          detail="Add stations from the dropdown above. The comparison can be deep-linked by URL."
        />
      ) : (
        <>
          <div className="toolbar">
            {compareSet.map((stn) => (
              <span key={stn} className="badge ok" title={`Remove ${stn}`}>
                <span className="dot" />
                {stn}
                <button
                  className="btn"
                  style={{ marginLeft: 6, padding: '0 6px' }}
                  onClick={() => removeStation(stn)}
                  aria-label={`Remove ${stn}`}
                >
                  ×
                </button>
              </span>
            ))}
            {compareSet.length >= COMPARE_MAX ? (
              <span className="count">max {COMPARE_MAX} reached</span>
            ) : null}
          </div>

          {forecasts.status === 'loading' && forecasts.firstLoad ? (
            <LoadingBlock label="Loading forecasts…" />
          ) : null}
          {forecasts.status === 'error' && forecasts.error ? (
            <ErrorBanner error={forecasts.error} onRetry={forecasts.reload} />
          ) : null}

          {forecasts.data ? (
            <>
              <section className="panel">
                <h3>Forecast yield history</h3>
                <DataTable
                  columns={columns}
                  rows={tableRows}
                  rowKey={(r) => r.stnid}
                  initialSort="stnid"
                  emptyText="No forecasts for the selected stations."
                />
                <p className="count" style={{ marginTop: 8 }}>
                  Yields via the forecast client (2 dp, current = latest year). The legacy
                  Compare tab prints 3 dp and reads the last-returned run — the two can differ.
                </p>
              </section>

              <section className="panel">
                <div className="toolbar">
                  <h3 style={{ margin: 0 }}>Series overlay</h3>
                  <select
                    aria-label="Overlay year"
                    value={overlayYear ?? ''}
                    onChange={(e) => pickOverlayYear(Number(e.target.value))}
                    disabled={overlayYears.length === 0}
                  >
                    {overlayYears.length === 0 ? <option>—</option> : null}
                    {overlayYears.map((y) => (
                      <option key={y} value={y}>
                        {y}
                      </option>
                    ))}
                  </select>
                </div>

                {overlayYear == null ? (
                  <EmptyState title="No common year to overlay." />
                ) : (
                  <div className="row">
                    {compareSet.map((stn) => (
                      <StationSeriesCard key={`${stn}-${overlayYear}`} station={stn} year={overlayYear} />
                    ))}
                  </div>
                )}
              </section>
            </>
          ) : null}
        </>
      )}
    </>
  );
}

/** One station's daily series for the overlay year, drawn with SeriesChart. */
function StationSeriesCard({ station, year }: { station: string; year: number }) {
  const series = useSeries(station, year);
  return (
    <section className="panel grow" style={{ flexBasis: 420 }}>
      <h3>
        {station} · {year}
      </h3>
      {series.status === 'loading' && series.firstLoad ? (
        <LoadingBlock label="Loading series…" />
      ) : null}
      {series.status === 'error' ? (
        <div className="banner warn" role="alert">
          No series for {station} in {year}.
        </div>
      ) : null}
      {series.data && series.data.length > 0 ? (
        <SeriesChart rows={series.data} />
      ) : series.data ? (
        <EmptyState title={`No ${year} daily records.`} />
      ) : null}
    </section>
  );
}

/** Build the next query-param object for the compare set + overlay year. */
function nextParams(set: string[], year: string | null): Record<string, string> {
  const out: Record<string, string> = {};
  if (set.length) out.stations = set.join(',');
  if (year && set.length) out.year = year;
  return out;
}
