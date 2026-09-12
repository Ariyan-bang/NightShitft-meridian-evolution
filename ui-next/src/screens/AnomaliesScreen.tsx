// src/screens/AnomaliesScreen.tsx
// 2026-02 — SCREEN 4 (migrated). Flagged readings / anomalies.
//
// Migrates the legacy dashboard Anomalies tab (dashboard/js/views/anomalies.js)
// into ui-next. Like the legacy tab, there is no server anomaly endpoint: the
// flags are derived on the client from the shared agronomy thresholds (see
// util/quality.ts, which carries the same rules the legacy console does).
//
// It lists the daily-series rows that trip one or more QC rules for a chosen
// station/year, with a scannable summary strip and per-flag filters, so an
// operator can eyeball the suspect days before signing off a run. State lives
// in the query string (?station=&year=) so a specific view can be deep-linked —
// the legacy tab could not be.

import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { PageHead } from '../components/PageHead';
import { LoadingBlock, Spinner } from '../components/Spinner';
import { ErrorBanner } from '../components/ErrorBanner';
import { EmptyState } from '../components/EmptyState';
import { StatTile, type Tone } from '../components/StatTile';
import { DataTable, type Column } from '../components/DataTable';
import { SeriesChart } from '../components/SeriesChart';
import { useStations } from '../hooks/useStations';
import { useForecast, latestYear } from '../hooks/useForecast';
import { useSeries } from '../hooks/useSeries';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { fixed } from '../util/format';
import { doyLabel } from '../util/doy';
import { PROGRESS_LABEL } from '../config/roadmap';
import {
  annotate,
  flagCounts,
  FLAG_LABELS,
  FLAG_ORDER,
  type FlagCode,
  type FlaggedRow,
} from '../util/quality';

