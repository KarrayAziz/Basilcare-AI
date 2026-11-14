package tn.supcom.basilcare.services;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import jakarta.json.JsonObject;
import jakarta.json.JsonString;
import jakarta.json.JsonValue;
import tn.supcom.basilcare.entities.DeviceState;
import tn.supcom.basilcare.entities.Reading;
import tn.supcom.basilcare.entities.ScreeningResult;
import tn.supcom.basilcare.repositories.TelemetryStore;

import java.time.Clock;
import java.time.Instant;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

/**
 * Stores the device messages forwarded by Node-RED and answers dashboard queries.
 * Applies the consumer rules of MQTT contract section 7: validation before storage,
 * duplicates ignored, buffered readings kept as history only, order by measured_at.
 */
@ApplicationScoped
public class TelemetryService {

    /** A sensor is stale when its last reading is older than this many telemetry intervals. */
    public static final int STALE_INTERVALS = 3;

    @Inject
    TelemetryStore store;

    @Inject
    Clock clock;

    @Inject
    IncidentService incidents;

    public TelemetryService() {
    }

    TelemetryService(TelemetryStore store, Clock clock, IncidentService incidents) {
        this.store = store;
        this.clock = clock;
        this.incidents = incidents;
    }

    // ---- ingestion ----------------------------------------------------------------

    public IngestResult ingestReading(JsonObject p) {
        List<String> errors = ContractValidator.telemetry(p);
        if (!errors.isEmpty()) {
            return IngestResult.invalid(errors);
        }
        OffsetDateTime measuredAt = Timestamps.parse(p.getString("measured_at")).orElseThrow();
        Reading reading = new Reading();
        reading.setDeviceId(p.getString("device_id"));
        reading.setSensor(p.getString("sensor"));
        reading.setValue(p.getJsonNumber("value").doubleValue());
        reading.setUnit(p.getString("unit"));
        reading.setMeasuredAt(p.getString("measured_at"));
        reading.setMeasuredAtEpoch(measuredAt.toInstant().toEpochMilli());
        reading.setCalibrated(p.getBoolean("calibrated"));
        reading.setSeq(p.getJsonNumber("seq").longValue());
        reading.setBuffered(p.getBoolean("buffered"));
        reading.setReceivedAt(Timestamps.now(clock));
        reading.setId(Reading.idOf(reading.getDeviceId(), reading.getSensor(), reading.getMeasuredAtEpoch()));

        // Compare with the live value BEFORE storing: only a newer, live reading may move it.
        Optional<Reading> previous = store.latestLive(reading.getDeviceId(), reading.getSensor());
        if (!store.insertReading(reading)) {
            return IngestResult.duplicate();
        }
        boolean newestLive = !reading.isBuffered()
                && previous.map(r -> r.getMeasuredAtEpoch() < reading.getMeasuredAtEpoch()).orElse(true);
        if (newestLive) {
            // A buffered or out-of-order reading describes the past: it must not open or
            // clear incidents about the present (scope section 2.3).
            incidents.onLiveReading(reading);
        }
        return IngestResult.stored();
    }

    public IngestResult ingestStatus(JsonObject p) {
        List<String> errors = ContractValidator.status(p);
        if (!errors.isEmpty()) {
            return IngestResult.invalid(errors);
        }
        Instant now = clock.instant();
        String deviceId = p.getString("device_id");
        DeviceState state = store.deviceState(deviceId).orElseGet(DeviceState::new);
        String reportedAt = p.isNull("reported_at") ? null : p.getString("reported_at");
        boolean online = p.getBoolean("online");
        // Retained replay of the message we already have: nothing new.
        if (deviceId.equals(state.getDeviceId()) && state.isOnline() == online
                && p.getString("started_at").equals(state.getStartedAt())
                && reportedAt != null && reportedAt.equals(state.getReportedAt())) {
            return IngestResult.duplicate();
        }
        state.setDeviceId(deviceId);
        state.setOnline(online);
        state.setStartedAt(p.getString("started_at"));
        state.setTelemetryIntervalS(p.getInt("telemetry_interval_s"));
        state.setSoftware(p.containsKey("software") && !p.isNull("software") ? p.getString("software") : null);
        state.setReportedAt(reportedAt);
        state.setReceivedAt(Timestamps.format(now, clock));
        state.setReceivedAtEpoch(now.toEpochMilli());
        store.saveDeviceState(state);
        incidents.onDeviceStatus(state);
        return IngestResult.stored();
    }

    public IngestResult ingestScreening(JsonObject p) {
        List<String> errors = ContractValidator.screening(p);
        if (!errors.isEmpty()) {
            return IngestResult.invalid(errors);
        }
        ScreeningResult result = new ScreeningResult();
        result.setImageId(p.getString("image_id"));
        result.setDeviceId(p.getString("device_id"));
        result.setCapturedAt(p.getString("captured_at"));
        result.setCapturedAtEpoch(Timestamps.parse(p.getString("captured_at")).orElseThrow().toInstant().toEpochMilli());
        result.setModelVersion(p.getString("model_version"));
        result.setLabel(p.getString("label"));
        result.setConfidence(p.getJsonNumber("confidence").doubleValue());
        result.setQualityOk(p.getBoolean("quality_ok"));
        List<String> issues = new ArrayList<>();
        for (JsonValue issue : p.getJsonArray("quality_issues")) {
            if (issue instanceof JsonString text) {
                issues.add(text.getString());
            }
        }
        result.setQualityIssues(issues);
        result.setReviewRequired(p.getBoolean("review_required"));
        result.setReceivedAt(Timestamps.now(clock));
        if (!store.insertScreening(result)) {
            return IngestResult.duplicate();
        }
        incidents.onScreening(result);
        return IngestResult.stored();
    }

    // ---- queries ------------------------------------------------------------------

    /** Live value of every sensor of a device, with its staleness. Buffered readings never appear here. */
    public List<LiveReading> latest(String deviceId) {
        Instant now = clock.instant();
        Optional<DeviceState> state = store.deviceState(deviceId);
        List<LiveReading> live = new ArrayList<>();
        for (SensorCatalog.Sensor sensor : SensorCatalog.all()) {
            store.latestLive(deviceId, sensor.name()).ifPresent(reading -> {
                long age = Math.max(0, (now.toEpochMilli() - reading.getMeasuredAtEpoch()) / 1000);
                live.add(LiveReading.of(reading, sensor.label(), age, isStale(state, age)));
            });
        }
        return live;
    }

    public List<Reading> history(String deviceId, String sensor, Instant from, Instant to, int limit) {
        return store.history(deviceId, sensor, from.toEpochMilli(), to.toEpochMilli(), limit);
    }

    public List<DeviceState> deviceStates() {
        return store.deviceStates();
    }

    public Optional<DeviceState> deviceState(String deviceId) {
        return store.deviceState(deviceId);
    }

    public List<ScreeningResult> screenings(String deviceId, int limit) {
        return store.screenings(deviceId, limit);
    }

    /** Stale only makes sense while the device says it is online; offline is its own incident. */
    static boolean isStale(Optional<DeviceState> state, long ageSeconds) {
        return state.filter(DeviceState::isOnline)
                .map(s -> ageSeconds > (long) STALE_INTERVALS * Math.max(1, s.getTelemetryIntervalS()))
                .orElse(false);
    }
}
