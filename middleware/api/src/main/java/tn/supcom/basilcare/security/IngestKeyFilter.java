package tn.supcom.basilcare.security;

import jakarta.annotation.Priority;
import jakarta.inject.Inject;
import jakarta.json.Json;
import jakarta.ws.rs.Priorities;
import jakarta.ws.rs.container.ContainerRequestContext;
import jakarta.ws.rs.container.ContainerRequestFilter;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;
import jakarta.ws.rs.ext.Provider;
import org.eclipse.microprofile.config.inject.ConfigProperty;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Optional;

/**
 * Checks the X-Ingest-Key header of every @IngestKeyRequired endpoint.
 *
 * The key comes from the INGEST_KEY environment variable (config key ingest.key) and is
 * never committed. Without a configured key, ingestion is disabled (fail closed).
 * The comparison is constant-time so the key cannot be guessed from response times.
 */
@IngestKeyRequired
@Provider
@Priority(Priorities.AUTHENTICATION)
public class IngestKeyFilter implements ContainerRequestFilter {

    public static final String HEADER = "X-Ingest-Key";

    @Inject
    @ConfigProperty(name = "ingest.key")
    Optional<String> configuredKey;

    @Override
    public void filter(ContainerRequestContext request) {
        String expected = configuredKey.map(String::trim).orElse("");
        if (expected.isEmpty()) {
            abort(request, Response.Status.SERVICE_UNAVAILABLE, "ingest_disabled",
                    "Set INGEST_KEY on the server to enable ingestion.");
            return;
        }
        if (!matches(expected, request.getHeaderString(HEADER))) {
            abort(request, Response.Status.UNAUTHORIZED, "invalid_ingest_key",
                    "Missing or wrong " + HEADER + " header.");
        }
    }

    static boolean matches(String expected, String given) {
        if (given == null) {
            return false;
        }
        return MessageDigest.isEqual(expected.getBytes(StandardCharsets.UTF_8),
                given.trim().getBytes(StandardCharsets.UTF_8));
    }

    private static void abort(ContainerRequestContext request, Response.Status status, String code, String message) {
        request.abortWith(Response.status(status)
                .type(MediaType.APPLICATION_JSON)
                .entity(Json.createObjectBuilder().add("error", code).add("message", message).build())
                .build());
    }
}
