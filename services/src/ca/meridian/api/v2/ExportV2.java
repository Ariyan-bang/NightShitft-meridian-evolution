package ca.meridian.api.v2;

import ca.meridian.db.DbClient;
import ca.meridian.db.QueryBuilder;
import ca.meridian.db.ResultSetLite;
import ca.meridian.db.Row;
import ca.meridian.util.Clock;
import ca.meridian.util.Csv;
import ca.meridian.util.Strings;
import ca.meridian.util.TinyJson;
import ca.meridian.util.Validate;

import java.io.IOException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Map;

/**
 * GET /api/v2/export?fmt=csv|json
 *
 * The versioned export. The 2019 /api/export only ever emitted CSV; the
 * v2 portal wanted the same rows as JSON for its in-page preview before
 * the user commits to a download, so this takes an &fmt and serves
 * either. The table selection and the validated station/year filters
 * follow the older handler so a caller does not have to learn two sets
 * of rules, but the response is built through the v2 dispatch rather
 * than writing to the exchange by hand.
 *
 * R. Osei 2026
 */
public final class ExportV2 {

    private final DbClient db;

    public ExportV2(DbClient db) {
        this.db = db;
    }

    @Endpoint(path = "/api/v2/export", summary = "CSV or JSON export of a table (fmt)")
    public V2Response export(V2Request req) throws IOException {
        String fmt = Strings.orEmpty(req.param("fmt")).toLowerCase();
        if (fmt.isEmpty()) {
            fmt = "csv";
        }
        if (!fmt.equals("csv") && !fmt.equals("json")) {
            return V2Response.error(400, "unknown fmt: " + fmt);
        }

        String table = Strings.orEmpty(req.param("table")).toLowerCase();
        if (table.isEmpty()) {
            table = "forecast";
        }

        String station = null;
        String stationRaw = req.param("station");
        if (Strings.notBlank(stationRaw)) {
            station = Validate.requireStation(stationRaw);
        }
        Integer year = Validate.optionalYear(req.param("year"));

        List<String> columns;
        QueryBuilder qb;
        switch (table) {
            case "forecast":
                columns = Arrays.asList("stnid", "year", "yield_t", "ndays", "model", "run_at");
                qb = QueryBuilder.select(columns.toArray(new String[0])).from("forecast");
                if (station != null) {
                    qb.whereEq("stnid", station);
                }
                if (year != null) {
                    qb.whereEq("year", year);
                }
                qb.orderBy("stnid", "year");
                break;
            case "readings":
                if (station == null) {
                    return V2Response.error(400, "station is required for a readings export");
                }
                columns = Arrays.asList("stnid", "year", "doy", "tmax", "tmin",
                        "rain", "srad", "rh", "wind", "flags");
                qb = QueryBuilder.select(columns.toArray(new String[0])).from("reading")
                        .whereEq("stnid", station);
                if (year != null) {
                    qb.whereEq("year", year);
                }
                qb.orderBy("year", "doy");
                break;
            case "series":
                if (station == null || year == null) {
                    return V2Response.error(400, "station and year are required for a series export");
                }
                columns = Arrays.asList("doy", "sw", "et", "drain", "biom", "lai");
                qb = QueryBuilder.select(columns.toArray(new String[0]))
                        .from("forecast_daily")
                        .whereEq("stnid", station)
                        .whereEq("year", year)
                        .orderBy("doy");
                break;
            default:
                return V2Response.error(400, "unknown table: " + table);
        }

        ResultSetLite rs = db.query(qb);
        List<Map<String, Object>> rows = new ArrayList<>(rs.size());
        for (Row r : rs) {
            rows.add(r.asMap());
        }

        if (fmt.equals("json")) {
            StringBuilder sb = new StringBuilder();
            sb.append("{\"table\":\"").append(table).append("\"");
            sb.append(",\"count\":").append(rows.size());
            sb.append(",\"columns\":").append(TinyJson.write(columns));
            sb.append(",\"rows\":[");
            for (int i = 0; i < rows.size(); i++) {
                if (i > 0) {
                    sb.append(',');
                }
                sb.append(TinyJson.write(ordered(columns, rows.get(i))));
            }
            sb.append("]}");
            return V2Response.json(sb.toString());
        }

        String csv = Csv.fromRows(columns, rows);
        String fname = "meridian_" + table
                + (station == null ? "" : "_" + station)
                + (year == null ? "" : "_" + year)
                + "_" + Clock.stampDay() + ".csv";
        return V2Response.csv(fname, csv);
    }

    // Projects a row map onto the declared column order so the JSON keys
    // come out in the same order as the CSV header.
    private static Map<String, Object> ordered(List<String> columns, Map<String, Object> row) {
        Map<String, Object> m = new java.util.LinkedHashMap<>();
        for (String c : columns) {
            m.put(c, row.get(c));
        }
        return m;
    }
}
