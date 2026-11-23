package tn.supcom.basilcare.boundaries;

import jakarta.inject.Inject;
import jakarta.json.Json;
import jakarta.json.JsonObject;
import jakarta.json.JsonString;
import jakarta.json.JsonValue;
import jakarta.ws.rs.Consumes;
import jakarta.ws.rs.POST;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;
import tn.supcom.basilcare.security.IngestKeyRequired;
import tn.supcom.basilcare.services.ContractValidator;
import tn.supcom.basilcare.services.IncidentService;
import tn.supcom.basilcare.services.IngestResult;
import tn.supcom.basilcare.services.LiveFrameStore;
import tn.supcom.basilcare.services.PumpService;
import tn.supcom.basilcare.services.TelemetryService;

import java.util.ArrayList;
import java.util.List;
import java.util.logging.Logger;

/**
 * Entry point of device data, called by the Node-RED ingestion flow only (X-Ingest-Key).
 * The bodies are the MQTT payloads of docs/mqtt-contract.md, unchanged.
 *
 * Answers: 201 stored, 200 duplicate or outdated (ignored, contract section 7), 422 invalid.
 */
@Path("ingest")
@IngestKeyRequired
@Consumes(MediaType.APPLICATION_JSON)
@Produces(MediaType.APPLICATION_JSON)
public class IngestResource {

    private static final Logger LOG = Logger.getLogger(IngestResource.class.getName());

    @Inject
    TelemetryService telemetry;

    @Inject
    PumpService pump;

    @Inject
    IncidentService incidents;

    @Inject
    LiveFrameStore frames;

    @POST
    @Path("telemetry")
    public Response telemetry(JsonObject payload) {
        return answer(telemetry.ingestReading(payload));
    }

    @POST
    @Path("status")
    public Response status(JsonObject payload) {
        return answer(telemetry.ingestStatus(payload));
    }

    @POST
    @Path("pump-state")
    public Response pumpState(JsonObject payload) {
        return answer(pump.ingestPumpState(payload));
    }

    @POST
    @Path("screening")
    public Response screening(JsonObject payload) {
        return answer(telemetry.ingestScreening(payload));
    }

    /** Live camera frame (contract section 6a): kept in memory only, replaces the previous one. */
    @POST
    @Path("camera")
    public Response camera(JsonObject payload) {
        return answer(frames.accept(payload));
    }

    /**
     * A message Node-RED rejected: {"topic": "...", "errors": ["..."]}.
     * It is never stored as data, but it raises a device incident (contract section 7).
     */
    @POST
    @Path("invalid")
    public Response invalid(JsonObject body) {
        if (body == null || body.get("topic") == null || body.get("topic").getValueType() != JsonValue.ValueType.STRING) {
            return Problems.of(Response.Status.BAD_REQUEST, "invalid_body", "topic is required.");
        }
        String topic = body.getString("topic");
        String[] parts = topic.split("/");
        if (parts.length < 3 || !ContractValidator.DEVICE_ID.matcher(parts[2]).matches()) {
            LOG.warning(() -> "invalid message on an unattributable topic: " + topic);
            return Response.accepted(Json.createObjectBuilder().add("incident", false).build()).build();
        }
        List<String> errors = new ArrayList<>();
        if (body.get("errors") != null && body.get("errors").getValueType() == JsonValue.ValueType.ARRAY) {
            body.getJsonArray("errors").forEach(e -> {
                if (e instanceof JsonString text) {
                    errors.add(text.getString());
                }
            });
        }
        incidents.onInvalidMessage(parts[2], topic, errors.isEmpty() ? List.of("invalid message") : errors);
        return Response.accepted(Json.createObjectBuilder().add("incident", true).build()).build();
    }

    private static Response answer(IngestResult result) {
        return switch (result.outcome()) {
            case STORED -> Response.status(Response.Status.CREATED)
                    .entity(Json.createObjectBuilder().add("stored", true).build()).build();
            case DUPLICATE -> Response.ok(Json.createObjectBuilder()
                    .add("stored", false).add("duplicate", true).build()).build();
            case OUTDATED -> Response.ok(Json.createObjectBuilder()
                    .add("stored", false).add("outdated", true).build()).build();
            case INVALID -> Problems.invalid("invalid_message", result.errors());
        };
    }
}
