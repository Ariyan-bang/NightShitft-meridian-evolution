"""Opt-in anomaly analysis over forecast OUTPUT.

    -- Archive (output) side, experimental --

qc.py guards the model's INPUT: it checks that a deck is decodable and
shaped the way cropmod assumes before four hours of batch time turns bad
weather into a bad yield.  It says nothing about the OUTPUT.  This module
is the mirror on the far side of the seam: a second-generation,
output-facing QC pass ("anomaly2") that reads a forecast's daily rows
back out and flags results that look physically or numerically off, so a
reviewer can spot a suspect forecast before it is reported as "in force"
(the hazard MRD-238 is about on the reporting side).

It is strictly OPT-IN and side-effect free.  It never runs the model,
never writes the store, and is not wired into the nightly run; nothing in
the default path imports it.  It reads stored forecasts (or summarises a
freshly parsed one) and returns plain value objects a report can render.

The checks are about *shape and plausibility*, not agronomy:

  * MRD-143 fingerprint   -- parsed days fewer than the banner promised,
                             i.e. a day was dropped on an overflow.
  * soil-water jumps      -- a day-to-day change in SW far outside the
                             run's own typical step (a decode artefact,
                             or the overflow residue MRD-143 leaves).
  * impossible negatives  -- ET, drainage, biomass or LAI below zero.
  * stuck soil water      -- SW pinned at a single value for a long run.
  * sustained stress      -- a long unbroken run of water-stressed days.
  * cohort yield outlier  -- a station-year whose yield is far from its
                             peers in the same year (z-score).

Added 2026 (continued evolution).  Experimental: advisory output only,
meant to be eyeballed, not to gate a run.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, List, Optional, Sequence

from .aggregate import summarize_rows
from .errors import AggregateError
from .results import DailyRow, ForecastResult, SeasonSummary
from .store import Store

# A day-to-day soil-water step larger than this many multiples of the
# run's own median absolute step is flagged.  Deliberately loose: we want
# the genuine discontinuities (a decode artefact), not ordinary rain days.
SW_JUMP_SIGMA = 6.0
# Minimum run of identical SW values before we call it "stuck".
STUCK_SW_RUN = 10
# Minimum run of consecutive water-stressed days worth flagging.
STRESS_RUN_DAYS = 21
# Cohort z-score beyond which a station-year's yield is an outlier.
YIELD_OUTLIER_Z = 2.5


class AnomalySeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class Anomaly:
    """One flagged observation about a forecast's output.

    ``doy`` is -1 for season-level findings that are not tied to a single
    day (a dropped-day count, a cohort outlier).
    """
    stnid: str
    year: int
    severity: AnomalySeverity
    code: str
    message: str
    doy: int = -1

    def as_row(self) -> Dict[str, object]:
        """Flatten to a report-ready dict (the derived-table row shape)."""
        d = asdict(self)
        d["severity"] = self.severity.value
        return d

    def __str__(self) -> str:
        where = "" if self.doy < 0 else " (doy %d)" % self.doy
        return "%s %s [%s %d]: %s%s" % (
            self.severity.value.upper(), self.code, self.stnid, self.year,
            self.message, where)


@dataclass
class AnomalyReport:
    """All anomalies found for one station-year, plus its summary."""
    stnid: str
    year: int
    summary: Optional[SeasonSummary] = None
    anomalies: List[Anomaly] = field(default_factory=list)

    def add(self, severity: AnomalySeverity, code: str, message: str,
            doy: int = -1) -> None:
        self.anomalies.append(
            Anomaly(self.stnid, self.year, severity, code, message, doy))

    def errors(self) -> List[Anomaly]:
        return [a for a in self.anomalies
                if a.severity is AnomalySeverity.ERROR]

    def warnings(self) -> List[Anomaly]:
        return [a for a in self.anomalies
                if a.severity is AnomalySeverity.WARNING]

    @property
    def clean(self) -> bool:
        return not any(a.severity is not AnomalySeverity.INFO
                       for a in self.anomalies)

    def as_rows(self) -> List[Dict[str, object]]:
        """The derived table for this station-year, one dict per anomaly."""
        return [a.as_row() for a in self.anomalies]

    def headline(self) -> str:
        return ("%s %d: %d error(s), %d warning(s)"
                % (self.stnid, self.year, len(self.errors()),
                   len(self.warnings())))


# ==========================================================================
# Small numeric helpers (kept local; no dependency added)
# ==========================================================================
def _median(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2 == 1:
        return ordered[mid]
    return 0.5 * (ordered[mid - 1] + ordered[mid])


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _stdev(values: Sequence[float]) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    mu = _mean(values)
    var = sum((v - mu) ** 2 for v in values) / (n - 1)
    return var ** 0.5


# ==========================================================================
# Per-station-year checks over the daily rows
# ==========================================================================
class DailyAnomalyScan:
    """Runs the daily-row checks for one station-year."""

    def __init__(self, report: AnomalyReport):
        self.report = report

    def run(self, ndays: int, rows: Sequence[DailyRow]) -> None:
        if not rows:
            self.report.add(AnomalySeverity.ERROR, "NOROWS",
                            "forecast has no daily rows")
            return
        self._dropped_days(ndays, rows)
        self._negatives(rows)
        self._sw_jumps(rows)
        self._stuck_sw(rows)
        self._stress_runs(rows)

    def _dropped_days(self, ndays: int, rows: Sequence[DailyRow]) -> None:
        # The MRD-143 fingerprint: fewer parsed rows than the banner said.
        parsed = len(rows)
        if parsed < ndays:
            self.report.add(
                AnomalySeverity.ERROR, "DROPPED",
                "parsed %d of %d banner days -- MRD-143 overflow fingerprint"
                % (parsed, ndays))
        elif parsed > ndays:
            self.report.add(
                AnomalySeverity.WARNING, "EXTRA",
                "parsed %d rows but banner promised %d" % (parsed, ndays))

    def _negatives(self, rows: Sequence[DailyRow]) -> None:
        for r in rows:
            if r.et < 0.0:
                self.report.add(AnomalySeverity.ERROR, "NEGET",
                                "et=%.3f is negative" % r.et, doy=r.doy)
            if r.drain < 0.0:
                self.report.add(AnomalySeverity.ERROR, "NEGDRAIN",
                                "drain=%.3f is negative" % r.drain, doy=r.doy)
            if r.biom < 0.0:
                self.report.add(AnomalySeverity.ERROR, "NEGBIOM",
                                "biomass=%.1f is negative" % r.biom,
                                doy=r.doy)
            if r.lai < 0.0:
                self.report.add(AnomalySeverity.ERROR, "NEGLAI",
                                "lai=%.3f is negative" % r.lai, doy=r.doy)

    def _sw_jumps(self, rows: Sequence[DailyRow]) -> None:
        if len(rows) < 3:
            return
        steps = [abs(b.sw - a.sw) for a, b in zip(rows, rows[1:])]
        typical = _median(steps)
        if typical <= 0.0:
            return
        threshold = typical * SW_JUMP_SIGMA
        for a, b in zip(rows, rows[1:]):
            delta = abs(b.sw - a.sw)
            if delta > threshold:
                self.report.add(
                    AnomalySeverity.WARNING, "SWJUMP",
                    "soil water stepped %.2f (typical %.2f) into doy %d"
                    % (delta, typical, b.doy), doy=b.doy)

    def _stuck_sw(self, rows: Sequence[DailyRow]) -> None:
        run_start = 0
        for i in range(1, len(rows) + 1):
            same = i < len(rows) and rows[i].sw == rows[run_start].sw
            if not same:
                run_len = i - run_start
                if run_len >= STUCK_SW_RUN:
                    self.report.add(
                        AnomalySeverity.WARNING, "STUCKSW",
                        "soil water held at %.2f for %d days from doy %d"
                        % (rows[run_start].sw, run_len, rows[run_start].doy),
                        doy=rows[run_start].doy)
                run_start = i

    def _stress_runs(self, rows: Sequence[DailyRow]) -> None:
        sw_max = max(r.sw for r in rows)
        threshold = sw_max * 0.5  # mirror aggregate.STRESS_SW_FRACTION
        run_start: Optional[int] = None
        for i, r in enumerate(rows):
            stressed = r.sw < threshold
            if stressed and run_start is None:
                run_start = i
            elif not stressed and run_start is not None:
                self._maybe_flag_stress(rows, run_start, i)
                run_start = None
        if run_start is not None:
            self._maybe_flag_stress(rows, run_start, len(rows))

    def _maybe_flag_stress(self, rows: Sequence[DailyRow], start: int,
                           end: int) -> None:
        run_len = end - start
        if run_len >= STRESS_RUN_DAYS:
            self.report.add(
                AnomalySeverity.INFO, "STRESSRUN",
                "%d consecutive water-stressed days from doy %d"
                % (run_len, rows[start].doy), doy=rows[start].doy)


# ==========================================================================
# Entry points
# ==========================================================================
def analyse_rows(stnid: str, year: int, ndays: int, yield_t: float,
                 rows: Sequence[DailyRow]) -> AnomalyReport:
    """Scan one station-year's daily rows.  Pure; no I/O."""
    report = AnomalyReport(stnid=stnid, year=year)
    try:
        report.summary = summarize_rows(stnid, year, yield_t, ndays, rows)
    except AggregateError:
        report.summary = None
    DailyAnomalyScan(report).run(ndays, rows)
    return report


