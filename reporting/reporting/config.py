"""Run-time configuration for a report invocation.

Everything the CLI collects gets funnelled into a single ReportConfig
object which is then handed to a report.  Reports never read argv or the
environment directly; they read the config.  This made the batch-mode
wrapper (the nightly cron that prints every station's season summary)
easy to write without going through argparse.

The old COBOL writer took its parameters as a punched control card;
the field order here still echoes that card, which is why width comes
before output path even though nobody remembers the card any more.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

# Layout widths we support.  80 is the teletype/greenbar default; 132 is
# the wide fan-fold the ministry switched to in 2021 for the daily
# detail tables that would not fit in 80 columns.
WIDTH_NARROW = 80
WIDTH_WIDE = 132
SUPPORTED_WIDTHS = (WIDTH_NARROW, WIDTH_WIDE)

# Emitter formats.
FMT_TEXT = "text"
FMT_CSV = "csv"
FMT_JSON = "json"
SUPPORTED_FORMATS = (FMT_TEXT, FMT_CSV, FMT_JSON)

# Default database path.  In production this is a symlink the collector
# and analytics both write through; for reports it is opened read-only.
DEFAULT_DB = os.environ.get("MERIDIAN_DB", "meridian.sqlite")

# How many report rows go on a printed page before we throw a form-feed
# and re-print the running header.  The greenbar stock the ministry
# buys is 66 lines; leave room for banner + column head + footer.
LINES_PER_PAGE_66 = 60
LINES_PER_PAGE_88 = 82  # the wide fan-fold is taller too


@dataclass
class ReportConfig:
    """Immutable-ish bag of run parameters.

    We do not make it frozen because the CLI layer occasionally has to
    back-fill a default (e.g. choose a year when the user omitted one)
    after construction.
    """

    report: str
    db_path: str = DEFAULT_DB
    station: Optional[str] = None
    year: Optional[int] = None
    width: int = WIDTH_NARROW
    fmt: str = FMT_TEXT
    output: Optional[str] = None  # None => stdout
    paginate: bool = True
    title_override: Optional[str] = None
    # A free-text note stamped into the banner; the nightly batch uses
    # it to record which spool the run came from.
    note: Optional[str] = None
    extras: dict = field(default_factory=dict)

    def lines_per_page(self) -> int:
        return LINES_PER_PAGE_88 if self.width == WIDTH_WIDE else LINES_PER_PAGE_66

    def is_wide(self) -> bool:
        return self.width == WIDTH_WIDE

    def validate(self) -> None:
        """Raise ValueError on an incoherent configuration.

        Called by the CLI after parsing but before any database work so
        the operator gets a clean message instead of a stack trace half
        way through a print run.
        """
        if self.width not in SUPPORTED_WIDTHS:
            raise ValueError(
                "unsupported width %r (want one of %s)"
                % (self.width, ", ".join(str(w) for w in SUPPORTED_WIDTHS))
            )
        if self.fmt not in SUPPORTED_FORMATS:
            raise ValueError(
                "unsupported format %r (want one of %s)"
                % (self.fmt, ", ".join(SUPPORTED_FORMATS))
            )
        if self.year is not None and not (1900 <= self.year <= 2100):
            raise ValueError("year %r out of range 1900..2100" % (self.year,))
        if self.station is not None and not self.station.strip():
            raise ValueError("station id is blank")

    def normalized_station(self) -> Optional[str]:
        if self.station is None:
            return None
        return self.station.strip().upper()
