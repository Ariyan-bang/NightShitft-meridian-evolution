"""Trend report.

Where the season summary is one year across every station and the
station report is one station's figures year by year, the trend report
is about *direction*: is a station's forecast yield rising or falling
over the years on file, and by how much per year.

It runs in two modes, chosen by whether a station is given:

  * ``--station GUELPH`` -- a single-station detail: every year on file
    with its year-over-year change, an index against the first year
    (first year = 100), the model that produced it, and a marker on the
    row that is the *current* run (see ``reports.selection``);

  * no station -- a province-wide roll-up: one row per station giving
    its first and last yields, net change, a least-squares slope in
    t/ha per year, a plain-language direction, and the crop year of its
    current run.

Both modes close with a short interpretive block (mean, best/worst,
risers vs fallers) so the page answers "which way is this going?" at a
glance without the reader working a ruler down the table.

The "current run" marker and the current-standing lines go through
``reports.selection.current_forecast`` rather than assuming the last
year in the table is the newest run -- a late backfill of an older crop
year can be the most recently computed figure.

    New in this cycle.  Shares the ranked-table machinery with the
    season summary and the run-selection rule with the station report.
"""
from __future__ import annotations

from typing import List, Optional, Sequence

from ..constants import long_name, region_of
from ..db import Forecast
from ..format import Block, Column, ColumnSet
from . import selection
from .base import BaseReport, ReportError


def _slope_per_year(forecasts: Sequence[Forecast]) -> Optional[float]:
    """Least-squares slope of yield against crop year (t/ha per year).

    Returns None when there are fewer than two years or every year is
    the same (a vertical/degenerate fit), so the caller can print a
    missing marker rather than a divide-by-zero.
    """
    n = len(forecasts)
    if n < 2:
        return None
    xs = [float(f.year) for f in forecasts]
    ys = [float(f.yield_t) for f in forecasts]
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0.0:
        return None
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return sxy / sxx


def _direction(net: Optional[float], eps: float = 0.0005) -> str:
    """A compact ASCII direction word for a net change over the span."""
    if net is None:
        return "-"
    if net > eps:
        return "up"
    if net < -eps:
        return "down"
    return "flat"