def analyse_result(result: ForecastResult) -> AnomalyReport:
    """Scan a freshly parsed forecast (during or just after a run)."""
    return analyse_rows(result.stnid, result.year, result.ndays,
                        result.yield_t, result.rows)


def analyse_stored(store: Store, stnid: str, year: int) -> AnomalyReport:
    """Scan a forecast already persisted in the store (after the fact)."""
    fc = store.get_forecast(stnid, year)
    if fc is None:
        raise AggregateError("no stored forecast to analyse",
                             stnid=stnid, year=year)
    rows = store.daily_rows(stnid, year)
    return analyse_rows(stnid, year, fc.ndays, fc.yield_t, rows)


def analyse_all(store: Store) -> List[AnomalyReport]:
    """Scan every stored forecast and add cross-station cohort checks.

    Per-station-year checks run first; then a cohort pass flags any
    station-year whose yield is a statistical outlier among the other
    stations in the SAME year.  The cohort finding is appended to that
    station-year's own report.
    """
    reports: List[AnomalyReport] = []
    index: Dict[tuple, AnomalyReport] = {}
    for fc in store.list_forecasts():
        rows = store.daily_rows(fc.stnid, fc.year)
        if not rows:
            continue
        rep = analyse_rows(fc.stnid, fc.year, fc.ndays, fc.yield_t, rows)
        reports.append(rep)
        index[(fc.stnid, fc.year)] = rep

    _cohort_yield_outliers(store, index)
    return reports


