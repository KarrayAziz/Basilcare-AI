package tn.supcom.basilcare.boundaries;

import jakarta.annotation.security.RolesAllowed;
import jakarta.json.Json;
import jakarta.json.JsonObject;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.Context;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.SecurityContext;
import tn.supcom.basilcare.security.Secured;

/** GET /api/me: who am I according to my token? */
@Path("me")
public class MeResource {

    @GET
    @Secured
    @RolesAllowed({"Farmer", "Admin"})
    @Produces(MediaType.APPLICATION_JSON)
    public JsonObject me(@Context SecurityContext security) {
        return Json.createObjectBuilder()
                .add("username", security.getUserPrincipal().getName())
                .add("admin", security.isUserInRole("Admin"))
                .build();
    }
}