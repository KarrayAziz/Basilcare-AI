package tn.supcom.basilcare.security;

import jakarta.annotation.Priority;
import jakarta.annotation.security.RolesAllowed;
import jakarta.inject.Inject;
import jakarta.json.JsonObject;
import jakarta.json.JsonString;
import jakarta.ws.rs.Priorities;
import jakarta.ws.rs.container.ContainerRequestContext;
import jakarta.ws.rs.container.ContainerRequestFilter;
import jakarta.ws.rs.container.ResourceInfo;
import jakarta.ws.rs.core.Context;
import jakarta.ws.rs.core.HttpHeaders;
import jakarta.ws.rs.core.Response;
import jakarta.ws.rs.core.SecurityContext;
import jakarta.ws.rs.ext.Provider;

import java.security.Principal;
import java.util.Arrays;
import java.util.Optional;
import java.util.Set;
import java.util.stream.Collectors;

/**
 * Runs before every @Secured endpoint:
 * 401 if the token is missing or invalid, 403 if the role is not in @RolesAllowed.
 */
@Secured
@Provider
@Priority(Priorities.AUTHENTICATION)
public class SecurityFilter implements ContainerRequestFilter {

    @Inject
    JwtVerifier verifier;

    @Context
    ResourceInfo resourceInfo;

    @Override
    public void filter(ContainerRequestContext request) {
        String header = request.getHeaderString(HttpHeaders.AUTHORIZATION);
        if (header == null || !header.startsWith("Bearer ")) {
            abort(request, Response.Status.UNAUTHORIZED);
            return;
        }
        Optional<JsonObject> claims = verifier.verify(header.substring("Bearer ".length()).trim());
        if (claims.isEmpty()) {
            abort(request, Response.Status.UNAUTHORIZED);
            return;
        }
        String subject = claims.get().getString("sub");
        Set<String> roles = claims.get().getJsonArray("groups").getValuesAs(JsonString.class).stream()
                .map(JsonString::getString)
                .collect(Collectors.toSet());

        RolesAllowed allowed = resourceInfo.getResourceMethod().getAnnotation(RolesAllowed.class);
        if (allowed == null) {
            allowed = resourceInfo.getResourceClass().getAnnotation(RolesAllowed.class);
        }
        if (allowed != null && Arrays.stream(allowed.value()).noneMatch(roles::contains)) {
            abort(request, Response.Status.FORBIDDEN);
            return;
        }

        // make the caller available to resources through @Context SecurityContext
        boolean secure = request.getSecurityContext().isSecure();
        Principal principal = () -> subject;
        request.setSecurityContext(new SecurityContext() {
            @Override
            public Principal getUserPrincipal() {
                return principal;
            }

            @Override
            public boolean isUserInRole(String role) {
                return roles.contains(role);
            }

            @Override
            public boolean isSecure() {
                return secure;
            }

            @Override
            public String getAuthenticationScheme() {
                return "Bearer";
            }
        });
    }

    private void abort(ContainerRequestContext request, Response.Status status) {
        request.abortWith(Response.status(status).header(HttpHeaders.WWW_AUTHENTICATE, "Bearer").build());
    }
}