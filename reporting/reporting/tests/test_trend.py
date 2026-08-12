"""Tests for the additions in this cycle: the trend report, the JSON
export emitter, and the centralised run-selection helpers.

Happy-path only, in the same spirit as the existing render tests: do the
new pieces render/compute, and do the headline numbers land.
"""
from __future__ import annotations

import json

import pytest

from ..cli import run_report
from ..config import FMT_JSON, WIDTH_NARROW, WIDTH_WIDE
from ..db import ReportDB
from ..reports import selection
from .conftest import make_config


# --- trend report: single station ----------------------------------------
def test_trend_single_station_renders(store_path):
    cfg = make_config(store_path, "trend", station="GUELPH", width=WIDTH_WIDE)
    out = run_report(cfg)
    assert "YIELD TREND -- GUELPH" in out
    assert "CURRENT STANDING" in out
    assert "YIELD TREND BY YEAR" in out
    # both years present, YoY delta 8.221-7.812 = +0.409
    assert "2020" in out and "2021" in out
    assert "+0.409" in out
    # index against first year: 8.221/7.812*100 == 105.2
    assert "105.2" in out


def test_trend_single_station_marks_current_run(store_path):
    # The current run for GUELPH is the 2021 row (newer run_at), so the
    # trend summary reports crop year 2021 as the current standing.
    cfg = make_config(store_path, "trend", station="GUELPH", width=WIDTH_WIDE)
    out = run_report(cfg)
    assert "crop year 2021" in out
    assert "cropmod-4.2" in out


def test_trend_single_station_slope_and_direction(store_path):
    cfg = make_config(store_path, "trend", station="GUELPH")
    out = run_report(cfg)
    assert "TREND SUMMARY" in out
    assert "Net change" in out
    assert "Direction ............ up" in out


# --- trend report: province-wide ------------------------------------------
def test_trend_province_renders(store_path):
    cfg = make_config(store_path, "trend", width=WIDTH_WIDE)
    out = run_report(cfg)
    assert "YIELD TREND -- ALL STATIONS" in out
    assert "PER-STATION YIELD TREND" in out
    # three stations have forecasts in the fixture
    assert "GUELPH" in out and "KITCHNER" in out and "WATERLOO" in out


def test_trend_province_ranks_by_net_change(store_path):
    # Net change: GUELPH +0.409, WATERLOO +0.326, KITCHNER -0.355.
    # Ranked descending: GUELPH, WATERLOO, KITCHNER.
    cfg = make_config(store_path, "trend", width=WIDTH_WIDE)
    out = run_report(cfg)
    assert out.index("GUELPH") < out.index("WATERLOO") < out.index("KITCHNER")
    # two rising, one falling
    assert "Rising / falling / flat  2 / 1 / 0" in out


def test_trend_both_widths_fit_page(store_path):
    for w in (WIDTH_NARROW, WIDTH_WIDE):
        for kw in ({"station": "GUELPH"}, {}):
            cfg = make_config(store_path, "trend", width=w, **kw)
            out = run_report(cfg)
            for line in out.splitlines():
                if line == "\f":
                    continue
                assert len(line) <= w, "trend line over %d cols: %r" % (w, line)


# --- JSON export emitter --------------------------------------------------
def test_json_export_is_parseable_and_has_no_banner(store_path):
    cfg = make_config(store_path, "season", year=2021, fmt=FMT_JSON)
    out = run_report(cfg)
    assert "PROVINCIAL AGRI-ENVIRONMENTAL MONITORING" not in out
    doc = json.loads(out)
    assert doc["report"]["reference"] == "SEAS-2021"
    assert isinstance(doc["tables"], list) and doc["tables"]
    # the ranked per-station table carries typed yields, GUELPH at 8.221
    table = doc["tables"][0]
    keys = {c["key"] for c in table["columns"]}
    assert "yield_t" in keys
    yields = [r["yield_t"] for r in table["rows"]]
    assert pytest.approx(max(yields), abs=1e-6) == 8.221
    # a float stays a JSON number, not a string
    assert isinstance(yields[0], float)


def test_json_export_trend(store_path):
    cfg = make_config(store_path, "trend", fmt=FMT_JSON)
    out = run_report(cfg)
    doc = json.loads(out)
    assert doc["report"]["reference"] == "TRND-ALL"
    headings = [t["heading"] for t in doc["tables"]]
    assert "PER-STATION YIELD TREND" in headings


# --- run-selection helpers ------------------------------------------------
def test_selection_current_forecast_uniform_timestamps(store_path):
    with ReportDB(store_path) as db:
        forecasts = db.forecasts_for_station("GUELPH")
    current = selection.current_forecast(forecasts)
    assert current is not None
    # 2021 run_at (2021-08-16...) is newer than 2020 (2020-08-15...)
    assert current.year == 2021
    assert current.model == "cropmod-4.2"
    assert selection.current_run_at(forecasts) == "2021-08-16T06:00:00"


def test_selection_order_by_recency(store_path):
    with ReportDB(store_path) as db:
        forecasts = db.forecasts_for_station("GUELPH")
    ordered = selection.order_by_recency(forecasts)
    assert [f.year for f in ordered] == [2021, 2020]


def test_selection_current_by_station(store_path):
    with ReportDB(store_path) as db:
        forecasts = (
            db.forecasts_for_station("GUELPH")
            + db.forecasts_for_station("KITCHNER")
        )
    current = selection.current_by_station(forecasts)
    assert set(current) == {"GUELPH", "KITCHNER"}
    assert current["GUELPH"].year == 2021
    assert current["KITCHNER"].year == 2021


def test_selection_empty_is_none():
    assert selection.current_forecast([]) is None
    assert selection.current_run_at([]) is None
