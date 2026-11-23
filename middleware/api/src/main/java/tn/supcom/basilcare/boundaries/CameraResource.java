package tn.supcom.basilcare.boundaries;

import jakarta.annotation.security.RolesAllowed;
import jakarta.inject.Inject;
import jakarta.json.Json;
import jakarta.json.JsonObjectBuilder;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.PathParam;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.CacheControl;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;
import tn.supcom.basilcare.security.Secured;
import tn.supcom.basilcare.services.LiveFrameStore;

import java.time.Duration;

/**
 * Live camera view (contract section 6a): the latest frame of a device with the model's
 * detections. The farmer app polls it about twice a second while the view is open.
 */
@Path("camera")
@Secured
@RolesAllowed({"Farmer", "Admin"})
@Produces(MediaType.APPLICATION_JSON)
public class CameraResource {

    @Inject
    LiveFrameStore frames;

    @GET
    @Path("{deviceId}/live")
    public Response live(@PathParam("deviceId") String deviceId) {
        String id;
        try {
            id = Params.deviceId(deviceId, true);
        } catch (IllegalArgumentException e) {
            return Problems.of(Response.Status.BAD_REQUEST, "invalid_query", e.getMessage());
        }
        CacheControl noStore = new CacheControl();
        noStore.setNoStore(true);
        return frames.latest(id)
                .map(frame -> {
                    JsonObjectBuilder body = Json.createObjectBuilder(frame.payload())
                            .add("received_at", frame.receivedAt().toString())
                            .add("age_s", Duration.between(frame.receivedAt(), frames.now()).toMillis() / 1000.0);
                    return Response.ok(body.build()).cacheControl(noStore).build();
                })
                .orElseGet(() -> Problems.of(Response.Status.NOT_FOUND, "no_live_frame",
                        "No live camera frame received from " + id + " since the server started."));
    }
}
