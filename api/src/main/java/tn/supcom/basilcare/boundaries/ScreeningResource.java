package tn.supcom.basilcare.boundaries;

import jakarta.annotation.security.RolesAllowed;
import jakarta.inject.Inject;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.QueryParam;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;
import tn.supcom.basilcare.security.Secured;
import tn.supcom.basilcare.services.TelemetryService;

/** Edge image-screening results (FR-05), newest first. */
@Path("screenings")
@Secured
@RolesAllowed({"Farmer", "Admin"})
@Produces(MediaType.APPLICATION_JSON)
public class ScreeningResource {

    @Inject
    TelemetryService telemetry;

    @GET
    public Response list(@QueryParam("deviceId") String deviceId, @QueryParam("limit") Integer limit) {
        try {
            return Response.ok(telemetry.screenings(Params.deviceId(deviceId, false), Params.limit(limit, 20, 500)))
                    .build();
        } catch (IllegalArgumentException e) {
            return Problems.of(Response.Status.BAD_REQUEST, "invalid_query", e.getMessage());
        }
    }
}
