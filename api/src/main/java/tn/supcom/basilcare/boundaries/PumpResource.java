package tn.supcom.basilcare.boundaries;

import jakarta.annotation.security.RolesAllowed;
import jakarta.inject.Inject;
import jakarta.json.Json;
import jakarta.json.JsonNumber;
import jakarta.json.JsonObject;
import jakarta.json.JsonValue;
import jakarta.ws.rs.Consumes;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.POST;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.PathParam;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.QueryParam;
import jakarta.ws.rs.container.ContainerRequestContext;
import jakarta.ws.rs.core.Context;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;
import jakarta.ws.rs.core.SecurityContext;
import tn.supcom.basilcare.entities.PumpCommand;
import tn.supcom.basilcare.security.Secured;
import tn.supcom.basilcare.security.SecurityFilter;
import tn.supcom.basilcare.services.PumpService;

/**
 * Pump control (contract section 5). The only way to move the pump from the cloud:
 * PWAs and, later, the MCP server call this endpoint; nobody publishes on pump/cmd directly.
 */
@Path("pump")
@Secured
@RolesAllowed({"Farmer", "Admin"})
@Produces(MediaType.APPLICATION_JSON)
public class PumpResource {

    @Inject
    PumpService pump;

    /**
     * POST /api/pump/{deviceId}/commands
     * Body: {"action": "on", "duration_s": 120, "confirm": true}
     * 202 accepted and sent; 409 rejected by the safety policy (recorded, with the reason);
     * 428 not confirmed; 503 broker unavailable (recorded); 400 invalid body.
     */
    @POST
    @Path("{deviceId}/commands")
    @Consumes(MediaType.APPLICATION_JSON)
    public Response command(@PathParam("deviceId") String deviceId, JsonObject body,
                            @Context SecurityContext security, @Context ContainerRequestContext request) {
        if (body == null) {
            return Problems.of(Response.Status.BAD_REQUEST, "invalid_request", "A JSON body is required.");
        }
        String action = body.get("action") != null && body.get("action").getValueType() == JsonValue.ValueType.STRING
                ? body.getString("action") : null;
        Integer duration = null;
        if (body.get("duration_s") instanceof JsonNumber number) {
            if (!number.isIntegral()) {
                return Problems.of(Response.Status.BAD_REQUEST, "invalid_request", "duration_s must be an integer.");
            }
            duration = number.intValue();
        }
        boolean confirmed = body.get("confirm") == JsonValue.TRUE;
        try {
            PumpCommand command = pump.request(deviceId, action, duration, confirmed, requester(security, request));
            if (PumpCommand.ACCEPTED.equals(command.getDecision())) {
                return Response.accepted(command).build();
            }
            int status = "broker_unavailable".equals(command.getDecisionReason()) ? 503 : 409;
            return Response.status(status).entity(command).build();
        } catch (PumpService.ConfirmationRequired e) {
            return Problems.of(428, "confirmation_required", e.getMessage());
        } catch (IllegalArgumentException e) {
            return Problems.of(Response.Status.BAD_REQUEST, "invalid_request", e.getMessage());
        }
    }

    /** GET /api/pump/{deviceId}: last state reported by the device, plus the API's limits. */
    @GET
    @Path("{deviceId}")
    public Response state(@PathParam("deviceId") String deviceId) {
        var limits = pump.limits();
        var json = Json.createObjectBuilder()
                .add("device_id", deviceId)
                .add("max_duration_s", limits.maxDurationS())
                .add("min_water_level", limits.minWaterLevel());
        pump.status(deviceId).ifPresentOrElse(s -> {
            json.add("state", s.getState());
            json.add("until", s.getUntil() == null ? JsonValue.NULL : Json.createValue(s.getUntil()));
            json.add("reason", s.getReason() == null ? JsonValue.NULL : Json.createValue(s.getReason()));
            json.add("reported_at", s.getReportedAt());
        }, () -> json.add("state", JsonValue.NULL));
        return Response.ok(json.build()).build();
    }

    /** GET /api/pump/commands?deviceId=...&limit=... : the audit trail, newest first. */
    @GET
    @Path("commands")
    public Response commands(@QueryParam("deviceId") String deviceId, @QueryParam("limit") Integer limit) {
        try {
            return Response.ok(pump.commands(Params.deviceId(deviceId, false), Params.limit(limit, 50, 1000))).build();
        } catch (IllegalArgumentException e) {
            return Problems.of(Response.Status.BAD_REQUEST, "invalid_query", e.getMessage());
        }
    }

    private static PumpService.Requester requester(SecurityContext security, ContainerRequestContext request) {
        String role = security.isUserInRole("Admin") ? "Admin" : "Farmer";
        String clientId = null;
        if (request.getProperty(SecurityFilter.CLAIMS) instanceof JsonObject claims
                && claims.get("aud") != null && claims.get("aud").getValueType() == JsonValue.ValueType.STRING) {
            clientId = claims.getString("aud");
        }
        return new PumpService.Requester(security.getUserPrincipal().getName(), role, clientId);
    }
}
