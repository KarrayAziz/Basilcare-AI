package tn.supcom.basilcare.services;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import jakarta.json.Json;
import jakarta.json.JsonObject;
import jakarta.json.JsonObjectBuilder;
import org.eclipse.microprofile.config.inject.ConfigProperty;
import tn.supcom.basilcare.entities.PumpCommand;
import tn.supcom.basilcare.entities.PumpStatus;
import tn.supcom.basilcare.repositories.PumpStore;
import tn.supcom.basilcare.repositories.TelemetryStore;

import java.time.Clock;
import java.time.Instant;
import java.util.List;
import java.util.Objects;
import java.util.Optional;
import java.util.UUID;
import java.util.logging.Logger;

/**
 * Pump control (contract section 5): role check (in PumpResource), user confirmation,
 * deterministic safety policy, audit record, then pump/cmd. The device's answer on
 * pump/state is added to the same audit record.
 */
@ApplicationScoped
public class PumpService {

    private static final Logger LOG = Logger.getLogger(PumpService.class.getName());

    /** Thrown when the caller did not confirm: nothing is recorded, nothing is sent. */
    public static class ConfirmationRequired extends RuntimeException {
        public ConfirmationRequired() {
            super("Confirm the action: send \"confirm\": true after the user agreed.");
        }
    }

    public record Requester(String username, String role, String clientId) {
    }

    @Inject
    PumpStore store;

    @Inject
    TelemetryStore telemetry;

    @Inject
    CommandPublisher publisher;

    @Inject
    IncidentService incidents;

    @Inject
    Clock clock;

    @Inject
    @ConfigProperty(name = "pump.max.duration.s", defaultValue = "900")
    int maxDurationS;

    @Inject
    @ConfigProperty(name = "pump.min.water.level", defaultValue = "20")
    double minWaterLevel;

    @Inject
    @ConfigProperty(name = "pump.command.ttl.s", defaultValue = "60")
    int commandTtlS;

    public PumpService() {
    }

    PumpService(PumpStore store, TelemetryStore telemetry, CommandPublisher publisher, IncidentService incidents,
                Clock clock, PumpSafetyPolicy.Limits limits) {
        this.store = store;
        this.telemetry = telemetry;
        this.publisher = publisher;
        this.incidents = incidents;
        this.clock = clock;
        this.maxDurationS = limits.maxDurationS();
        this.minWaterLevel = limits.minWaterLevel();
        this.commandTtlS = limits.commandTtlS();
    }

    /**
     * Handles one request. Returns the audit record: decision "accepted" (sent to the device)
     * or "rejected" (with the reason). Invalid input throws IllegalArgumentException and an
     * unconfirmed request throws ConfirmationRequired; neither is recorded.
     */
    public PumpCommand request(String deviceId, String action, Integer durationS, boolean confirmed,
                               Requester requester) {
        if (deviceId == null || !ContractValidator.DEVICE_ID.matcher(deviceId).matches()) {
            throw new IllegalArgumentException("Invalid device id.");
        }
        if (!"on".equals(action) && !"off".equals(action)) {
            throw new IllegalArgumentException("action must be \"on\" or \"off\".");
        }
        if ("on".equals(action) && (durationS == null || durationS < 1)) {
            throw new IllegalArgumentException("duration_s must be a positive number of seconds for \"on\".");
        }
        if (!confirmed) {
            throw new ConfirmationRequired();
        }
        Integer duration = "on".equals(action) ? durationS : null;
        long now = clock.millis();
        var facts = new PumpSafetyPolicy.Facts(
                store.device(deviceId),
                telemetry.deviceState(deviceId),
                store.pumpStatus(deviceId),
                telemetry.latestLive(deviceId, "water_level"),
                now);
        var limits = new PumpSafetyPolicy.Limits(maxDurationS, minWaterLevel, commandTtlS);
        var decision = PumpSafetyPolicy.evaluate(action, duration, facts, limits);

        PumpCommand command = new PumpCommand();
        command.setCommandId(UUID.randomUUID().toString());
        command.setDeviceId(deviceId);
        command.setAction(action);
        command.setDurationS(duration);
        command.setRequestedBy(requester.username());
        command.setRequesterRole(requester.role());
        command.setClientId(requester.clientId());
        command.setRequestedAt(Timestamps.format(Instant.ofEpochMilli(now), clock));
        command.setRequestedAtEpoch(now);
        command.setExpiresAt(Timestamps.format(Instant.ofEpochMilli(now + 1000L * commandTtlS), clock));
        command.setDecision(decision.accepted() ? PumpCommand.ACCEPTED : PumpCommand.REJECTED);
        command.setDecisionReason(decision.reason());
        command.setPublished(decision.accepted());
        // Audit first: an action that reaches the device must always have its record.
        store.saveCommand(command);
        if (!decision.accepted()) {
            LOG.info(() -> "pump request rejected: " + deviceId + " " + action + " by " + requester.username()
                    + " (" + decision.reason() + ")");
            return command;
        }
        try {
            publisher.publish("basilcare/v1/" + deviceId + "/pump/cmd", payload(command).toString());
        } catch (CommandPublisher.PublishException e) {
            command.setDecision(PumpCommand.REJECTED);
            command.setDecisionReason("broker_unavailable");
            command.setPublished(false);
            store.saveCommand(command);
            LOG.warning(() -> "pump command not sent: " + e.getMessage());
        }
        return command;
    }