def _cohort_yield_outliers(store: Store,
                           index: Dict[tuple, AnomalyReport]) -> None:
    """Flag yields far from their same-year peers (needs >= 3 stations)."""
    by_year: Dict[int, List[tuple]] = {}
    for fc in store.list_forecasts():
        by_year.setdefault(fc.year, []).append((fc.stnid, fc.yield_t))

    for year, pairs in by_year.items():
        if len(pairs) < 3:
            continue
        yields = [y for _, y in pairs]
        mu = _mean(yields)
        sigma = _stdev(yields)
        if sigma <= 0.0:
            continue
        for stnid, y in pairs:
            z = (y - mu) / sigma
            if abs(z) >= YIELD_OUTLIER_Z:
                rep = index.get((stnid, year))
                if rep is not None:
                    rep.add(
                        AnomalySeverity.WARNING, "YIELDOUT",
                        "yield %.3f t/ha is %.1f sigma from the %d-station "
                        "cohort mean %.3f" % (y, z, len(pairs), mu))


def to_table(reports: Sequence[AnomalyReport]) -> List[Dict[str, object]]:
    """Flatten many reports into one derived table (list of row dicts).

    This is the report-ready structure the reporting subsystem (or a
    reviewer's notebook) can consume directly: one row per anomaly, across
    every station-year scanned, ordered by station then year then day.
    """
    rows: List[Dict[str, object]] = []
    for rep in reports:
        rows.extend(rep.as_rows())
    rows.sort(key=lambda r: (r["stnid"], r["year"], r["doy"], r["code"]))
    return rows
