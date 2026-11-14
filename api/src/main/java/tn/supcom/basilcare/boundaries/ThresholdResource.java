package tn.supcom.basilcare.boundaries;

import jakarta.annotation.security.RolesAllowed;
import jakarta.inject.Inject;
import jakarta.ws.rs.Consumes;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.PUT;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.PathParam;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.Context;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;
import jakarta.ws.rs.core.SecurityContext;
import tn.supcom.basilcare.entities.Threshold;
import tn.supcom.basilcare.security.Secured;
import tn.supcom.basilcare.services.ThresholdService;

import java.util.List;

/** Agronomic alert ranges: everyone reads them, only administrators change them. */
@Path("thresholds")
@Secured
@Produces(MediaType.APPLICATION_JSON)
public class ThresholdResource {

    @Inject
    ThresholdService thresholds;

    @GET
    @RolesAllowed({"Farmer", "Admin"})
    public List<Threshold> list() {
        return thresholds.list();
    }

    /** Body: {"min": 5.5, "max": 6.5, "enabled": true, "severity": "warning", "verified": true, "source": "..."} */
    @PUT
    @Path("{sensor}")
    @RolesAllowed("Admin")
    @Consumes(MediaType.APPLICATION_JSON)
    public Response update(@PathParam("sensor") String sensor, Threshold request, @Context SecurityContext security) {
        try {
            return Response.ok(thresholds.update(sensor, request, security.getUserPrincipal().getName())).build();
        } catch (IllegalArgumentException e) {
            return Problems.of(Response.Status.BAD_REQUEST, "invalid_threshold", e.getMessage());
        }
    }
}
