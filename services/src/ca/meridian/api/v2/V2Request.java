package ca.meridian.api.v2;

import ca.meridian.api.Http;
import ca.meridian.util.Strings;
import ca.meridian.util.Validate;
import com.sun.net.httpserver.HttpExchange;

import java.util.Map;

/**
 * The request side of the v2 dispatch. Wraps the JDK exchange and the
 * parsed query string so the annotated handlers do not each re-reach
 * into {@link HttpExchange}. The parsing is deliberately the same
 * {@link Http} helper the 2021 endpoints use, so the two families agree
 * on param names and percent-decoding; only the plumbing around it is
 * new.
 *
 * R. Osei 2026
 */
public final class V2Request {

    private final HttpExchange exchange;
    private final Map<String, String> query;

    V2Request(HttpExchange exchange) {
        this.exchange = exchange;
        this.query = Http.query(exchange);
    }

    public HttpExchange exchange() {
        return exchange;
    }

    public String path() {
        return exchange.getRequestURI().getPath();
    }

    public String verb() {
        return exchange.getRequestMethod();
    }

    /** A trimmed query value, or null when absent or blank. */
    public String param(String name) {
        return Http.param(query, name);
    }

    public boolean has(String name) {
        return Strings.notBlank(query.get(name));
    }

    /**
     * An integer query value with a fallback, clamped to [lo, hi]. A
     * non-numeric value falls back rather than failing the request, the
     * way the paging controls want: a stray ?page=x should land on
     * page one, not a 400.
     */
    public int intParam(String name, int dflt, int lo, int hi) {
        String raw = param(name);
        if (raw == null) {
            return Validate.clamp(dflt, lo, hi);
        }
        int v;
        try {
            v = Integer.parseInt(raw);
        } catch (NumberFormatException nfe) {
            v = dflt;
        }
        return Validate.clamp(v, lo, hi);
    }
}
