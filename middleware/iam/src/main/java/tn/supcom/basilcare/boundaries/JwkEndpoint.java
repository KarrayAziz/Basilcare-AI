package tn.supcom.basilcare.boundaries;

import jakarta.inject.Inject;
import jakarta.json.JsonObject;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.MediaType;
import tn.supcom.basilcare.security.JwtIssuer;

/** GET /iam/jwk: the public key(s) other services use to verify our tokens. */
@Path("jwk")
public class JwkEndpoint {

    @Inject
    JwtIssuer jwt;

    @GET
    @Produces(MediaType.APPLICATION_JSON)
    public JsonObject keys() {
        return jwt.publicKeys();
    }
}