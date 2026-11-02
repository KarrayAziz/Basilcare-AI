package tn.supcom.basilcare.boundaries;

import jakarta.inject.Inject;
import jakarta.json.Json;
import jakarta.ws.rs.Consumes;
import jakarta.ws.rs.FormParam;
import jakarta.ws.rs.POST;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;
import org.eclipse.microprofile.config.inject.ConfigProperty;
import tn.supcom.basilcare.entities.Identity;
import tn.supcom.basilcare.repositories.IdentityRepository;
import tn.supcom.basilcare.security.AuthorizationCodeStore;
import tn.supcom.basilcare.security.AuthorizationCodeStore.Grant;
import tn.supcom.basilcare.security.JwtIssuer;
import tn.supcom.basilcare.security.Pkce;

import java.util.Optional;

/** OAuth step 6-7: exchange code + PKCE verifier for an access token. */
@Path("oauth/token")
public class TokenEndpoint {

    @Inject
    AuthorizationCodeStore codes;

    @Inject
    IdentityRepository identities;

    @Inject
    JwtIssuer jwt;

    @Inject
    @ConfigProperty(name = "jwt.lifetime.seconds")
    long lifetimeSeconds;

    @POST
    @Consumes(MediaType.APPLICATION_FORM_URLENCODED)
    @Produces(MediaType.APPLICATION_JSON)
    public Response token(@FormParam("grant_type") String grantType,
                          @FormParam("code") String code,
                          @FormParam("client_id") String clientId,
                          @FormParam("redirect_uri") String redirectUri,
                          @FormParam("code_verifier") String codeVerifier) {
        if (!"authorization_code".equals(grantType)) {
            return error("unsupported_grant_type");
        }
        if (code == null || codeVerifier == null) {
            return error("invalid_request");
        }
        Optional<Grant> found = codes.consume(code);
        if (found.isEmpty()) {
            return error("invalid_grant");          // unknown, expired or already used
        }
        Grant grant = found.get();
        if (!grant.clientId().equals(clientId)
                || !grant.redirectUri().equals(redirectUri)
                || !Pkce.matches(codeVerifier, grant.codeChallenge())) {
            return error("invalid_grant");
        }
        Identity identity = identities.findById(grant.username()).orElseThrow();
        String accessToken = jwt.issue(grant.clientId(), identity.getUsername(), identity.getRole(), grant.scope());
        return Response.ok(Json.createObjectBuilder()
                        .add("access_token", accessToken)
                        .add("token_type", "Bearer")
                        .add("expires_in", lifetimeSeconds)
                        .build())
                .header("Cache-Control", "no-store")   // tokens must not be cached
                .build();
    }

    private Response error(String code) {
        return Response.status(Response.Status.BAD_REQUEST)
                .entity(Json.createObjectBuilder().add("error", code).build())
                .build();
    }
}