"""Opt-in soil-parameter configuration loader.

    -- Nightshift (orchestration) side, experimental --

Soil parameters (available water capacity and rooting depth) are hard
coded in deck.py because the 2008 ``reading`` schema has nowhere to put
them (MRD-91).  That dict IS the soil registry today, and the deck writer
must not be "improved" into a lookup against a table that does not exist.

This module is the first step towards closing MRD-91 WITHOUT touching the
schema: it reads the same per-station parameters from an external config
file (YAML or INI) into a :class:`SoilRegistry`, so an operator can adjust
them without editing code.  It is strictly OPT-IN.  deck.py and the
default run path keep using their hard-coded SOIL / LATITUDE dicts, so the
nightly forecast is unchanged (GUELPH still 5.951 t/ha).  A caller that
wants file-driven parameters loads a registry here and passes it to
:func:`spec_from_readings_with` instead of calling deck.spec_from_readings.

The file format mirrors the hard-coded values one-for-one:

    stations:
      GUELPH:   {awc: 0.150, rooting_depth_mm: 1100.0, latitude: 43.545}
      KITCHNER: {awc: 0.142, rooting_depth_mm: 1050.0}
    defaults: {awc: 0.145, rooting_depth_mm: 1000.0, latitude: 43.545}

INI is accepted too, one ``[STATION]`` section per station plus an
optional ``[defaults]`` section, same keys.  A missing parameter for a
station falls back to the file's defaults, then to deck.py's constants, so
a partial file never silently zeroes a value.

Added 2026 (continued evolution).  Validated against the same envelopes
qc.py uses for soil so a fat-fingered config fails loudly at load time
rather than producing a confident, wrong yield four hours later.
"""
from __future__ import annotations

import configparser
import os
from dataclasses import dataclass
from typing import Dict, Mapping, Optional, Sequence, Tuple

from . import deck
from .errors import ConfigError
from .results import InputReading, ModelInputSpec

try:  # PyYAML is present on the app host but not a hard dependency here.
    import yaml  # type: ignore
    _HAVE_YAML = True
except Exception:  # pragma: no cover - environment-dependent
    yaml = None  # type: ignore
    _HAVE_YAML = False


# Generous physical envelopes, matching the spirit of qc.QCLimits: the
# point is to catch a decoding or typing error (cm for mm, a percentage
# where a fraction belongs), not to second-guess an agronomist.
AWC_MIN, AWC_MAX = 0.0, 1.0
RDEPTH_MIN_MM, RDEPTH_MAX_MM = 100.0, 5000.0
LAT_MIN, LAT_MAX = -90.0, 90.0


@dataclass(frozen=True)
class SoilParams:
    """One station's soil (and optional latitude) parameters."""
    awc: float
    rooting_depth_mm: float
    latitude: Optional[float] = None

    def validate(self, stnid: str) -> None:
        if not (AWC_MIN < self.awc < AWC_MAX):
            raise ConfigError(
                "awc=%.4f for %s is not a fraction in (%.1f, %.1f)"
                % (self.awc, stnid, AWC_MIN, AWC_MAX))
        if not (RDEPTH_MIN_MM <= self.rooting_depth_mm <= RDEPTH_MAX_MM):
            raise ConfigError(
                "rooting_depth_mm=%.1f for %s outside [%.0f, %.0f] "
                "(looks like cm, not mm?)"
                % (self.rooting_depth_mm, stnid, RDEPTH_MIN_MM,
                   RDEPTH_MAX_MM))
        if self.latitude is not None and not (LAT_MIN <= self.latitude
                                              <= LAT_MAX):
            raise ConfigError(
                "latitude=%.3f for %s outside [%.0f, %.0f]"
                % (self.latitude, stnid, LAT_MIN, LAT_MAX))


@dataclass(frozen=True)
class SoilRegistry:
    """File-driven replacement for deck.py's hard-coded SOIL/LATITUDE.

    Resolution order for any one station is: an explicit per-station entry
    in the file, then the file's ``defaults`` block, then deck.py's
    hard-coded constants.  That last fallback means a registry built from
    a partial file still produces exactly the hard-coded answer for any
    station the file does not mention, so adopting it is safe to do
    incrementally.
    """
    stations: Mapping[str, SoilParams]
    defaults: Optional[SoilParams] = None

    def soil_for(self, stnid: str) -> Tuple[float, float]:
        """(awc, rooting depth mm) for a station, file first."""
        params = self._resolve(stnid)
        if params is not None:
            return params.awc, params.rooting_depth_mm
        return deck.soil_for(stnid)

    def latitude_for(self, stnid: str) -> float:
        """Latitude for a station: file value if given, else deck.py."""
        params = self._resolve(stnid)
        if params is not None and params.latitude is not None:
            return params.latitude
        return deck.latitude_for(stnid)

    def known_stations(self) -> Sequence[str]:
        """Stations the file names explicitly, in file order."""
        return list(self.stations.keys())

    def _resolve(self, stnid: str) -> Optional[SoilParams]:
        key = stnid.upper()
        if key in self.stations:
            return self.stations[key]
        return self.defaults


# ==========================================================================
# Parsing
# ==========================================================================
def _coerce_params(stnid: str, raw: Mapping[str, object]) -> SoilParams:
    """Build (and validate) one SoilParams from a mapping of strings."""
    if "awc" not in raw or "rooting_depth_mm" not in raw:
        raise ConfigError(
            "soil config for %s needs both 'awc' and 'rooting_depth_mm'"
            % stnid)
    try:
        awc = float(raw["awc"])
        rdepth = float(raw["rooting_depth_mm"])
        lat_raw = raw.get("latitude")
        lat = float(lat_raw) if lat_raw is not None and lat_raw != "" \
            else None
    except (TypeError, ValueError) as exc:
        raise ConfigError("soil config for %s has a non-numeric value: %s"
                          % (stnid, exc))
    params = SoilParams(awc=awc, rooting_depth_mm=rdepth, latitude=lat)
    params.validate(stnid)
    return params


