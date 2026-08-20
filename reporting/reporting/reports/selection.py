"""Run-selection helpers: which forecast run is "current".

Several reports have to answer the same small question in the same small
way: given the forecast rows on file for a station (at most one per crop
year, per the store schema), which one is the *current* run -- the most
recently computed, the figure "in force"?  The station report has asked
this since 2021 via ``db.latest_forecast_for_station``; the trend report
added in this cycle asks it too.  Rather than let each report grow its
own copy of the ordering rule -- which is how the writer accumulated
subtly different answers in the past -- the rule lives here, once, and
the reports call it.

The ordering key is a forecast's ``run_at``: the timestamp the analytics
job stamps when it writes the row.  The newest ``run_at`` is the current
run.  Ties (two rows stamped at the same instant, which a same-batch
backfill can produce) are broken by crop year, newest year first, so the
selection is deterministic run to run.

    New in this cycle.  Centralises the per-report run selection that had
    been duplicated into station_report and (via SQL) into db.py.

Known limitation
----------------
``run_at`` is compared as text here (see ``_recency_key``).  For the
timestamps the analytics job writes today -- ISO-8601, zero-padded, fixed
width -- text order and time order are the same, so this is correct on
all current data and on the seeded test store.  It is **not** correct for
a run whose ``run_at`` was written in a different textual shape, e.g. a
manual backfill stamped ``08/16/2021 06:00`` (day/month/year) rather than
``2021-08-16T06:00:00``: that string sorts *before* the ISO stamps
because ``'0' < '2'``, so a newer backfill can be mistaken for an older
run.  This is the same text-vs-time hazard tracked for the SQL path in
MRD-238; it is latent here until such a run appears in the store.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from ..db import Forecast


def _recency_key(run_at: Optional[str]) -> str:
    """Comparison key for ordering runs by recency.

    The analytics job writes ``run_at`` as an ISO-8601 stamp, so the text
    order of two stamps already matches their time order and we can order
    on the normalised text directly without parsing a datetime.

    (This is the seam the MRD-238 text-ordering hazard lives behind: for
    an off-format backfill the text order and the time order diverge.)
    """
    return (run_at or "").strip()


def current_forecast(forecasts: Sequence[Forecast]) -> Optional[Forecast]:
    """The current (most recently run) forecast from a set of rows.

    ``forecasts`` is typically every year on file for one station.  The
    row with the newest ``run_at`` wins; on a tie the newest crop year
    wins so the choice is deterministic.  Returns None for an empty set.
    """
    chosen: Optional[Forecast] = None
    chosen_key = None
    for f in forecasts:
        key = (_recency_key(f.run_at), f.year)
        if chosen is None or key > chosen_key:
            chosen = f
            chosen_key = key
    return chosen


def current_run_at(forecasts: Sequence[Forecast]) -> Optional[str]:
    """The ``run_at`` of the current forecast, or None for an empty set."""
    cur = current_forecast(forecasts)
    return cur.run_at if cur is not None else None


def order_by_recency(forecasts: Sequence[Forecast]) -> List[Forecast]:
    """All rows ordered newest run first (ties: newest crop year first)."""
    return sorted(
        forecasts,
        key=lambda f: (_recency_key(f.run_at), f.year),
        reverse=True,
    )


def current_by_station(
    forecasts: Sequence[Forecast],
) -> Dict[str, Forecast]:
    """Map each station id to its current forecast.

    Groups a flat list of forecast rows by station and applies
    :func:`current_forecast` within each group.  Handy when a report has
    pulled a wide slice of the store and wants the in-force row per site
    without a query per station.
    """
    groups: Dict[str, List[Forecast]] = {}
    for f in forecasts:
        groups.setdefault(f.stnid, []).append(f)
    return {stn: current_forecast(rows) for stn, rows in groups.items()
            if current_forecast(rows) is not None}
