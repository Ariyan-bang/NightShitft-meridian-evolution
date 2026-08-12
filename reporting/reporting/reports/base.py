"""Base class shared by every report type.

A report is a small object that, given a ReportConfig and an open
ReportDB, builds a ReportDocument (banner + blocks) which an emitter then
turns into text or CSV.  The base class handles the parts every report
shares -- constructing the banner, picking the page geometry from the
config, choosing the emitter -- so each concrete report only has to say
what its subtitle is and produce its blocks.

The template-method shape (build_document calls the subclass's
build_blocks) is deliberately old-fashioned; it predates the CSV emitter
and has survived every rewrite because it keeps the report modules short.

    R. Halloran, 2017; emitter selection moved into the base 2011 rewrite,
    kept when the class was re-typed in 2019.
"""
from __future__ import annotations

import datetime as _dt
from typing import List, Optional

from ..config import FMT_CSV, FMT_JSON, ReportConfig
from ..constants import REPORT_CODES
from ..db import ReportDB
from ..format import (
    Block,
    ReportDocument,
    build_banner,
    emit_csv,
    emit_json,
    emit_text,
)


class ReportError(Exception):
    """Raised when a report cannot be built (bad params, no data)."""


class BaseReport:
    """Abstract report.  Subclasses set `name`/`code` and override the
    two build_* hooks."""

    #: short lowercase identifier used on the CLI (e.g. 'season')
    name: str = "base"
    #: human title used in the banner subtitle
    title: str = "REPORT"
    #: ministry file-reference code prefix
    code: str = "RPT"

    def __init__(self, config: ReportConfig, db: ReportDB):
        self.config = config
        self.db = db
        self._generated_at = _dt.datetime.now()

    # -- hooks a subclass overrides ---------------------------------------
    def subtitle(self) -> str:
        """The report-specific banner line, e.g. 'SEASON SUMMARY -- 2021'.

        Default is just the title; most reports append their scope.
        """
        return self.title

    def ref_code(self) -> Optional[str]:
        """Ministry file reference, e.g. 'SEAS-2021'.  Optional."""
        return None

    def running_title(self) -> str:
        """One-line reminder printed atop continuation pages."""
        return self.subtitle()

    def build_blocks(self) -> List[Block]:  # pragma: no cover - abstract
        raise NotImplementedError

    # -- shared machinery --------------------------------------------------
    def _new_document(self) -> ReportDocument:
        doc = ReportDocument(
            width=self.config.width,
            lines_per_page=self.config.lines_per_page(),
            running_title=self.running_title(),
            ref_code=self.ref_code(),
        )
        doc.banner = build_banner(
            self.subtitle(),
            self.config.width,
            db_path=self.config.db_path,
            generated_at=self._generated_at,
            source_run_at=self._source_run_at(),
            note=self.config.note,
            ref_code=self.ref_code(),
        )
        return doc

    def _source_run_at(self) -> Optional[str]:
        """The newest forecast run the data came from, for the banner.

        Reports over readings (anomaly) have no forecast run; they return
        None and the banner shows '(none)'.  Overridable.
        """
        try:
            return self.db.latest_run_at()
        except Exception:
            return None

    def build_document(self) -> ReportDocument:
        doc = self._new_document()
        for block in self.build_blocks():
            doc.add_block(block)
        return doc

    def render(self) -> str:
        """Build and emit the report as a string per the config's format."""
        doc = self.build_document()
        if self.config.fmt == FMT_CSV:
            return emit_csv(doc)
        if self.config.fmt == FMT_JSON:
            return emit_json(doc)
        return emit_text(doc, paginate=self.config.paginate)

    # -- helpers subclasses lean on ---------------------------------------
    def _require_station(self) -> str:
        stn = self.config.normalized_station()
        if not stn:
            raise ReportError("%s requires a station (--station)" % self.name)
        return stn

    def _require_year(self) -> int:
        if self.config.year is None:
            raise ReportError("%s requires a year (--year)" % self.name)
        return self.config.year

    def _default_ref(self, scope: str) -> str:
        prefix = REPORT_CODES.get(self.name, self.code)
        return "%s-%s" % (prefix, scope)
