package ca.meridian.util;

/**
 * Runtime configuration.
 *
 * All of Meridian's configuration has always come from -D system
 * properties. There was an attempt in 2016 to move to a properties
 * file loaded from the classpath but the deployment scripts on the
 * old collector host wrote the -D flags directly into the init
 * script, so the file was never wired up and this stayed the way in.
 *
 * A. Okonkwo, 2014-09
 */
public final class Env {

    /** Property holding the listen port. */
    public static final String PORT = "meridian.port";

    /** Property holding the path to the sqlite database file. */
    public static final String DB = "meridian.db";

    /** Property toggling per-request logging. Off by default. */
    public static final String LOG = "meridian.log";

    /** Property holding the sqlite3 shell-out retry count. */
    public static final String RETRIES = "meridian.db.retries";

    /** Property holding the station cache TTL in seconds. */
    public static final String CACHE_TTL = "meridian.cache.ttl";

    /** Property holding the v2 forecast-summary cache TTL in seconds. */
    public static final String V2_CACHE_TTL = "meridian.v2.cache.ttl";

    private Env() {
    }

    public static int port() {
        return intProp(PORT, 8081);
    }

    public static String db() {
        return System.getProperty(DB, "data/meridian.db");
    }

    public static boolean logEnabled() {
        return boolProp(LOG, false);
    }

    public static int retries() {
        return intProp(RETRIES, 2);
    }

    public static int cacheTtlSeconds() {
        return intProp(CACHE_TTL, 60);
    }

    public static int v2CacheTtlSeconds() {
        return intProp(V2_CACHE_TTL, 300);
    }

    public static String prop(String key, String dflt) {
        String v = System.getProperty(key);
        return v == null ? dflt : v;
    }

    public static int intProp(String key, int dflt) {
        String v = System.getProperty(key);
        if (v == null || v.isEmpty()) {
            return dflt;
        }
        try {
            return Integer.parseInt(v.trim());
        } catch (NumberFormatException nfe) {
            // Bad value in the init script. Fall back rather than fail
            // to start; the old host had no way to see a stack trace.
            return dflt;
        }
    }

    public static boolean boolProp(String key, boolean dflt) {
        String v = System.getProperty(key);
        if (v == null) {
            return dflt;
        }
        v = v.trim().toLowerCase();
        return v.equals("1") || v.equals("true") || v.equals("yes") || v.equals("on");
    }
}
