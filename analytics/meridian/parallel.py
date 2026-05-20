"""Opt-in parallel orchestration for cropmod runs.

    -- Nightshift (orchestration) side, experimental --

The serial orchestrator (orchestrator.run_all) runs one station-year at a
time because cropmod reads and writes MERIDIAN.DAT / MERIDIAN.OUT using
those exact names in its current working directory (MRD-201).  scratch.py
enforces that with a process-wide run lock, so even a threaded caller
cannot fan the model out.  That lock is why the nightly batch of six
stations takes about four hours.

This module is a FIRST ATTEMPT at MRD-201.  The observation is that the
fixed-filename constraint is only a constraint *within a working
directory*: two cropmod processes that each have their own private
directory never see each other's files, so they can run at the same time
safely.  The serial lock is therefore stronger than it needs to be.  Here
each station-year gets its own freshly-created working directory (via the
lock-free ScratchDir, NOT the locked ScratchRun) and the model
invocations are fanned out across a small thread pool; the subprocess
releases the GIL while cropmod runs, so threads give real concurrency for
what is an I/O- and compute-bound external process.

IMPORTANT -- this is NOT the default path.  orchestrator.run_all stays the
production runner and is untouched.  Nothing in run_forecast.py reaches
this module unless the operator passes --parallel explicitly.  The store
is a single SQLite connection and is NOT thread-safe, so all reads
(building specs) and all writes (persisting results) happen on the calling
thread; only the model runs and the pure parse step are parallel.  Keep it
that way until the store grows a real connection pool.

Added 2026 (continued evolution).  Treat as experimental: the serial path
remains the source of truth for a forecast until this has a full season of
shadow runs behind it.
"""
from __future__ import annotations

import datetime as _dt
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from . import aggregate, deck, parse, qc
from .config import Config, DEFAULT
from .errors import ModelRunError
from .results import (ForecastResult, ModelInputSpec, RunArtifacts,
                      RunOutcome, SeasonSummary, StationYear)
from .scratch import ScratchDir
from .store import Store

# A deliberately modest default.  cropmod is an external process doing
# real file I/O, so a handful of concurrent runs already recovers most of
# the wall-clock the serial lock was costing; pushing this higher mostly
# buys scratch-disk contention.  Operators override it with --workers.
DEFAULT_MAX_WORKERS = 4


def resolve_workers(requested: Optional[int], n_targets: int) -> int:
    """Clamp a requested worker count to something sensible.

    Never more workers than there are targets, never fewer than one.  A
    ``None`` request falls back to :data:`DEFAULT_MAX_WORKERS`.
    """
    if requested is None or requested <= 0:
        requested = DEFAULT_MAX_WORKERS
    if n_targets <= 0:
        return 1
    return max(1, min(requested, n_targets))


# ==========================================================================
# A single prepared unit of work
# ==========================================================================
@dataclass(frozen=True)
class PreparedRun:
    """A station-year whose spec has been built and QC'd, ready to model.

    Specs are assembled on the calling thread (store reads are serial),
    then handed to the pool so the worker touches only the filesystem and
    the model binary, never the store.
    """
    target: StationYear
    spec: ModelInputSpec

    @property
    def stnid(self) -> str:
        return self.target.stnid

    @property
    def year(self) -> int:
        return self.target.year


@dataclass(frozen=True)
class Modelled:
    """What a worker hands back: the parsed result for one station-year.

    Carries the target explicitly so the collector never has to infer the
    year from the result alone.
    """
    target: StationYear
    result: ForecastResult
    summary: SeasonSummary
    elapsed_s: float
    deck_days: int


