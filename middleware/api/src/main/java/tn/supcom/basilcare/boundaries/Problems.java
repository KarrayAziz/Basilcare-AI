package tn.supcom.basilcare.boundaries;

import jakarta.json.Json;
import jakarta.json.JsonArrayBuilder;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;

import java.util.List;

/** Error bodies shared by the resources: {"error": "code", "message": "...", "details": [...]}. */
final class Problems {

    private Problems() {
    }

    static Response of(Response.Status status, String code, String message) {
        return Response.status(status)
                .type(MediaType.APPLICATION_JSON)
                .entity(Json.createObjectBuilder().add("error", code).add("message", message).build())
                .build();
    }

    static Response of(int status, String code, String message) {
        return Response.status(status)
                .type(MediaType.APPLICATION_JSON)
                .entity(Json.createObjectBuilder().add("error", code).add("message", message).build())
                .build();
    }

    static Response invalid(String code, List<String> details) {
        JsonArrayBuilder list = Json.createArrayBuilder();
        details.forEach(list::add);
        return Response.status(422)
                .type(MediaType.APPLICATION_JSON)
                .entity(Json.createObjectBuilder()
                        .add("error", code)
                        .add("message", "The message does not follow the MQTT contract.")
                        .add("details", list)
                        .build())
                .build();
    }
}
