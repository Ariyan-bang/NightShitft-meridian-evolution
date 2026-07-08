package ca.meridian.api.v2;

import ca.meridian.db.DbClient;
import ca.meridian.db.ForecastCache;
import ca.meridian.db.QueryBuilder;
import ca.meridian.db.ResultSetLite;
import ca.meridian.db.Row;
import ca.meridian.util.Numbers;
import ca.meridian.util.Strings;
import ca.meridian.util.TinyJson;
import ca.meridian.util.Validate;

import java.io.IOException;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * GET /api/v2/forecast
 *
 * The versioned forecast view. Where the original /api/forecast streams
 * the whole table (or one station's rows) in a single array, this pages
 * the rows with &page and &size and wraps them in an envelope that also
 * carries paging counts and, when a station is given, a small summary
 * block. The envelope is what the v2 portal's table component expects:
 * it renders the summary header from one call and the body rows from
 * the same payload.
 *
 * The rows are read live on every call. The summary (run count, latest
 * run, mean yield) is aggregated over the station's whole history and
 * is served through {@link ForecastCache}, because the component asks
 * for it again on every page change.
 *
 * R. Osei 2026
 */
public final class ForecastV2 {

    private static final int DEFAULT_SIZE = 20;
    private static final int MAX_SIZE = 200;

    private final DbClient db;
    private final ForecastCache cache;

    public ForecastV2(DbClient db, ForecastCache cache) {
        this.db = db;
        this.cache = cache;
    }

    @Endpoint(path = "/api/v2/forecast", summary = "paginated forecasts with a cached station summary")
    public V2Response forecast(V2Request req) throws IOException {
        String station = null;
        String stationRaw = req.param("station");
        if (Strings.notBlank(stationRaw)) {
            station = Validate.requireStation(stationRaw);
        }

        int page = req.intParam("page", 1, 1, 1_000_000);
        int size = req.intParam("size", DEFAULT_SIZE, 1, MAX_SIZE);

        QueryBuilder qb = QueryBuilder.select(
                        "stnid", "year", "yield_t", "ndays", "model", "run_at")
                .from("forecast");
        if (station != null) {
            qb.whereEq("stnid", station);
        }
        qb.orderBy("stnid", "year");

        ResultSetLite rs = db.query(qb);
        List<Row> all = rs.rows();
        int total = all.size();
        int pages = total == 0 ? 0 : (total + size - 1) / size;

        int from = (page - 1) * size;
        int to = Math.min(from + size, total);
        List<Map<String, Object>> pageRows = new ArrayList<>();
        for (int i = from; i < to; i++) {
            pageRows.add(rowOf(all.get(i)));
        }

        StringBuilder sb = new StringBuilder();
        sb.append('{');
        sb.append("\"station\":").append(station == null ? "null" : quoted(station));
        sb.append(",\"page\":").append(page);
        sb.append(",\"size\":").append(size);
        sb.append(",\"total\":").append(total);
        sb.append(",\"pages\":").append(pages);
        sb.append(",\"summary\":").append(station == null ? "null" : summaryJson(station));
        sb.append(",\"rows\":").append(rowsJson(pageRows));
        sb.append('}');
        return V2Response.json(sb.toString());
    }

    private String summaryJson(String station) throws IOException {
        ForecastCache.Summary s = cache.summary(station);
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("station", s.station);
        m.put("runs", s.runs);
        m.put("latest_run", s.latestRun);
        m.put("mean_yield", Numbers.round3(s.meanYield));
        m.put("last_year", s.lastYear);
        return TinyJson.write(m);
    }

    private static Map<String, Object> rowOf(Row r) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("stnid", r.str("stnid"));
        m.put("year", r.intVal("year"));
        m.put("yield_t", r.dbl("yield_t"));
        m.put("ndays", r.intVal("ndays"));
        m.put("model", r.str("model"));
        m.put("run_at", r.str("run_at"));
        return m;
    }

    private static String rowsJson(List<Map<String, Object>> rows) {
        StringBuilder sb = new StringBuilder();
        sb.append('[');
        for (int i = 0; i < rows.size(); i++) {
            if (i > 0) {
                sb.append(',');
            }
            sb.append(TinyJson.write(rows.get(i)));
        }
        sb.append(']');
        return sb.toString();
    }

    private static String quoted(String s) {
        return "\"" + TinyJson.escape(s) + "\"";
    }
}
