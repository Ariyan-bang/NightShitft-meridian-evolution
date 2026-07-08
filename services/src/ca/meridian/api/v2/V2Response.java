package ca.meridian.api.v2;

import com.sun.net.httpserver.HttpExchange;

import java.io.IOException;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * The response side of the v2 dispatch. A handler builds one of these
 * and hands it back to {@link Dispatcher}, which writes it. Carrying
 * the status, content type and body as a value rather than writing to
 * the exchange inline lets the dispatcher add the shared headers (CORS,
 * and whatever else the versioned surface grows) in one place instead
 * of each handler repeating them, which is the trap the original
 * handlers fell into.
 *
 * R. Osei 2026
 */
public final class V2Response {

    private final int status;
    private final String contentType;
    private final byte[] body;
    private final Map<String, String> headers = new LinkedHashMap<>();

    private V2Response(int status, String contentType, byte[] body) {
        this.status = status;
        this.contentType = contentType;
        this.body = body;
    }

    public static V2Response json(String json) {
        return new V2Response(200, "application/json",
                json.getBytes(StandardCharsets.UTF_8));
    }

    public static V2Response json(int status, String json) {
        return new V2Response(status, "application/json",
                json.getBytes(StandardCharsets.UTF_8));
    }

    public static V2Response csv(String filename, String csv) {
        V2Response r = new V2Response(200, "text/csv; charset=utf-8",
                csv.getBytes(StandardCharsets.UTF_8));
        r.headers.put("Content-Disposition", "attachment; filename=\"" + filename + "\"");
        return r;
    }

    public static V2Response error(int status, String message) {
        String safe = message == null ? "" : message.replace("\"", "'");
        return json(status, "{\"error\":\"" + safe + "\"}");
    }

    public V2Response header(String name, String value) {
        headers.put(name, value);
        return this;
    }

    void writeTo(HttpExchange ex) throws IOException {
        ex.getResponseHeaders().add("Content-Type", contentType);
        ex.getResponseHeaders().add("Access-Control-Allow-Origin", "*");
        for (Map.Entry<String, String> e : headers.entrySet()) {
            ex.getResponseHeaders().add(e.getKey(), e.getValue());
        }
        ex.sendResponseHeaders(status, body.length);
        try (OutputStream os = ex.getResponseBody()) {
            os.write(body);
        }
    }
}
