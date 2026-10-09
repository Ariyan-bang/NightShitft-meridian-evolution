# Meridian

Provincial agri-environmental monitoring and yield forecasting platform.

## Architecture

Meridian is a three-tier application:

1. **Collector** (`ingest/`) receives telemetry from the field station
   network and writes it to the reading store.
2. **Application server** (`services/`) is a Spring Boot application
   exposing the REST API and the scheduled batch jobs.
3. **Web client** (`dashboard/`) is the operator console.

The reading store is a PostgreSQL instance on `db01.meridian.internal`.

## Building

    ./gradlew build

Requires JDK 8 and PostgreSQL 9.4 client libraries.

## Running the nightly batch

The batch is scheduled by the application server's Quartz configuration.
See `services/src/main/resources/quartz.properties`.

## Contacts

- Platform: D. Ferreira (dferreira@)
- Application: A. Okonkwo (aokonkwo@)
- Agronomy model: R. Halvorsen (rhalvorsen@)

---
*Last updated 2015-11-04.*

## Continued evolution (2026)

The system has kept moving since the archaeology snapshot. Recent, still-settling work:

- model: an optional soil-nitrogen balance (run switch `MERIDIAN_NBAL`), plus a self-contained
  mineralisation kernel put forward as the port target for MRD-231, with a trace hook
  (`MERIDIAN_TRACE`) meant to seed a validation fixture. Off by default.
- ingest: a second telemetry frame format, "MRD2" (two extra channels), alongside MRD1, and a
  `mrd_framedump` debug tool. The field spool is still MRD1.
- analytics: an opt-in `--parallel` orchestrator and an external soil-parameter config loader,
  neither on the nightly path yet.
- services: a versioned `/api/v2` surface (pagination, export, a station summary cache) routed by a
  newer annotation dispatcher beside the original Router.
- reporting: a `trend` report and a JSON export, plus a centralised run-selection module.
- ui-next: Anomalies and Compare screens landed (5 of 11), with a forecast client of their own.

Not everything here is finished, consistent, or correct. Treat the docs as a starting point and
confirm behaviour against the running system.