export function AnomaliesScreen() {
  const [params, setParams] = useSearchParams();
  const station = params.get('station');
  const yearParam = params.get('year');
  const year = yearParam ? Number(yearParam) : null;

  const [active, setActive] = useState<Set<FlagCode>>(new Set());

  const stations = useStations();
  useEffect(() => {
    if (!station && stations.data && stations.data.length > 0) {
      setParams({ station: stations.data[0].stnid }, { replace: true });
    }
  }, [station, stations.data, setParams]);

  const forecast = useForecast(station);
  const newestYear = latestYear(forecast.data);
  useEffect(() => {
    if (station && year == null && newestYear != null) {
      setParams({ station, year: String(newestYear) }, { replace: true });
    }
  }, [station, year, newestYear, setParams]);

  const series = useSeries(station, year);

  // Derive flags once per series load. Clearing filters on a fresh load keeps
  // the view honest — a filter from the previous station shouldn't hide rows.
  const flagged = useMemo<FlaggedRow[]>(
    () => (series.data ? annotate(series.data) : []),
    [series.data],
  );
  useEffect(() => {
    setActive(new Set());
  }, [station, year]);

  const counts = useMemo(() => flagCounts(flagged), [flagged]);
  const suspect = useMemo(() => flagged.filter((r) => r.suspect), [flagged]);
  const total = flagged.length;

  const shown = useMemo(() => {
    if (active.size === 0) return suspect;
    return suspect.filter((r) => r.flags.some((f) => active.has(f)));
  }, [suspect, active]);

  useDocumentTitle(station ? `Anomalies · ${station}` : 'Anomalies');

  function pickStation(stn: string) {
    setParams({ station: stn });
  }
  function pickYear(y: number) {
    if (station) setParams({ station, year: String(y) });
  }
  function toggleFlag(code: FlagCode) {
    setActive((prev) => {
      const next = new Set(prev);
      if (next.has(code)) next.delete(code);
      else next.add(code);
      return next;
    });
  }

  const suspectFrac = total > 0 ? suspect.length / total : 0;
  const summaryTone: Tone = suspect.length === 0 ? 'ok' : suspectFrac > 0.1 ? 'warn' : 'neutral';

  const years = (forecast.data ?? []).slice().sort((a, b) => b.year - a.year);

  const columns: Column<FlaggedRow>[] = [
    { key: 'doy', header: 'DOY', numeric: true },
    {
      key: 'suspect', // distinct key; renders the calendar date, not the field
      header: 'Date',
      sortable: false,
      render: (r) => <span className="muted">{year != null ? doyLabel(year, r.doy) : ''}</span>,
    },
    { key: 'sw', header: 'SW', numeric: true, render: (r) => fixed(r.sw, 1) },
    { key: 'et', header: 'ET', numeric: true, render: (r) => fixed(r.et, 2) },
    { key: 'drain', header: 'Drain', numeric: true, render: (r) => fixed(r.drain, 2) },
    { key: 'biom', header: 'Biomass', numeric: true, render: (r) => fixed(r.biom, 0) },
    { key: 'lai', header: 'LAI', numeric: true, render: (r) => fixed(r.lai, 2) },
    {
      key: 'flags',
      header: 'Flags',
      sortable: false,
      render: (r) => (
        <span>
          {r.flags.map((f) => (
            <span key={f} className="badge warn" style={{ marginRight: 4 }} title={FLAG_LABELS[f]}>
              {f}
            </span>
          ))}
        </span>
      ),
    },
  ];

  return (
    <>
      <PageHead
        title="Anomalies"
        crumb={`ui-next · ${PROGRESS_LABEL} migrated`}
        actions={
          <div style={{ display: 'flex', gap: 8 }}>
            <select
              aria-label="Station"
              value={station ?? ''}
              onChange={(e) => pickStation(e.target.value)}
              disabled={!stations.data}
            >
              {!stations.data ? <option>loading…</option> : null}
              {stations.data?.map((s) => (
                <option key={s.stnid} value={s.stnid}>
                  {s.stnid}
                </option>
              ))}
            </select>
            <select
              aria-label="Year"
              value={year ?? ''}
              onChange={(e) => pickYear(Number(e.target.value))}
              disabled={years.length === 0}
            >
              {years.length === 0 ? <option>—</option> : null}
              {years.map((r) => (
                <option key={`${r.year}-${r.run_at}`} value={r.year}>
                  {r.year}
                </option>
              ))}
            </select>
          </div>
        }
      />

      {stations.status === 'error' && stations.error ? (
        <ErrorBanner error={stations.error} onRetry={stations.reload} />
      ) : null}

      {!station ? (
        <EmptyState title="Select a station to scan its series for anomalies." />
      ) : year == null ? (
        <EmptyState title="This station has no forecast runs to scan." />
      ) : (
        <>
          {series.status === 'loading' && series.firstLoad ? (
            <LoadingBlock label="Scanning for anomalies…" />
          ) : null}
          {series.status === 'error' && series.error ? (
            <ErrorBanner error={series.error} onRetry={series.reload} />
          ) : null}

          {series.data ? (
            <>
              <div className="stat-row">
                <StatTile label="Days scanned" value={total} hint={`${station} · ${year}`} />
                <StatTile
                  label="Suspect days"
                  value={suspect.length}
                  hint={total > 0 ? `${(suspectFrac * 100).toFixed(1)}% of days` : '—'}
                  tone={summaryTone}
                />
                <StatTile
                  label="Total flags"
                  value={Object.values(counts).reduce((a, b) => a + b, 0)}
                  hint="across all rules"
                />
                <StatTile
                  label="Cleanest rule"
                  value={suspect.length === 0 ? 'all clean' : 'see filters'}
                  tone={suspect.length === 0 ? 'ok' : 'neutral'}
                />
              </div>

              {suspect.length === 0 ? (
                <div className="banner info" role="status" style={{ marginTop: 12 }}>
                  No suspect readings in {total} days. Clean run.
                </div>
              ) : null}

              <section className="panel">
                <h3>Daily water balance &amp; growth</h3>
                {series.data.length > 0 ? (
                  <SeriesChart rows={series.data} />
                ) : (
                  <EmptyState title="No daily records for this station/year." />
                )}
              </section>

              {suspect.length > 0 ? (
                <section className="panel">
                  <div className="toolbar">
                    <span className="count">Filter by flag:</span>
                    {FLAG_ORDER.map((code) => {
                      const n = counts[code];
                      if (!n) return null;
                      const on = active.has(code);
                      return (
                        <button
                          key={code}
                          className="btn"
                          aria-pressed={on}
                          onClick={() => toggleFlag(code)}
                          style={on ? { borderColor: 'var(--accent)', color: 'var(--accent)' } : undefined}
                          title={FLAG_LABELS[code]}
                        >
                          {code} <span className="count">({n})</span>
                        </button>
                      );
                    })}
                    {active.size > 0 ? (
                      <button className="btn" onClick={() => setActive(new Set())}>
                        Clear filters
                      </button>
                    ) : null}
                    {series.status === 'loading' ? <Spinner /> : null}
                  </div>

                  <DataTable
                    columns={columns}
                    rows={shown}
                    rowKey={(r) => String(r.doy)}
                    initialSort="doy"
                    emptyText="No readings match the active filters."
                  />
                  <p className="count" style={{ marginTop: 8 }}>
                    {shown.length} of {suspect.length} suspect days shown
                  </p>
                </section>
              ) : null}
            </>
          ) : null}
        </>
      )}
    </>
  );
}
