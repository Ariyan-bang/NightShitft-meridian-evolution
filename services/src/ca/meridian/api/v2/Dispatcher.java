package ca.meridian.api.v2;

import ca.meridian.util.TinyJson;
import ca.meridian.util.Validate;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;

import java.io.IOException;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

/**
 * The v2 request-mapping layer.
 *
 * One JDK context is registered at /api/v2 and this dispatches within
 * it, rather than giving every v2 route its own context the way the
 * hand-rolled {@link ca.meridian.api.Router} does for the 2019-21
 * endpoints. At construction it scans the controller objects it is
 * given for {@link Endpoint}-annotated methods and builds a path/verb
 * table; at request time it matches the exact path, invokes the method
 * reflectively with a {@link V2Request}, and writes the returned
 * {@link V2Response}.
 *
 * This is knowingly a second way of doing what Router already does. It
 * was brought in with the versioning work because the annotations keep
 * the route next to the code that serves it, and it is scoped to v2 so
 * the older contexts are left exactly as they were. The two styles now
 * sit side by side; consolidating them was filed and not scheduled.
 *
 * R. Osei 2026
 */
public final class Dispatcher implements HttpHandler {

    /** One resolved route: the controller instance and its method. */
    private static final class Mapping {
        final Object controller;
        final Method method;
        final String summary;

        Mapping(Object controller, Method method, String summary) {
            this.controller = controller;
            this.method = method;
            this.summary = summary;
        }
    }

    // path -> (verb -> mapping)
    private final Map<String, Map<String, Mapping>> table = new TreeMap<>();
    private final String base;

    private Dispatcher(String base) {
        this.base = base;
    }

    /** Builds a dispatcher rooted at /api/v2 from the given controllers. */
    public static Dispatcher of(Object... controllers) {
        return rooted("/api/v2", controllers);
    }

    public static Dispatcher rooted(String base, Object... controllers) {
        Dispatcher d = new Dispatcher(base);
        for (Object c : controllers) {
            d.register(c);
        }
        return d;
    }

    private void register(Object controller) {
        for (Method m : controller.getClass().getMethods()) {
            Endpoint ep = m.getAnnotation(Endpoint.class);
            if (ep == null) {
                continue;
            }
            checkSignature(controller, m);
            String path = ep.path();
            String verb = ep.verb().toUpperCase();
            Map<String, Mapping> byVerb = table.get(path);
            if (byVerb == null) {
                byVerb = new LinkedHashMap<>();
                table.put(path, byVerb);
            }
            if (byVerb.containsKey(verb)) {
                throw new IllegalStateException(
                        "two handlers for " + verb + " " + path);
            }
            byVerb.put(verb, new Mapping(controller, m, ep.summary()));
        }
    }

    private static void checkSignature(Object controller, Method m) {
        Class<?>[] params = m.getParameterTypes();
        boolean ok = params.length == 1
                && params[0] == V2Request.class
                && V2Response.class.isAssignableFrom(m.getReturnType());
        if (!ok) {
            throw new IllegalStateException("endpoint method "
                    + controller.getClass().getSimpleName() + "." + m.getName()
                    + " must be (V2Request) -> V2Response");
        }
    }

    /** The registered routes, for the service's /api index. */
    public List<String[]> routes() {
        List<String[]> out = new ArrayList<>();
        for (Map.Entry<String, Map<String, Mapping>> e : table.entrySet()) {
            for (Mapping m : e.getValue().values()) {
                out.add(new String[] { e.getKey(), m.summary });
            }
        }
        return out;
    }

    @Override
    public void handle(HttpExchange ex) throws IOException {
        String path = ex.getRequestURI().getPath();
        if (path.endsWith("/") && path.length() > 1) {
            path = path.substring(0, path.length() - 1);
        }

        // The bare base path returns a small index of what lives under it.
        if (path.equals(base)) {
            index(ex);
            return;
        }

        Map<String, Mapping> byVerb = table.get(path);
        if (byVerb == null) {
            write(ex, V2Response.error(404, "no such v2 route: " + path));
            return;
        }
        Mapping mapping = byVerb.get(ex.getRequestMethod().toUpperCase());
        if (mapping == null) {
            write(ex, V2Response.error(405, "method not allowed"));
            return;
        }

        V2Response response;
        try {
            V2Request req = new V2Request(ex);
            response = (V2Response) mapping.method.invoke(mapping.controller, req);
        } catch (InvocationTargetException ite) {
            response = mapError(ite.getCause());
        } catch (IllegalAccessException iae) {
            response = V2Response.error(500, "dispatch failed");
        }
        write(ex, response);
    }

    private static V2Response mapError(Throwable cause) {
        if (cause instanceof Validate.BadRequest) {
            return V2Response.error(400, cause.getMessage());
        }
        if (cause instanceof IOException) {
            return V2Response.error(500, cause.getMessage());
        }
        String msg = cause == null ? "server error" : cause.getMessage();
        return V2Response.error(500, msg == null ? "server error" : msg);
    }

    private void index(HttpExchange ex) throws IOException {
        List<Object> list = new ArrayList<>();
        for (Map.Entry<String, Map<String, Mapping>> e : table.entrySet()) {
            Map<String, Object> m = new LinkedHashMap<>();
            m.put("path", e.getKey());
            m.put("verbs", new ArrayList<>(e.getValue().keySet()));
            Mapping any = e.getValue().values().iterator().next();
            m.put("summary", any.summary);
            list.add(m);
        }
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("base", base);
        body.put("routes", list);
        write(ex, V2Response.json(TinyJson.write(body)));
    }

    private static void write(HttpExchange ex, V2Response r) throws IOException {
        r.writeTo(ex);
    }

    // kept so callers can list verbs without exposing the table
    public List<String> verbsFor(String path) {
        Map<String, Mapping> byVerb = table.get(path);
        if (byVerb == null) {
            return Collections.emptyList();
        }
        return new ArrayList<>(byVerb.keySet());
    }
}
