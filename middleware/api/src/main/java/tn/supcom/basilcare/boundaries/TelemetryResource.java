package tn.supcom.basilcare.boundaries;

import jakarta.annotation.security.RolesAllowed;
import jakarta.inject.Inject;
import jakarta.json.Json;
import jakarta.json.JsonArrayBuilder;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.QueryParam;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;
import tn.supcom.basilcare.entities.Reading;
import tn.supcom.basilcare.security.Secured;
import tn.supcom.basilcare.services.SensorCatalog;
import tn.supcom.basilcare.services.TelemetryService;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.List;

/** Live values and history for the dashboards (FR-02). */
@Path("telemetry")
@Secured
@RolesAllowed({"Farmer", "Admin"})
@Produces(MediaType.APPLICATION_JSON)
public class TelemetryResource {

    private static final int MAX_POINTS = 10_000;

    @Inject
    TelemetryService telemetry;

    @Inject
    Clock clock;

    /** GET /api/telemetry/latest?deviceId=basil-sim-01 : one live value per sensor, never a buffered one. */
    @GET
    @Path("latest")
    public Response latest(@QueryParam("deviceId") String deviceId) {
        try {
            String id = Params.deviceId(deviceId, true);
            return Response.ok(telemetry.latest(id)).build();
        } catch (IllegalArgumentException e) {
            return Problems.of(Response.Status.BAD_REQUEST, "invalid_query", e.getMessage());
        }
    }

    /**
     * GET /api/telemetry/history?deviceId=...&sensor=ph&from=...&to=...&limit=...
     * Default window: the last 24 hours. Points are ordered by measured_at (contract section 7),
     * and buffered points carry "buffered": true so a chart can draw them differently.
     */
    @GET
    @Path("history")
    public Response history(@QueryParam("deviceId") String deviceId, @QueryParam("sensor") String sensor,
                            @QueryParam("from") String from, @QueryParam("to") String to,
                            @QueryParam("limit") Integer limit) {
        try {
            String id = Params.deviceId(deviceId, true);
            var catalog = SensorCatalog.find(sensor)
                    .orElseThrow(() -> new IllegalArgumentException("Unknown sensor " + sensor + "."));
            Instant end = Params.instant(to, clock.instant(), "to");
            Instant start = Params.instant(from, end.minus(Duration.ofHours(24)), "from");
            if (!start.isBefore(end)) {
                throw new IllegalArgumentException("from must be before to.");
            }
            int max = Params.limit(limit, 2000, MAX_POINTS);
            List<Reading> points = telemetry.history(id, catalog.name(), start, end, max);
            JsonArrayBuilder list = Json.createArrayBuilder();
            for (Reading r : points) {
                list.add(Json.createObjectBuilder()
                        .add("measured_at", r.getMeasuredAt())
                        .add("value", r.getValue())
                        .add("calibrated", r.isCalibrated())
                        .add("buffered", r.isBuffered()));
            }
            return Response.ok(Json.createObjectBuilder()
                    .add("device_id", id)
                    .add("sensor", catalog.name())
                    .add("label", catalog.label())
                    .add("unit", catalog.unit())
                    .add("truncated", points.size() == max)
                    .add("points", list)
                    .build()).build();
        } catch (IllegalArgumentException e) {
            return Problems.of(Response.Status.BAD_REQUEST, "invalid_query", e.getMessage());
        }
    }
}
