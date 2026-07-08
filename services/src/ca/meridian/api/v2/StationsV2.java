package ca.meridian.api.v2;

import ca.meridian.db.DbClient;
import ca.meridian.db.StationCache;
import ca.meridian.model.Station;
import ca.meridian.util.TinyJson;

import java.io.IOException;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * GET /api/v2/stations
 *
 * The versioned station list. The original /api/stations returns the
 * record counts straight from the GROUP BY; this folds in the standing
 * metadata the network has always had on paper but never in the store
 * (the site's full name, its approximate latitude, and the region it
 * reports under) so the v2 portal can label the map without a second
 * lookup. The coverage figures still come through {@link StationCache},
 * so this adds no load the station endpoint did not already carry.
 *
 * The catalogue is static because the six sites have not changed since
 * before the service existed; a seventh would be a schema conversation,
 * not a config edit.
 *
 * R. Osei 2026
 */
public final class StationsV2 {

    /** Standing site metadata, keyed by the truncated station id. */
    private static final Map<String, String[]> CATALOGUE = new LinkedHashMap<>();
    static {
        // id -> { display name, latitude, region }
        CATALOGUE.put("GUELPH",   new String[] { "Guelph",      "43.53", "Wellington" });
        CATALOGUE.put("KITCHNER", new String[] { "Kitchener",   "43.45", "Waterloo" });
        CATALOGUE.put("WATERLOO", new String[] { "Waterloo",    "43.47", "Waterloo" });
        CATALOGUE.put("CAMBRIDG", new String[] { "Cambridge",   "43.36", "Waterloo" });
        CATALOGUE.put("MILTON",   new String[] { "Milton",      "43.52", "Halton" });
        CATALOGUE.put("BRANTFRD", new String[] { "Brantford",   "43.14", "Brant" });
    }

    private final StationCache stations;

    public StationsV2(DbClient db) {
        this.stations = new StationCache(db);
    }

    @Endpoint(path = "/api/v2/stations", summary = "stations with coverage and site metadata")
    public V2Response stations(V2Request req) throws IOException {
        List<Station> list = stations.stations();
        List<Object> out = new ArrayList<>(list.size());
        for (Station s : list) {
            Map<String, Object> m = new LinkedHashMap<>();
            m.put("id", s.id);
            m.put("days", s.days);
            m.put("first_year", s.firstYear);
            m.put("last_year", s.lastYear);
            m.put("years", s.years());

            String[] meta = CATALOGUE.get(s.id);
            if (meta != null) {
                m.put("display_name", meta[0]);
                m.put("latitude", Double.parseDouble(meta[1]));
                m.put("region", meta[2]);
            } else {
                // A site in the store with no catalogue entry still lists,
                // just without the paper metadata, rather than vanishing.
                m.put("display_name", s.id);
                m.put("latitude", null);
                m.put("region", null);
            }
            out.add(m);
        }

        Map<String, Object> body = new LinkedHashMap<>();
        body.put("count", out.size());
        body.put("stations", out);
        return V2Response.json(TinyJson.write(body));
    }
}
