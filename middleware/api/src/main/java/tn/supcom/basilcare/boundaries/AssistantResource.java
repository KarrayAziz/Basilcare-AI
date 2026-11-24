package tn.supcom.basilcare.boundaries;

import jakarta.annotation.security.RolesAllowed;
import jakarta.inject.Inject;
import jakarta.json.Json;
import jakarta.json.JsonObject;
import jakarta.ws.rs.*;
import jakarta.ws.rs.core.*;
import java.io.InputStream;
import java.io.ByteArrayInputStream;
import tn.supcom.basilcare.security.Secured;
import tn.supcom.basilcare.services.AssistantClient;
import tn.supcom.basilcare.services.AssistantLimits;

@Path("assistant")
@Secured
@RolesAllowed({"Farmer", "Admin"})
@Produces(MediaType.APPLICATION_JSON)
public class AssistantResource {
    @Inject AssistantClient assistant;
    @Inject AssistantLimits limits;

    @POST
    @Path("ask")
    @Consumes(MediaType.APPLICATION_JSON)
    public Response ask(InputStream input, @Context SecurityContext security) {
        // The filter normally enforces this; keep direct calls fail-closed too.
        if (security == null || security.getUserPrincipal() == null) return problem(401, "unauthorized", "Sign in to ask a question.");
        if (!security.isUserInRole("Farmer") && !security.isUserInRole("Admin")) return problem(403, "forbidden", "This account cannot use the assistant.");
        String question;
        try {
            byte[] raw = input == null ? new byte[0] : input.readNBytes(16385);
            if (raw.length > 16384) return problem(413, "too_large", "Question is too large.");
            JsonObject body = Json.createReader(new ByteArrayInputStream(raw)).readObject();
            question = body.getString("question").strip();
            if (!body.keySet().equals(java.util.Set.of("question")) || question.isEmpty() || question.length() > 2000) throw new IllegalArgumentException();
        } catch (Exception e) {
            return problem(400, "invalid_question", "Enter a question between 1 and 2000 characters.");
        }
        if (!limits.allow(security.getUserPrincipal().getName(), System.currentTimeMillis())) {
            return Response.status(429).header("Retry-After", "60").header("Cache-Control", "no-store")
                    .entity(Json.createObjectBuilder().add("message", "Too many questions. Wait a minute and try again.").build()).build();
        }
        if (!limits.acquire()) return problem(503, "assistant_busy", "The assistant is busy. Try again shortly.");
        try {
            return Response.ok(assistant.ask(question)).header("Cache-Control", "no-store").build();
        } catch (AssistantClient.Unavailable e) {
            return problem(503, "assistant_unavailable", "The assistant is temporarily unavailable. Try again later or ask an administrator to check its configuration and quota.");
        } finally {
            limits.release();
        }
    }

    private static Response problem(int status, String code, String message) {
        return Response.status(status).header("Cache-Control", "no-store")
                .entity(Json.createObjectBuilder().add("error", code).add("message", message).build()).build();
    }
}
