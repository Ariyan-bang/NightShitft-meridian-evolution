"""Command-line entry point for the report writer.

Usage grew from a punched control card, to a shell wrapper that positional-
parsed $1 $2 $3, to this argparse front end in the 2011 rewrite.  The
positional legacy still shows: `report` is a positional argument because
every operator's muscle memory types the report name first.

The CLI does three things and no more:
  1. parse argv into a ReportConfig,
  2. open the store read-only,
  3. build the chosen report and write it out.

Everything else -- what a season summary looks like, how a field is
right-justified -- lives in the report and format packages.  Keeping the
CLI thin is why the nightly batch (tools/nightly.sh in the ops tree) can
drive the same reports by importing run_report() directly instead of
shelling out per station.

    argparse front end: 2011 rewrite.  --width/--format flags 2021
    (P. Adeyemi).  --list added after one too many "what reports are
    there again?" phone calls.
"""
from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from .config import (
    FMT_CSV,
    FMT_JSON,
    FMT_TEXT,
    SUPPORTED_FORMATS,
    SUPPORTED_WIDTHS,
    WIDTH_NARROW,
    WIDTH_WIDE,
    DEFAULT_DB,
    ReportConfig,
)
from .db import ReportDB, ReportDBError
from .reports import ReportError, get_report_class, report_titles
from .version import __version__

PROG = "reporting"


def build_parser() -> argparse.ArgumentParser:
    epilog = _reports_help() + "\n\nExamples:\n" + _examples_help()
    p = argparse.ArgumentParser(
        prog=PROG,
        description=(
            "Meridian fixed-format report writer -- reads the forecast "
            "store and prints the operational reports the provincial "
            "agri-environmental monitoring programme files."
        ),
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "report",
        nargs="?",
        help="which report to run (see the list below); omit with --list",
    )
    p.add_argument(
        "--db",
        default=DEFAULT_DB,
        metavar="PATH",
        help="path to the SQLite forecast store (default: %(default)s or "
        "$MERIDIAN_DB)",
    )
    p.add_argument(
        "-s",
        "--station",
        metavar="STNID",
        help="station id, e.g. GUELPH (required by station/daily reports)",
    )
    p.add_argument(
        "-y",
        "--year",
        type=int,
        metavar="YYYY",
        help="crop year (required by season/daily; optional filter for anomaly)",
    )
    p.add_argument(
        "-w",
        "--width",
        type=int,
        default=WIDTH_NARROW,
        choices=SUPPORTED_WIDTHS,
        metavar="COLS",
        help="page width in columns: %d (greenbar) or %d (wide fan-fold); "
        "default %d" % (WIDTH_NARROW, WIDTH_WIDE, WIDTH_NARROW),
    )
    p.add_argument(
        "-f",
        "--format",
        dest="fmt",
        default=FMT_TEXT,
        choices=SUPPORTED_FORMATS,
        help="output format: '%s' (fixed-format printout), '%s' "
        "(spreadsheet import) or '%s' (machine-readable export); the last "
        "two are not fixed-format; default '%s'"
        % (FMT_TEXT, FMT_CSV, FMT_JSON, FMT_TEXT),
    )
    p.add_argument(
        "-o",
        "--output",
        metavar="FILE",
        help="write to FILE instead of standard output",
    )
    p.add_argument(
        "--no-paginate",
        action="store_true",
        help="suppress page headers/footers and form feeds (text format "
        "only); handy for screen viewing and diffs",
    )
    p.add_argument(
        "--note",
        metavar="TEXT",
        help="free-text note stamped into the banner (e.g. the spool id)",
    )
    p.add_argument(
        "--list",
        action="store_true",
        help="list the available reports and exit",
    )
    p.add_argument(
        "--version",
        action="version",
        version="%(prog)s (Meridian report writer) " + __version__,
    )
    return p


def _reports_help() -> str:
    lines = ["Reports:"]
    for name, title in report_titles():
        lines.append("  %-10s %s" % (name, title))
    return "\n".join(lines)


def _examples_help() -> str:
    return "\n".join(
        [
            "  %s season --year 2021 --db meridian.sqlite" % PROG,
            "  %s station --station GUELPH --width 132" % PROG,
            "  %s daily -s WATERLOO -y 2021 -w 132 -o waterloo2021.txt" % PROG,
            "  %s trend --station GUELPH --width 132" % PROG,
            "  %s trend --format json -o trend.json" % PROG,
            "  %s anomaly --year 2021" % PROG,
            "  %s coverage --format csv" % PROG,
        ]
    )


def config_from_args(args: argparse.Namespace) -> ReportConfig:
    cfg = ReportConfig(
        report=args.report,
        db_path=args.db,
        station=args.station,
        year=args.year,
        width=args.width,
        fmt=args.fmt,
        output=args.output,
        paginate=not args.no_paginate,
        note=args.note,
    )
    cfg.validate()
    return cfg


def run_report(cfg: ReportConfig) -> str:
    """Open the store, build the report, return the rendered text.

    Importable by the nightly batch.  Raises ReportError/ReportDBError on
    a problem; the CLI wrapper turns those into a message + exit code.
    """
    cls = get_report_class(cfg.report)
    with ReportDB(cfg.db_path) as db:
        report = cls(cfg, db)
        return report.render()


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list:
        sys.stdout.write(_reports_help() + "\n")
        return 0

    if not args.report:
        parser.error("no report chosen (try --list to see them)")

    # CSV + no-paginate is a no-op combo, but harmless; text + no-paginate
    # is the interesting one.  We do not forbid odd-but-harmless combos.
    try:
        cfg = config_from_args(args)
    except ValueError as exc:
        parser.error(str(exc))

    from .format import write_output

    try:
        text = run_report(cfg)
    except KeyError as exc:
        # unknown report name from the registry
        sys.stderr.write("%s: %s\n" % (PROG, exc))
        return 2
    except ReportError as exc:
        sys.stderr.write("%s: %s\n" % (PROG, exc))
        return 1
    except ReportDBError as exc:
        sys.stderr.write("%s: database error: %s\n" % (PROG, exc))
        return 1

    write_output(text, cfg.output)
    if cfg.output:
        sys.stderr.write(
            "%s: wrote %s report to %s\n" % (PROG, cfg.report, cfg.output)
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
