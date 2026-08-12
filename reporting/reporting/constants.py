"""Station tables, units and other fixed lore for the reports.

None of this changes at run time.  The station roster is fixed by the
telemetry contract (see docs/CONTRACTS.md): six stations, ids of eight
characters or fewer, space-padded in the wire frame.  We keep the long
names here because the ministry insists the printed reports spell them
out in full -- "GUELPH" on a wire frame, "Guelph" on a printout that a
deputy minister might read.

Originally these lived in a flat text file (STATIONS.DAT) that the
COBOL writer READ at start-up.  When the report writer was rewritten in
Python the table was inlined so there is one less file to lose.
"""
from __future__ import annotations

# --- Station roster -------------------------------------------------------
# Order here is the *canonical report order*.  Season summaries are
# re-ranked by yield, but coverage and roster listings walk this order so
# that two printouts of the same run line up row for row.
STATION_IDS = [
    "GUELPH",
    "KITCHNER",
    "WATERLOO",
    "CAMBRIDG",
    "MILTON",
    "BRANTFRD",
]

# Long names as the ministry wants them spelled on paper.  The wire ids
# are truncated/abbreviated to fit eight columns; these are not.
STATION_LONG_NAMES = {
    "GUELPH": "Guelph",
    "KITCHNER": "Kitchener",
    "WATERLOO": "Waterloo",
    "CAMBRIDG": "Cambridge",
    "MILTON": "Milton",
    "BRANTFRD": "Brantford",
}

# County / administrative region, printed on the station report header.
STATION_REGIONS = {
    "GUELPH": "Wellington",
    "KITCHNER": "Waterloo Region",
    "WATERLOO": "Waterloo Region",
    "CAMBRIDG": "Waterloo Region",
    "MILTON": "Halton",
    "BRANTFRD": "Brant",
}


def long_name(stnid: str) -> str:
    """Full station name for headers; falls back to the raw id.

    Old data occasionally carried a station id we no longer recognise
    (a decommissioned site, a typo from the manual-entry days).  Rather
    than crash a report over one bad row we echo the id back.
    """
    return STATION_LONG_NAMES.get(stnid.strip().upper(), stnid.strip())


def region_of(stnid: str) -> str:
    return STATION_REGIONS.get(stnid.strip().upper(), "-")


def is_known_station(stnid: str) -> bool:
    return stnid.strip().upper() in STATION_LONG_NAMES


# --- Units ----------------------------------------------------------------
# Printed in column sub-headers.  Kept as a table so the 80- and 132-col
# layouts agree on the wording.
UNITS = {
    "yield_t": "t/ha",
    "tmax": "degC",
    "tmin": "degC",
    "rain": "mm",
    "srad": "MJ/m2",
    "rh": "%",
    "wind": "m/s",
    "sw": "mm",
    "et": "mm",
    "drain": "mm",
    "biom": "g/m2",
    "lai": "m2/m2",
}

# Column captions for the daily-detail table.  The model output doc
# (docs/OUTFMT.txt) fixes the physical meaning; these are the human
# captions we print above each column.
DAILY_CAPTIONS = {
    "doy": "DOY",
    "sw": "SoilWat",
    "et": "ET",
    "drain": "Drain",
    "biom": "Biomass",
    "lai": "LAI",
}

# --- Flag bits (from the telemetry contract) ------------------------------
FLAG_SUSPECT = 0x0001  # value failed a range/consistency check on ingest
FLAG_MANUAL = 0x0002  # hand-entered or hand-corrected reading


def flag_labels(flags: int) -> str:
    """Compact human rendering of the flag bits for a reading.

    Returns something like 'SUS' or 'SUS+MAN' or '-' for none set.
    """
    parts = []
    if flags & FLAG_SUSPECT:
        parts.append("SUS")
    if flags & FLAG_MANUAL:
        parts.append("MAN")
    # Any high bits we do not know about get shown as HEX so a future
    # ingest change is at least visible on the printout.
    known = FLAG_SUSPECT | FLAG_MANUAL
    if flags & ~known:
        parts.append("x%02X" % (flags & ~known))
    return "+".join(parts) if parts else "-"


# --- Report identifiers ---------------------------------------------------
# The short codes double as the ministry's file-reference prefixes; a
# printed season summary for 2021 is filed as "SEAS-2021-..." and so on.
REPORT_CODES = {
    "season": "SEAS",
    "station": "STNR",
    "daily": "DALY",
    "anomaly": "ANOM",
    "coverage": "COVR",
    "trend": "TRND",
}

# Fortran-style overflow marker.  When a numeric field will not fit its
# width we print this instead of a wrong number -- same convention the
# model output uses (see MRD-143 in docs/OUTFMT.txt).
OVERFLOW_MARK = "*"
