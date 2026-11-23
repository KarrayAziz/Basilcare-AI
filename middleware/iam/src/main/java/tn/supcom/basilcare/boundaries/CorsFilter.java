package tn.supcom.basilcare.boundaries;

import jakarta.inject.Inject;
import jakarta.ws.rs.container.ContainerRequestContext;
import jakarta.ws.rs.container.ContainerRequestFilter;
import jakarta.ws.rs.container.PreMatching;
import jakarta.ws.rs.core.Response;
import jakarta.ws.rs.container.ContainerResponseContext;
import jakarta.ws.rs.container.ContainerResponseFilter;
import jakarta.ws.rs.ext.Provider;
import org.eclipse.microprofile.config.inject.ConfigProperty;

import java.util.List;

/** Adds CORS headers for the PWA origins listed in cors.allowed.origins. */
@Provider
@PreMatching
public class CorsFilter implements ContainerRequestFilter, ContainerResponseFilter {

    @Inject
    @ConfigProperty(name = "cors.allowed.origins")
    List<String> allowedOrigins;

    // Preflight is unauthenticated; the actual resource request still needs its token.
    @Override
    public void filter(ContainerRequestContext request) {
        if ("OPTIONS".equals(request.getMethod())
                && request.getHeaderString("Access-Control-Request-Method") != null) {
            String method = request.getHeaderString("Access-Control-Request-Method");
            boolean permitted = allowedOrigins.contains(request.getHeaderString("Origin"))
                    && List.of("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS").contains(method);
            request.abortWith(Response.status(permitted ? 204 : 403).build());
        }
    }

    @Override
    public void filter(ContainerRequestContext request, ContainerResponseContext response) {
        String origin = request.getHeaderString("Origin");
        if (origin != null && allowedOrigins.contains(origin)) {
            response.getHeaders().putSingle("Access-Control-Allow-Origin", origin);
            response.getHeaders().putSingle("Vary", "Origin");
            response.getHeaders().putSingle("Access-Control-Allow-Headers", "Authorization, Content-Type");
            response.getHeaders().putSingle("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS");
        }
    }
}
