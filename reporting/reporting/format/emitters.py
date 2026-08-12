"""Output emitters: plaintext and CSV.

A report is assembled internally as a structured object -- a banner, some
section blocks, and one or more tables described by ColumnSets and row
dicts.  An *emitter* turns that structure into bytes:

  * the plaintext emitter is the real product: the fixed-format,
    paginated, banner-topped printout the ministry files.  It is the
    default and the one the fixed-format contract is about.

  * the CSV emitter is a convenience the spreadsheet users asked for in
    2004.  It throws the banner and pagination away and emits just the
    table rows with a header line, so the numbers can be pulled into a
    spreadsheet.  It is explicitly NOT fixed-format and carries a comment
    saying so, because every couple of years someone tries to parse the
    plaintext with a CSV reader and we point them here instead.

    CSV emitter: R. Halloran, 2004; quoting fixed 2019 after a station
    with a comma in a free-text note broke a downstream import (MRD-201).
"""
from __future__ import annotations

import csv
import io
import json
from typing import Any, Dict, List, Optional, Sequence

from .columns import ColumnSet
from .layout import BodyLine, PageContext, Paginator


class ReportDocument:
    """The in-memory form of a report before it is emitted.

    A report builds one of these; an emitter consumes it.  It holds:
      banner      -- pre-rendered banner lines
      blocks      -- ordered list of Block objects (section head + table
                     and/or free text)
      running_title, ref_code, width, lines_per_page -- for pagination
    """

    def __init__(
        self,
        *,
        width: int,
        lines_per_page: int,
        running_title: str,
        ref_code: Optional[str] = None,
    ):
        self.width = width
        self.lines_per_page = lines_per_page
        self.running_title = running_title
        self.ref_code = ref_code
        self.banner: List[str] = []
        self.blocks: List[Block] = []

    def add_block(self, block: "Block") -> None:
        self.blocks.append(block)


class Block:
    """A section of a report: an optional heading, optional free-text
    lines, and an optional table (ColumnSet + rows).

    A report is a list of these.  Keeping tables structured (rather than
    pre-rendered) is what lets the CSV emitter exist at all -- it reads
    the ColumnSet and rows directly and ignores the heading/free text.
    """

    def __init__(
        self,
        heading: Optional[str] = None,
        head_lines: Optional[List[str]] = None,
        columns: Optional[ColumnSet] = None,
        rows: Optional[Sequence[dict]] = None,
        text_lines: Optional[List[str]] = None,
        show_units: bool = True,
    ):
        self.heading = heading
        self.head_lines = head_lines or []
        self.columns = columns
        self.rows = list(rows) if rows is not None else []
        self.text_lines = text_lines or []
        self.show_units = show_units


# --- plaintext ------------------------------------------------------------
def emit_text(doc: ReportDocument, paginate: bool = True) -> str:
    """Render `doc` as the fixed-format plaintext printout."""
    body: List[BodyLine] = []
    repeat_header: List[str] = []

    for bi, block in enumerate(doc.blocks):
        if bi > 0:
            body.append(BodyLine("", breakable_before=False))
        if block.heading:
            for hl in _heading_lines(block.heading, doc.width):
                body.append(BodyLine(hl, breakable_before=False))
        for hl in block.head_lines:
            body.append(BodyLine(hl, breakable_before=False))
        for tl in block.text_lines:
            body.append(BodyLine(tl, breakable_before=True))
        if block.columns is not None:
            hdr = _table_header_lines(block)
            # first table in the doc supplies the repeat-on-break header
            if not repeat_header:
                repeat_header = list(hdr)
            for hl in hdr:
                body.append(BodyLine(hl, breakable_before=False))
            for row in block.rows:
                body.append(BodyLine(block.columns.row_line(row), breakable_before=True))

    if not paginate:
        return "\n".join(doc.banner + [bl.text for bl in body]) + "\n"

    ctx = PageContext(
        running_title=doc.running_title,
        width=doc.width,
        lines_per_page=doc.lines_per_page,
        ref_code=doc.ref_code,
    )
    pg = Paginator(ctx)
    out = pg.paginate(doc.banner, body, repeat_on_break=repeat_header or None)
    return "\n".join(out) + "\n"


