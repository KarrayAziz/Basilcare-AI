package tn.supcom.basilcare.boundaries;

import jakarta.inject.Inject;
import jakarta.json.Json;
import jakarta.ws.rs.Consumes;
import jakarta.ws.rs.DELETE;
import jakarta.ws.rs.HeaderParam;
import jakarta.ws.rs.PATCH;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.PathParam;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;
import tn.supcom.basilcare.security.JwtIssuer;
import tn.supcom.basilcare.services.AccountManagementService;
import tn.supcom.basilcare.services.AccountManagementService.AccountProblem;

/** Account mutations use verified Admin-client tokens and a live database role check. */
@Path("accounts/{username}")
@Produces(MediaType.APPLICATION_JSON)
public class AccountResource {
    @Inject
    JwtIssuer jwt;
    @Inject
    AccountManagementService accounts;

    public static class Update {
        private String role;
        private Boolean active;
        public String getRole() { return role; }
        public void setRole(String role) { this.role = role; }
        public Boolean getActive() { return active; }
        public void setActive(Boolean active) { this.active = active; }
    }

    @DELETE
    public Response delete(@HeaderParam("Authorization") String authorization,
                           @PathParam("username") String username) {
        return execute(authorization, actor -> accounts.delete(actor, username));
    }

    @PATCH
    @Consumes(MediaType.APPLICATION_JSON)
    public Response update(@HeaderParam("Authorization") String authorization,
                           @PathParam("username") String username, Update request) {
        return execute(authorization, actor -> {
            if (request == null) throw new AccountProblem(400, "invalid_update", "A JSON body is required.");
            accounts.update(actor, username, request.getRole(), request.getActive());
        });
    }

    private Response execute(String authorization, java.util.function.Consumer<String> action) {
        var actor = authorization != null && authorization.startsWith("Bearer ")
                ? jwt.adminSubject(authorization.substring(7).trim()) : java.util.Optional.<String>empty();
        if (actor.isEmpty()) {
            return Response.fromResponse(error(401, "invalid_admin_token", "A valid Admin PWA token is required."))
                    .header("WWW-Authenticate", "Bearer").build();
        }
        try {
            action.accept(actor.get());
            return Response.noContent().build();
        } catch (AccountProblem problem) {
            return error(problem.status, problem.code, problem.getMessage());
        }
    }

    private static Response error(int status, String code, String message) {
        return Response.status(status).entity(Json.createObjectBuilder()
                .add("error", code).add("message", message).build()).build();
    }
}