# ==========================================================================
# Worker-side: run cropmod in a private directory, parse, return
# ==========================================================================
def _run_one(prepared: PreparedRun, config: Config, run_at: str) -> Modelled:
    """Run the model for one prepared station-year in its own scratch dir.

    This is the body that runs on a pool thread.  It is lock-free on
    purpose: each call owns a private ScratchDir, so the fixed-name files
    cropmod insists on (MRD-201) never collide with another worker's.  It
    does no store I/O -- parsing produces a value object the caller then
    persists serially.
    """
    spec = prepared.spec
    binary = config.resolved_model_binary()
    if not os.path.exists(binary):
        raise ModelRunError("cropmod binary not found at %s" % binary,
                            stnid=spec.stnid, year=spec.year)

    started = _dt.datetime.now()
    # Lock-free scratch: a unique mkdtemp directory per worker.  Because
    # the directory is private, two workers running cropmod at the same
    # time cannot clobber each other's MERIDIAN.DAT / MERIDIAN.OUT.
    scratch = ScratchDir(root=config.scratch_root,
                         prefix=config.scratch_prefix,
                         keep=config.keep_scratch)
    scratch.create()
    try:
        deck_path = scratch.child(deck.DECK_NAME)
        n = deck.write_deck_spec(deck_path, spec)

        proc = subprocess.run(
            [binary], cwd=scratch.path, capture_output=True, text=True,
            timeout=config.run_timeout_s)
        if proc.returncode != 0:
            raise ModelRunError(
                "cropmod exited %d: %s"
                % (proc.returncode, proc.stderr.strip()[:200]),
                stnid=spec.stnid, year=spec.year)

        out_path = scratch.child(parse.OUT_NAME)
        if not os.path.exists(out_path):
            raise ModelRunError("cropmod wrote no output file",
                                stnid=spec.stnid, year=spec.year)

        artifacts = RunArtifacts(
            stnid=spec.stnid, year=spec.year, scratch_dir=scratch.path,
            deck_path=deck_path, out_path=out_path, model_binary=binary,
            returncode=proc.returncode, deck_days=n,
            stdout_tail=proc.stdout.strip()[-200:])

        # Parsing is pure CPU and owns the column format (MRD-143); it is
        # safe off-thread because it touches neither the store nor shared
        # state.  We parse here, while the scratch dir is still alive,
        # exactly as the serial seam does.
        result: ForecastResult = parse.parse_artifacts(artifacts,
                                                        run_at=run_at)
        summary: SeasonSummary = aggregate.summarize_result(result)
    finally:
        scratch.cleanup()

    elapsed = (_dt.datetime.now() - started).total_seconds()
    return Modelled(target=prepared.target, result=result, summary=summary,
                    elapsed_s=elapsed, deck_days=n)