def _heading_lines(heading: str, width: int) -> List[str]:
    from .banner import build_section_head

    return build_section_head(heading, width)


def _table_header_lines(block: Block) -> List[str]:
    cs = block.columns
    lines = [cs.header_line()]
    if block.show_units and cs.has_units():
        lines.append(cs.unit_line())
    lines.append(cs.rule("-"))
    return lines


# --- CSV ------------------------------------------------------------------
def emit_csv(doc: ReportDocument) -> str:
    """Render the report's tables as CSV.

    NOT fixed-format: banner, pagination and section rules are dropped.
    Multiple tables in one report are separated by a blank line and a
    '# <heading>' comment row so a human can still tell them apart, but a
    strict CSV consumer should ask for a report with a single table.
    """
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    wrote_any = False
    for block in doc.blocks:
        if block.columns is None:
            continue
        if wrote_any:
            writer.writerow([])
        if block.heading:
            writer.writerow(["# " + block.heading])
        wrote_any = True
        cs = block.columns
        writer.writerow([c.title.strip() for c in cs.columns])
        for row in block.rows:
            writer.writerow([_csv_cell(row.get(c.key)) for c in cs.columns])
    return buf.getvalue()


def _csv_cell(value) -> str:
    """Render a raw value for CSV.

    We emit the *value*, not the fixed-width field -- a spreadsheet does
    its own alignment.  None becomes an empty cell.  Floats are left to
    str() so the full precision reaches the spreadsheet; the fixed-format
    rounding is a print concern, not a data concern.
    """
    if value is None:
        return ""
    return str(value)


# --- JSON -----------------------------------------------------------------
def emit_json(doc: ReportDocument, *, indent: Optional[int] = 2) -> str:
    """Render the report's tables as a machine-readable JSON document.

    A sibling of the CSV emitter, for callers that want the numbers
    structured rather than a flat sheet: the nightly batch feeds this
    into the ministry's data warehouse, which wants typed values and the
    column metadata, not a fixed-width printout.  Like CSV it is
    explicitly NOT fixed-format -- the banner, pagination and section
    rules are dropped and only the structured tables survive.

    Shape::

        {
          "report": {"title": ..., "reference": ...},
          "tables": [
            {
              "heading": "...",
              "columns": [{"key","title","unit","kind"}, ...],
              "rows": [{<key>: <typed value>, ...}, ...]
            }, ...
          ]
        }

    Values are emitted at full precision (``None`` -> JSON ``null``); the
    fixed-format rounding is a print concern and is not applied here.  The
    output is 7-bit ASCII (``ensure_ascii``) so it travels the same line
    as the plaintext reports do.
    """
    tables: List[Dict[str, Any]] = []
    for block in doc.blocks:
        if block.columns is None:
            continue
        cs = block.columns
        columns = [
            {
                "key": c.key,
                "title": c.title.strip(),
                "unit": c.unit,
                "kind": c.kind,
            }
            for c in cs.columns
        ]
        rows = [
            {c.key: _json_cell(row.get(c.key)) for c in cs.columns}
            for row in block.rows
        ]
        tables.append(
            {"heading": block.heading, "columns": columns, "rows": rows}
        )

    payload: Dict[str, Any] = {
        "report": {
            "title": doc.running_title,
            "reference": doc.ref_code,
        },
        "tables": tables,
    }
    return json.dumps(payload, ensure_ascii=True, indent=indent) + "\n"


def _json_cell(value):
    """Coerce a raw cell value to a JSON-friendly scalar.

    Numbers and None pass straight through (so a reader gets a real
    number / null, not a string); anything else is stringified, matching
    the CSV emitter's "the spreadsheet does its own typing" stance for
    labels and flag strings.
    """
    if value is None or isinstance(value, (int, float, bool)):
        return value
    return str(value)


def write_output(text: str, path: Optional[str]) -> None:
    """Write rendered text to a file, or stdout when path is None.

    We write in text mode with a trailing newline already present.  The
    form-feed characters in a paginated report are written as-is; they
    are what the line printer wants and pagers tolerate them.
    """
    if path is None:
        import sys

        sys.stdout.write(text)
        return
    with open(path, "w", encoding="ascii", errors="replace", newline="\n") as fh:
        fh.write(text)
