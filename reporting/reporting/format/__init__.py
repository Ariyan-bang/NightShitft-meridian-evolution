"""Fixed-format rendering engine for Meridian reports.

This package is the machinery that turns a report's numbers into the
column-exact, banner-topped, paginated printouts the ministry files.  It
knows nothing about crops or forecasts; the report modules in
`reporting.reports` supply the data and the column specs, and this
package renders them.

Sub-modules:
    numfmt   -- per-field numeric/text formatting (right-align, overflow)
    columns  -- Column / ColumnSet: declarative table layout
    banner   -- the letterhead block
    layout   -- pagination, running headers and footers
    emitters -- ReportDocument/Block plus plaintext and CSV emitters

The public surface a report needs is re-exported here so a report can do
`from ..format import Column, ColumnSet, ReportDocument, Block`.
"""
from __future__ import annotations

from .banner import build_banner, build_section_head
from .columns import Column, ColumnSet, center_block
from .emitters import (
    Block,
    ReportDocument,
    emit_csv,
    emit_json,
    emit_text,
    write_output,
)

__all__ = [
    "Column",
    "ColumnSet",
    "center_block",
    "Block",
    "ReportDocument",
    "emit_text",
    "emit_csv",
    "emit_json",
    "write_output",
    "build_banner",
    "build_section_head",
]