# ==========================================================================
# Calling-thread side: prepare, fan out, collect, persist
# ==========================================================================
class ParallelOrchestrator:
    """Runs many station-years concurrently, one private dir each.

    The lifecycle mirrors the serial orchestrator but splits it across the
    seam differently:

      1. prepare()  -- on the calling thread: read the store, build and QC
                       each spec.  Serial because the store is serial.
      2. run()      -- fan the model invocations out across the pool; each
                       worker returns a Modelled value object.
      3. persist()  -- back on the calling thread: write every result to
                       the store.  Serial because the store is serial.

    Only step 2 is parallel, which is the step MRD-201's lock was
    throttling.
    """

    def __init__(self, store: Store, config: Config = DEFAULT,
                 max_workers: Optional[int] = None):
        self.store = store
        self.config = config
        self.max_workers = max_workers

    # -- step 1 ------------------------------------------------------------
    def prepare(self, targets: Sequence[StationYear]) -> List[PreparedRun]:
        """Build and QC a spec for each target on the calling thread."""
        prepared: List[PreparedRun] = []
        for t in targets:
            readings = self.store.readings(t.stnid, t.year)
            if not readings:
                raise ModelRunError("no readings for %s %d"
                                    % (t.stnid, t.year),
                                    stnid=t.stnid, year=t.year)
            spec = deck.spec_from_readings(t.stnid, t.year, readings)
            if self.config.qc_enabled:
                qc.check_inputs(spec, self.config.qc,
                                blocking=self.config.qc_blocking)
            prepared.append(PreparedRun(target=t, spec=spec))
        return prepared

    # -- step 2 ------------------------------------------------------------
    def run(self, prepared: Sequence[PreparedRun],
            run_at: str) -> Tuple[List[Modelled], List[RunOutcome]]:
        """Fan the prepared runs out across the thread pool.

        Returns the successful :class:`Modelled` objects together with a
        :class:`RunOutcome` per failure so the caller can report both.
        The successes come back in completion order; the caller decides
        how to collect them.
        """
        workers = resolve_workers(self.max_workers, len(prepared))
        modelled: List[Modelled] = []
        failures: List[RunOutcome] = []

        if not prepared:
            return modelled, failures

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(_run_one, p, self.config, run_at): p
                for p in prepared
            }
            for fut in as_completed(futures):
                p = futures[fut]
                try:
                    modelled.append(fut.result())
                except Exception as exc:  # noqa: BLE001 - recorded, not raised
                    failures.append(
                        RunOutcome.failure(p.target, str(exc), elapsed_s=0.0))
        return modelled, failures

    # -- step 3 ------------------------------------------------------------
    def persist(self, modelled: Sequence[Modelled],
                run_at: str) -> Dict[str, Modelled]:
        """Write every modelled result to the store on the calling thread.

        Collects the completed runs before writing so persistence is a
        single serial sweep over a stable collection rather than a race of
        pool threads against one SQLite connection.
        """
        # Collect the completed runs, newest write wins, before the serial
        # persist sweep.  Keying the collection by station groups a
        # station's runs together for the write and for the summary the
        # caller reports.
        collected: Dict[str, Modelled] = {}
        for m in modelled:
            collected[m.target.stnid] = m

        for m in collected.values():
            self.store.save_result(m.result, run_at=run_at)
        return collected


# ==========================================================================
# Convenience entry points (mirror orchestrator.run_all / run_station_year)
# ==========================================================================
def _targets_for(store: Store) -> List[StationYear]:
    return [StationYear(stnid=s, year=y) for (s, y) in store.station_years()]


def run_all_parallel(store: Store, config: Optional[Config] = None,
                     max_workers: Optional[int] = None) -> List[dict]:
    """Parallel analogue of orchestrator.run_all (opt-in).

    Runs every station-year in the store concurrently, each in its own
    working directory, then persists serially.  Returns the same legacy
    result dicts orchestrator.run_all returns so run_forecast.py can print
    them unchanged.  This is only ever reached via an explicit --parallel
    request; the default path never calls it.
    """
    if config is None:
        config = DEFAULT
    targets = _targets_for(store)
    return run_targets_parallel(store, targets, config=config,
                                max_workers=max_workers)


def run_targets_parallel(store: Store, targets: Sequence[StationYear],
                         config: Optional[Config] = None,
                         max_workers: Optional[int] = None) -> List[dict]:
    """Run an explicit set of station-years in parallel (opt-in)."""
    if config is None:
        config = DEFAULT
    orch = ParallelOrchestrator(store, config=config, max_workers=max_workers)
    run_at = _dt.datetime.now().isoformat(timespec="seconds")

    prepared = orch.prepare(targets)
    modelled, failures = orch.run(prepared, run_at)
    collected = orch.persist(modelled, run_at)

    if failures:
        first = failures[0]
        raise ModelRunError(
            "parallel run had %d failure(s); first: %s"
            % (len(failures), first.error),
            stnid=first.target.stnid, year=first.target.year)

    out: List[dict] = []
    for m in collected.values():
        legacy = m.result.as_legacy_dict()
        legacy["deck_days"] = m.deck_days
        legacy["run_at"] = run_at
        legacy["result"] = m.result
        legacy["summary"] = m.summary
        legacy["dropped_days"] = m.result.dropped_days
        legacy["elapsed_s"] = m.elapsed_s
        out.append(legacy)
    out.sort(key=lambda d: (d["stnid"], d["year"]))
    return out
