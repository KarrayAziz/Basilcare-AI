package tn.supcom.basilcare.boundaries;

import jakarta.annotation.security.RolesAllowed;
import jakarta.inject.Inject;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.PathParam;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;
import tn.supcom.basilcare.entities.DeviceState;
import tn.supcom.basilcare.security.Secured;
import tn.supcom.basilcare.services.TelemetryService;

import java.util.List;

/**
 * Online/offline state reported by the devices themselves (retained status topic).
 * A separate root from /devices on purpose: /devices is the administrator's registry.
 */
@Path("device-states")
@Secured
@RolesAllowed({"Farmer", "Admin"})
@Produces(MediaType.APPLICATION_JSON)
public class DeviceStateResource {

    @Inject
    TelemetryService telemetry;

    @GET
    public List<DeviceState> list() {
        return telemetry.deviceStates();
    }

    @GET
    @Path("{deviceId}")
    public Response get(@PathParam("deviceId") String deviceId) {
        return telemetry.deviceState(deviceId)
                .<Response>map(state -> Response.ok(state).build())
                .orElseGet(() -> Problems.of(Response.Status.NOT_FOUND, "state_unknown",
                        "No status received yet from " + deviceId + "."));
    }
}