class TrendReport(BaseReport):
    name = "trend"
    title = "YIELD TREND"
    code = "TRND"

    # -- banner wiring -----------------------------------------------------
    def subtitle(self) -> str:
        stn = self.config.normalized_station()
        if stn:
            return "%s -- %s (%s)" % (self.title, stn, long_name(stn))
        return "%s -- ALL STATIONS" % self.title

    def ref_code(self):
        stn = self.config.normalized_station()
        return self._default_ref(stn if stn else "ALL")

    def running_title(self) -> str:
        stn = self.config.normalized_station()
        return "YIELD TREND -- %s" % (stn if stn else "ALL STATIONS")

    # -- dispatch ----------------------------------------------------------
    def build_blocks(self) -> List[Block]:
        stn = self.config.normalized_station()
        if stn:
            return self._single_station_blocks(stn)
        return self._province_blocks()

    # -- single-station mode ----------------------------------------------
    def _single_columns(self) -> ColumnSet:
        if self.config.is_wide():
            return ColumnSet(
                [
                    Column("year", "YEAR", 6, kind="int"),
                    Column("yield_t", "YIELD", 10, kind="float", decimals=3,
                           unit="t/ha"),
                    Column("delta", "YoY", 9, kind="delta", decimals=3,
                           unit="t/ha"),
                    Column("index", "INDEX", 8, kind="float", decimals=1),
                    Column("ndays", "DAYS", 6, kind="int"),
                    Column("model", "MODEL", 16, kind="text", align="left"),
                    Column("run_at", "RUN AT", 20, kind="text", align="left"),
                    Column("cur", "CUR", 4, kind="text", align="left"),
                ]
            )
        return ColumnSet(
            [
                Column("year", "YEAR", 6, kind="int"),
                Column("yield_t", "YIELD", 10, kind="float", decimals=3,
                       unit="t/ha"),
                Column("delta", "YoY", 9, kind="delta", decimals=3,
                       unit="t/ha"),
                Column("index", "INDEX", 8, kind="float", decimals=1),
                Column("model", "MODEL", 13, kind="text", align="left"),
                Column("cur", "CUR", 4, kind="text", align="left"),
            ]
        )

    def _single_station_blocks(self, stn: str) -> List[Block]:
        forecasts = self.db.forecasts_for_station(stn)  # oldest year first
        if not forecasts:
            raise ReportError("no forecasts on file for station %s" % stn)

        current = selection.current_forecast(forecasts)
        base_yield = forecasts[0].yield_t

        rows = []
        prev: Optional[float] = None
        for f in forecasts:
            delta = None if prev is None else (f.yield_t - prev)
            index = (f.yield_t / base_yield * 100.0) if base_yield else None
            is_current = current is not None and f.year == current.year
            rows.append(
                {
                    "year": f.year,
                    "yield_t": f.yield_t,
                    "delta": delta,
                    "index": index,
                    "ndays": f.ndays,
                    "model": f.model,
                    "run_at": f.run_at,
                    "cur": "*" if is_current else "",
                }
            )
            prev = f.yield_t

        head = self._single_standing_block(stn, forecasts, current)
        table = Block(
            heading="YIELD TREND BY YEAR",
            columns=self._single_columns(),
            rows=rows,
        )
        foot = self._single_summary_block(forecasts)
        return [head, table, foot]

    def _single_standing_block(
        self, stn: str, forecasts: List[Forecast], current: Optional[Forecast]
    ) -> Block:
        lines = [
            "  Station .............. %-10s  %s" % (stn, long_name(stn)),
            "  Region ............... %s" % region_of(stn),
            "  Years on file ........ %d  (%d..%d)"
            % (
                len(forecasts),
                min(f.year for f in forecasts),
                max(f.year for f in forecasts),
            ),
        ]
        if current is not None:
            lines += [
                "  Current run .......... %s  (crop year %d)"
                % (current.run_at, current.year),
                "  Model in force ....... %s" % current.model,
                "  Current yield ........ %.3f t/ha" % current.yield_t,
            ]
        return Block(heading="CURRENT STANDING", text_lines=lines)

    def _single_summary_block(self, forecasts: List[Forecast]) -> Block:
        ys = [f.yield_t for f in forecasts]
        mean = sum(ys) / len(ys)
        hi = max(forecasts, key=lambda f: f.yield_t)
        lo = min(forecasts, key=lambda f: f.yield_t)
        first, last = forecasts[0], forecasts[-1]
        net = last.yield_t - first.yield_t
        slope = _slope_per_year(forecasts)
        lines = [
            "  Mean yield ........... %.3f t/ha over %d year(s)"
            % (mean, len(ys)),
            "  Best year ............ %d  (%.3f t/ha)" % (hi.year, hi.yield_t),
            "  Worst year ........... %d  (%.3f t/ha)" % (lo.year, lo.yield_t),
            "  Net change ........... %+.3f t/ha  (%d -> %d)"
            % (net, first.year, last.year),
        ]
        if slope is not None:
            lines.append("  Trend slope .......... %+.3f t/ha per year" % slope)
        else:
            lines.append("  Trend slope .......... (undefined: one year on file)")
        lines.append("  Direction ............ %s" % _direction(net))
        return Block(heading="TREND SUMMARY", text_lines=lines)

    # -- province-wide mode ------------------------------------------------
    def _province_columns(self) -> ColumnSet:
        if self.config.is_wide():
            return ColumnSet(
                [
                    Column("stnid", "STN", 8, kind="text", align="left"),
                    Column("name", "STATION", 14, kind="text", align="left"),
                    Column("region", "REGION", 16, kind="text", align="left"),
                    Column("years", "YRS", 5, kind="int"),
                    Column("first", "FIRST", 9, kind="float", decimals=3,
                           unit="t/ha"),
                    Column("last", "LAST", 9, kind="float", decimals=3,
                           unit="t/ha"),
                    Column("mean", "MEAN", 9, kind="float", decimals=3,
                           unit="t/ha"),
                    Column("net", "NET", 9, kind="delta", decimals=3,
                           unit="t/ha"),
                    Column("slope", "SLOPE", 9, kind="delta", decimals=3,
                           unit="/yr"),
                    Column("dir", "DIR", 5, kind="text", align="left"),
                    Column("curyr", "CURYR", 6, kind="int"),
                ]
            )
        return ColumnSet(
            [
                Column("stnid", "STN", 8, kind="text", align="left"),
                Column("name", "STATION", 12, kind="text", align="left"),
                Column("years", "YRS", 4, kind="int"),
                Column("first", "FIRST", 9, kind="float", decimals=3,
                       unit="t/ha"),
                Column("last", "LAST", 9, kind="float", decimals=3,
                       unit="t/ha"),
                Column("net", "NET", 9, kind="delta", decimals=3, unit="t/ha"),
                Column("slope", "SLOPE", 9, kind="delta", decimals=3,
                       unit="/yr"),
                Column("curyr", "CURYR", 6, kind="int"),
            ]
        )

    def _province_blocks(self) -> List[Block]:
        stations = self.db.all_station_ids()
        if not stations:
            raise ReportError("no forecasts on file -- nothing to trend")

        rows = []
        risers = 0
        fallers = 0
        flats = 0
        for stn in stations:
            forecasts = self.db.forecasts_for_station(stn)
            if not forecasts:
                continue
            ys = [f.yield_t for f in forecasts]
            first, last = forecasts[0], forecasts[-1]
            net = last.yield_t - first.yield_t
            slope = _slope_per_year(forecasts)
            current = selection.current_forecast(forecasts)
            direction = _direction(net)
            if direction == "up":
                risers += 1
            elif direction == "down":
                fallers += 1
            else:
                flats += 1
            rows.append(
                {
                    "stnid": stn,
                    "name": long_name(stn),
                    "region": region_of(stn),
                    "years": len(forecasts),
                    "first": first.yield_t,
                    "last": last.yield_t,
                    "mean": sum(ys) / len(ys),
                    "net": net,
                    "slope": slope,
                    "dir": direction,
                    "curyr": current.year if current is not None else None,
                }
            )

        if not rows:
            raise ReportError("no forecasts on file -- nothing to trend")

        # Rank by net change descending so the strongest risers lead; a
        # stable tie-break on station id keeps the order deterministic.
        rows.sort(key=lambda r: (-r["net"], r["stnid"]))

        table = Block(
            heading="PER-STATION YIELD TREND",
            columns=self._province_columns(),
            rows=rows,
        )
        summary = self._province_summary_block(rows, risers, fallers, flats)
        return [table, summary]

    def _province_summary_block(
        self, rows, risers, fallers, flats
    ) -> Block:
        leader = rows[0]
        laggard = rows[-1]
        mean_of_means = sum(r["mean"] for r in rows) / len(rows)
        lines = [
            "  Stations with a trend  %d" % len(rows),
            "  Rising / falling / flat  %d / %d / %d"
            % (risers, fallers, flats),
            "  Province mean-of-means   %.3f t/ha" % mean_of_means,
            "  Strongest riser .......  %-10s %+.3f t/ha"
            % (leader["stnid"], leader["net"]),
            "  Steepest faller .......  %-10s %+.3f t/ha"
            % (laggard["stnid"], laggard["net"]),
        ]
        return Block(heading="PROVINCIAL TREND SUMMARY", text_lines=lines)