    /** pump/state forwarded by Node-RED: updates the current state and completes the audit record. */
    public IngestResult ingestPumpState(JsonObject p) {
        List<String> errors = ContractValidator.pumpState(p);
        if (!errors.isEmpty()) {
            return IngestResult.invalid(errors);
        }
        String deviceId = p.getString("device_id");
        String commandId = text(p, "command_id");
        String reportedAt = p.getString("reported_at");
        Optional<PumpStatus> previous = store.pumpStatus(deviceId);
        // Retained replay or QoS 1 redelivery: identical in EVERY field. Timestamps have second
        // precision, so two genuine answers (e.g. to an "on" then an "off") can share the same
        // reported_at and state; only the command they answer tells them apart (review finding #5).
        if (previous.map(s -> reportedAt.equals(s.getReportedAt())
                && p.getString("state").equals(s.getState())
                && Objects.equals(commandId, s.getCommandId())
                && Objects.equals(text(p, "result"), s.getResult())
                && Objects.equals(text(p, "reason"), s.getReason())).orElse(false)) {
            return IngestResult.duplicate();
        }
        PumpStatus status = new PumpStatus();
        status.setDeviceId(deviceId);
        status.setState(p.getString("state"));
        status.setUntil(text(p, "until"));
        status.setCommandId(commandId);
        status.setResult(text(p, "result"));
        status.setReason(text(p, "reason"));
        status.setReportedAt(reportedAt);
        status.setReceivedAt(Timestamps.now(clock));
        store.savePumpStatus(status);

        if (commandId != null) {
            store.command(commandId)
                    .filter(c -> deviceId.equals(c.getDeviceId()) && c.getDeviceResult() == null)
                    .ifPresent(c -> {
                        c.setDeviceResult(status.getResult());
                        c.setDeviceReason(status.getReason());
                        c.setDeviceReportedAt(reportedAt);
                        store.saveCommand(c);
                    });
        }
        incidents.onPumpStatus(status);
        return IngestResult.stored();
    }

    public Optional<PumpStatus> status(String deviceId) {
        return store.pumpStatus(deviceId);
    }

    public List<PumpCommand> commands(String deviceId, int limit) {
        return store.commands(deviceId, limit);
    }

    public PumpSafetyPolicy.Limits limits() {
        return new PumpSafetyPolicy.Limits(maxDurationS, minWaterLevel, commandTtlS);
    }

    /** pump/cmd payload of contract section 5.1. */
    static JsonObject payload(PumpCommand command) {
        JsonObjectBuilder json = Json.createObjectBuilder()
                .add("device_id", command.getDeviceId())
                .add("command_id", command.getCommandId())
                .add("action", command.getAction());
        if (command.getDurationS() != null) {
            json.add("duration_s", command.getDurationS());
        }
        return json.add("requested_by", command.getRequestedBy())
                .add("requested_at", command.getRequestedAt())
                .add("expires_at", command.getExpiresAt())
                .build();
    }

    private static String text(JsonObject p, String field) {
        return p.containsKey(field) && !p.isNull(field) ? p.getString(field) : null;
    }
}
