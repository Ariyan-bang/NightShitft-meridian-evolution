package ca.meridian.api.v2;

import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

/**
 * Marks a method as a v2 route handler.
 *
 * The original service wired routes up by hand in ApiServer and later
 * through {@link ca.meridian.api.Router}. Neither reads well once a
 * family of endpoints shares the same shape, so the 2026 versioning
 * work took a different tack for v2: a method annotated with the path
 * it serves, discovered by {@link Dispatcher} at start-up through
 * reflection. It is the thin edge of the request-mapping style the
 * 2014 Spring application had, brought back for the new surface only.
 *
 * An annotated method must be public, take a single {@link V2Request}
 * and return a {@link V2Response}.
 *
 * R. Osei 2026
 */
@Retention(RetentionPolicy.RUNTIME)
@Target(ElementType.METHOD)
public @interface Endpoint {

    /** The exact request path this method answers, e.g. /api/v2/forecast. */
    String path();

    /** The HTTP verb. Only GET is used today. */
    String verb() default "GET";

    /** A one-line summary for the route index. */
    String summary() default "";
}
