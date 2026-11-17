package tn.supcom.basilcare.boundaries;

import jakarta.json.Json;
import jakarta.json.JsonObject;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.MediaType;

import java.time.OffsetDateTime;

/** Public liveness check: GET /api/health. Used by the deploy script and Postman. */
@Path("health")
public class HealthResource {

    @GET
    @Produces(MediaType.APPLICATION_JSON)
    public JsonObject health() {
        return Json.createObjectBuilder()
                .add("service", "basilcare-api")
                .add("status", "UP")
                .add("time", OffsetDateTime.now().toString())
                .build();
    }
}