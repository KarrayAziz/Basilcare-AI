package tn.supcom.basilcare.boundaries;

import jakarta.inject.Inject;
import jakarta.ws.rs.Consumes;
import jakarta.ws.rs.FormParam;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.POST;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.QueryParam;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;
import jakarta.ws.rs.core.UriBuilder;
import tn.supcom.basilcare.entities.Identity;
import tn.supcom.basilcare.entities.Tenant;
import tn.supcom.basilcare.repositories.IdentityRepository;
import tn.supcom.basilcare.repositories.TenantRepository;
import tn.supcom.basilcare.security.AuthorizationCodeStore;
import tn.supcom.basilcare.security.PasswordHasher;

import java.time.Instant;
import java.util.Optional;

/** OAuth steps 2 to 5: show the login page, check the password, redirect back with a code. */
@Path("/")
public class AuthorizationEndpoint {

    @Inject
    TenantRepository tenants;

    @Inject
    IdentityRepository identities;

    @Inject
    PasswordHasher hasher;

    @Inject
    AuthorizationCodeStore codes;

    @GET
    @Path("authorize")
    @Produces(MediaType.TEXT_HTML)
    public Response authorize(@QueryParam("client_id") String clientId,
                              @QueryParam("redirect_uri") String redirectUri,
                              @QueryParam("response_type") String responseType,
                              @QueryParam("code_challenge") String codeChallenge,
                              @QueryParam("code_challenge_method") String challengeMethod) {
        String problem = checkRequest(clientId, redirectUri, responseType, codeChallenge, challengeMethod);
        return problem != null ? Pages.error(problem) : Pages.page("login.html");
    }

    @POST
    @Path("login")
    @Consumes(MediaType.APPLICATION_FORM_URLENCODED)
    @Produces(MediaType.TEXT_HTML)
    public Response login(@QueryParam("client_id") String clientId,
                          @QueryParam("redirect_uri") String redirectUri,
                          @QueryParam("response_type") String responseType,
                          @QueryParam("code_challenge") String codeChallenge,
                          @QueryParam("code_challenge_method") String challengeMethod,
                          @QueryParam("scope") String scope,
                          @QueryParam("state") String state,
                          @FormParam("username") String username,
                          @FormParam("password") String password) {
        String problem = checkRequest(clientId, redirectUri, responseType, codeChallenge, challengeMethod);
        if (problem != null) {
            return Pages.error(problem);
        }
        if (username == null || password == null) {
            return Pages.error("Username and password are required.");
        }
        Optional<Identity> identity = identities.findById(username);
        if (identity.isEmpty() || !hasher.verify(identity.get().getPasswordHash(), password.toCharArray())) {
            return Pages.error("Wrong username or password.");
        }
        if (!identity.get().isActive()) {
            return Pages.error("Your account is not activated yet. Enter the code you received by e-mail.");
        }
        Tenant tenant = tenants.findById(clientId).orElseThrow();
        if (!tenant.allows(identity.get().getRole())) {
            return Pages.error("Your account cannot use this application.");
        }

        String code = codes.create(new AuthorizationCodeStore.Grant(
                clientId, username, scope == null ? "" : scope, redirectUri, codeChallenge,
                Instant.now().plusSeconds(120)));
        UriBuilder target = UriBuilder.fromUri(redirectUri).queryParam("code", code);
        if (state != null) {
            target.queryParam("state", state);   // lets the PWA check the answer belongs to its request
        }
        return Response.seeOther(target.build()).build();
    }

    /** Returns an error message, or null when the request is valid. */
    private String checkRequest(String clientId, String redirectUri, String responseType,
                                String codeChallenge, String challengeMethod) {
        if (clientId == null) {
            return "client_id is missing.";
        }
        Optional<Tenant> tenant = tenants.findById(clientId);
        if (tenant.isEmpty()) {
            return "Unknown application: " + clientId;
        }
        if (!tenant.get().getRedirectUri().equals(redirectUri)) {
            return "redirect_uri does not match the one registered for this application.";
        }
        if (!"code".equals(responseType)) {
            return "response_type must be 'code'.";
        }
        if (codeChallenge == null || !"S256".equals(challengeMethod)) {
            return "PKCE is required (code_challenge with code_challenge_method=S256).";
        }
        return null;
    }
}