def _registry_from_mapping(data: Mapping[str, object]) -> SoilRegistry:
    """Build a registry from an already-parsed mapping (YAML shape)."""
    stations_raw = data.get("stations")
    if not isinstance(stations_raw, Mapping):
        raise ConfigError("soil config needs a 'stations' mapping")
    stations: Dict[str, SoilParams] = {}
    for stnid, raw in stations_raw.items():
        if not isinstance(raw, Mapping):
            raise ConfigError("soil config entry for %s is not a mapping"
                              % stnid)
        stations[str(stnid).upper()] = _coerce_params(str(stnid), raw)

    defaults = None
    defaults_raw = data.get("defaults")
    if isinstance(defaults_raw, Mapping):
        defaults = _coerce_params("defaults", defaults_raw)
    elif defaults_raw is not None:
        raise ConfigError("soil config 'defaults' must be a mapping")

    return SoilRegistry(stations=stations, defaults=defaults)


def load_yaml(text: str) -> SoilRegistry:
    """Parse a YAML soil config string into a registry."""
    if not _HAVE_YAML:
        raise ConfigError(
            "PyYAML is not available; use an INI soil config instead")
    try:
        data = yaml.safe_load(text)
    except Exception as exc:  # pragma: no cover - yaml's own error types
        raise ConfigError("could not parse YAML soil config: %s" % exc)
    if not isinstance(data, Mapping):
        raise ConfigError("YAML soil config must be a mapping at the top")
    return _registry_from_mapping(data)


def load_ini(text: str) -> SoilRegistry:
    """Parse an INI soil config string into a registry.

    One ``[STATION]`` section per station, plus an optional ``[defaults]``
    section, each with ``awc`` / ``rooting_depth_mm`` / optional
    ``latitude`` keys.
    """
    parser = configparser.ConfigParser()
    try:
        parser.read_string(text)
    except configparser.Error as exc:
        raise ConfigError("could not parse INI soil config: %s" % exc)

    stations: Dict[str, SoilParams] = {}
    defaults = None
    for section in parser.sections():
        raw = dict(parser.items(section))
        if section.lower() == "defaults":
            defaults = _coerce_params("defaults", raw)
        else:
            stations[section.upper()] = _coerce_params(section, raw)
    if not stations and defaults is None:
        raise ConfigError("INI soil config has no station sections")
    return SoilRegistry(stations=stations, defaults=defaults)


def load_file(path: str) -> SoilRegistry:
    """Load a soil config from a file, dispatching on its extension.

    ``.yaml`` / ``.yml`` go through the YAML reader; ``.ini`` / ``.cfg``
    through the INI reader.  Anything else is tried as YAML when PyYAML is
    present, otherwise as INI.
    """
    if not os.path.exists(path):
        raise ConfigError("soil config file not found: %s" % path)
    with open(path, "r") as fh:
        text = fh.read()

    ext = os.path.splitext(path)[1].lower()
    if ext in (".yaml", ".yml"):
        return load_yaml(text)
    if ext in (".ini", ".cfg", ".conf"):
        return load_ini(text)
    # Unknown extension: prefer YAML when we can, fall back to INI.
    if _HAVE_YAML:
        return load_yaml(text)
    return load_ini(text)


# ==========================================================================
# Spec assembly using a registry (parallel to deck.spec_from_readings)
# ==========================================================================
def spec_from_readings_with(registry: SoilRegistry, stnid: str, year: int,
                            readings: Sequence) -> ModelInputSpec:
    """Assemble a ModelInputSpec using file-driven soil parameters.

    The analogue of ``deck.spec_from_readings`` but with the soil and
    latitude taken from ``registry`` (which itself falls back to deck.py's
    constants for anything the file omits).  Returns the same
    ModelInputSpec the hard-coded path produces, so the deck writer, QC and
    the rest of Nightshift are entirely unaware which source was used.
    """
    awc, rdepth = registry.soil_for(stnid)
    lat = registry.latitude_for(stnid)
    projected = [
        InputReading(stnid=stnid, year=year, doy=r.doy, tmax=r.tmax,
                     tmin=r.tmin, rain=r.rain, srad=r.srad)
        for r in readings
    ]
    return ModelInputSpec(stnid=stnid, year=year, latitude=lat, awc=awc,
                          rooting_depth_mm=rdepth, readings=projected)


def registry_from_deck_defaults() -> SoilRegistry:
    """Build a registry that reproduces deck.py's hard-coded values.

    Useful as a starting point for writing a config file, and as the
    identity case in tests: a spec built through this registry is
    byte-for-byte the spec deck.spec_from_readings produces.
    """
    stations: Dict[str, SoilParams] = {}
    for stnid, (awc, rdepth) in deck.SOIL.items():
        lat = deck.LATITUDE.get(stnid)
        stations[stnid] = SoilParams(awc=awc, rooting_depth_mm=rdepth,
                                     latitude=lat)
    default_awc, default_rdepth = deck.DEFAULT_SOIL
    defaults = SoilParams(awc=default_awc, rooting_depth_mm=default_rdepth,
                          latitude=deck.DEFAULT_LAT)
    return SoilRegistry(stations=stations, defaults=defaults)
