package ca.meridian.admin;

import ca.meridian.db.Db;
import ca.meridian.db.DbClient;
import ca.meridian.db.ForecastCache;
import ca.meridian.db.QueryBuilder;
import ca.meridian.db.ResultSetLite;
import ca.meridian.db.Row;
import ca.meridian.db.StationCache;
import ca.meridian.model.Station;
import ca.meridian.util.Env;
import ca.meridian.util.Strings;

import java.io.IOException;
import java.util.List;

/**
 * A small offline admin tool, run against the same database the
 * service reads. It grew out of the shell one-liners the on-call rota
 * kept re-typing: "how many rows has GUELPH got", "which station is
 * missing this year". Bundled into the service jar rather than kept as
 * loose scripts so it could not drift from the schema the handlers
 * assume.
 *
 *   java -Dmeridian.db=data/meridian.db ca.meridian.admin.AdminCli stations
 *   java -Dmeridian.db=data/meridian.db ca.meridian.admin.AdminCli coverage GUELPH
 *   java -Dmeridian.db=data/meridian.db ca.meridian.admin.AdminCli suspect GUELPH 2025
 *   java -Dmeridian.db=data/meridian.db ca.meridian.admin.AdminCli evict GUELPH 2025
 *
 * D. Iqbal 2021, extended R. Osei 2026
 */
public final class AdminCli {

    private final DbClient db;

    public AdminCli(DbClient db) {
        this.db = db;
    }

    public static void main(String[] args) throws Exception {
        String dbPath = Env.db();
        DbClient db = new DbClient(new Db(dbPath));
        AdminCli cli = new AdminCli(db);

        String cmd = args.length > 0 ? args[0] : "help";
        switch (cmd) {
            case "stations":
                cli.stations();
                break;
            case "coverage":
                if (args.length < 2) {
                    System.err.println("usage: coverage <station>");
                    System.exit(2);
                }
                cli.coverage(Strings.normStation(args[1]));
                break;
            case "suspect":
                if (args.length < 3) {
                    System.err.println("usage: suspect <station> <year>");
                    System.exit(2);
                }
                cli.suspect(Strings.normStation(args[1]), Integer.parseInt(args[2]));
                break;
            case "evict":
                if (args.length < 3) {
                    System.err.println("usage: evict <station> <year>");
                    System.exit(2);
                }
                cli.evict(Strings.normStation(args[1]), Integer.parseInt(args[2]));
                break;
            case "help":
            default:
                usage();
        }
    }

    private static void usage() {
        System.out.println("meridian admin");
        System.out.println("  stations            list stations and record counts");
        System.out.println("  coverage <stn>      per-year day counts for a station");
        System.out.println("  suspect <stn> <yr>  count flagged readings");
        System.out.println("  evict <stn> <yr>    drop the v2 cached summary after a backfill");
    }

    void stations() throws IOException {
        StationCache cache = new StationCache(db);
        List<Station> list = cache.stations();
        System.out.println(Strings.padRight("STATION", 10)
                + Strings.padRight("DAYS", 10) + "YEARS");
        for (Station s : list) {
            System.out.println(Strings.padRight(s.id, 10)
                    + Strings.padRight(String.valueOf(s.days), 10)
                    + s.firstYear + "-" + s.lastYear
                    + " (" + s.years() + ")");
        }
    }

    void coverage(String station) throws IOException {
        String sql = QueryBuilder.select("year", "COUNT(*) AS days")
                .from("reading")
                .whereEq("stnid", station)
                .groupBy("year")
                .orderBy("year")
                .build();
        ResultSetLite rs = db.query(sql);
        if (rs.isEmpty()) {
            System.out.println("no readings for " + station);
            return;
        }
        for (Row r : rs) {
            int days = r.intVal("days");
            System.out.println(r.intVal("year") + "  "
                    + Strings.padRight(String.valueOf(days), 5)
                    + bar(days));
        }
    }

    void suspect(String station, int year) throws IOException {
        String sql = QueryBuilder.select("COUNT(*) AS n")
                .from("reading")
                .whereEq("stnid", station)
                .whereEq("year", year)
                .whereRaw("flags <> 0")
                .build();
        ResultSetLite rs = db.query(sql);
        int n = rs.isEmpty() ? 0 : rs.first().intVal("n");
        System.out.println(station + " " + year + ": " + n + " flagged reading(s)");
    }

    /**
     * Drops the v2 forecast-summary cache entry for a station after a
     * manual backfill has written a new run for that year, so the v2
     * endpoint reflects it without waiting out the TTL.
     */
    void evict(String station, int year) throws IOException {
        ForecastCache cache = new ForecastCache(db);
        // Warm the entry first so there is something to drop, mirroring
        // what the running service would hold after a read.
        cache.summary(station);
        cache.invalidate(station, year);
        System.out.println("evicted v2 summary for " + station + " " + year
                + " (entries now " + cache.size() + ")");
    }

    /** A crude sparkline; 366 days maps to roughly one bar per week. */
    private static String bar(int days) {
        int len = Math.min(52, (days + 6) / 7);
        return Strings.repeat("#", len);
    }
}
