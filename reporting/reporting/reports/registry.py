"""Registry mapping report names to their classes.

The CLI and the nightly batch both need to turn a report name from a
control card ('season') into the class that builds it.  Rather than a
chain of if/elif in the CLI -- which is how this started, and which grew a
bug every time a report was added out of order -- the mapping lives here
in one table.

A report registers by name; unknown names raise a clear error listing the
ones that do exist, which is what the operator wants to see when they
fat-finger a control card at 6am.

    Table extracted from cli.py by P. Adeyemi, 2021 (MRD-176).
"""
from __future__ import annotations

from typing import Dict, List, Type

from .anomaly import AnomalyReport
from .base import BaseReport
from .coverage import CoverageReport
from .daily_detail import DailyDetailReport
from .season_summary import SeasonSummaryReport
from .station_report import StationReport
from .trend import TrendReport

# Ordered so `--help` and the usage banner list them in a sensible
# reading order (province-wide first, then station, then quality).
_REPORTS: List[Type[BaseReport]] = [
    SeasonSummaryReport,
    StationReport,
    TrendReport,
    DailyDetailReport,
    AnomalyReport,
    CoverageReport,
]

_BY_NAME: Dict[str, Type[BaseReport]] = {r.name: r for r in _REPORTS}


def report_names() -> List[str]:
    return [r.name for r in _REPORTS]


def report_titles() -> List[tuple]:
    """(name, title) pairs for help text."""
    return [(r.name, r.title) for r in _REPORTS]


def get_report_class(name: str) -> Type[BaseReport]:
    key = (name or "").strip().lower()
    if key not in _BY_NAME:
        raise KeyError(
            "unknown report %r; known reports: %s"
            % (name, ", ".join(report_names()))
        )
    return _BY_NAME[key]
