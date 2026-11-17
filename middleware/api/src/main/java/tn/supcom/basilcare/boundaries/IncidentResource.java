package tn.supcom.basilcare.boundaries;

import jakarta.annotation.security.RolesAllowed;
import jakarta.inject.Inject;
import jakarta.json.JsonObject;
import jakarta.json.JsonValue;
import jakarta.ws.rs.Consumes;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.POST;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.PathParam;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.QueryParam;
import jakarta.ws.rs.core.Context;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;
import jakarta.ws.rs.core.SecurityContext;
import tn.supcom.basilcare.entities.Incident;
import tn.supcom.basilcare.security.Secured;
import tn.supcom.basilcare.services.IncidentService;

import java.util.List;
import java.util.Optional;

/** Incidents (FR-03): list, acknowledge, resolve with a note (FR-04). */
@Path("incidents")
@Secured
@RolesAllowed({"Farmer", "Admin"})
@Produces(MediaType.APPLICATION_JSON)
public class IncidentResource {

    @Inject
    IncidentService incidents;

    /**
     * GET /api/incidents?status=unresolved|open|acknowledged|resolved|all&deviceId=...&limit=...
     * Default: unresolved (open + acknowledged), newest first.
     */
    @GET
    public Response list(@QueryParam("status") String status, @QueryParam("deviceId") String deviceId,
                         @QueryParam("limit") Integer limit) {
        try {
            List<String> statuses = switch (status == null ? "unresolved" : status) {
                case "unresolved" -> List.of(Incident.OPEN, Incident.ACKNOWLEDGED);
                case "open" -> List.of(Incident.OPEN);
                case "acknowledged" -> List.of(Incident.ACKNOWLEDGED);
                case "resolved" -> List.of(Incident.RESOLVED);
                case "all" -> List.of();
                default -> throw new IllegalArgumentException(
                        "status must be unresolved, open, acknowledged, resolved or all.");
            };
            return Response.ok(incidents.list(Params.deviceId(deviceId, false), statuses,
                    Params.limit(limit, 100, 1000))).build();
        } catch (IllegalArgumentException e) {
            return Problems.of(Response.Status.BAD_REQUEST, "invalid_query", e.getMessage());
        }
    }

    @GET
    @Path("{id}")
    public Response get(@PathParam("id") String id) {
        return found(incidents.find(id));
    }

    @POST
    @Path("{id}/acknowledge")
    public Response acknowledge(@PathParam("id") String id, @Context SecurityContext security) {
        try {
            return found(incidents.acknowledge(id, security.getUserPrincipal().getName()));
        } catch (IllegalStateException e) {
            return Problems.of(Response.Status.CONFLICT, "already_resolved", e.getMessage());
        }
    }

    /** Body: {"note": "Recalibrated the pH probe and replaced the solution."} */
    @POST
    @Path("{id}/resolve")
    @Consumes(MediaType.APPLICATION_JSON)
    public Response resolve(@PathParam("id") String id, JsonObject body, @Context SecurityContext security) {
        String note = body != null && body.get("note") != null
                && body.get("note").getValueType() == JsonValue.ValueType.STRING ? body.getString("note") : null;
        try {
            return found(incidents.resolve(id, security.getUserPrincipal().getName(), note));
        } catch (IllegalArgumentException e) {
            return Problems.of(Response.Status.BAD_REQUEST, "note_required", e.getMessage());
        } catch (IllegalStateException e) {
            return Problems.of(Response.Status.CONFLICT, "already_resolved", e.getMessage());
        }
    }

    private static Response found(Optional<Incident> incident) {
        return incident.<Response>map(i -> Response.ok(i).build())
                .orElseGet(() -> Problems.of(Response.Status.NOT_FOUND, "incident_not_found", "No such incident."));
    }
}
