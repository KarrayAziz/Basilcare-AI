package tn.supcom.basilcare.services;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import tn.supcom.basilcare.entities.DeviceState;
import tn.supcom.basilcare.entities.Incident;
import tn.supcom.basilcare.entities.PumpStatus;
import tn.supcom.basilcare.entities.Reading;
import tn.supcom.basilcare.entities.ScreeningResult;
import tn.supcom.basilcare.entities.Threshold;
import tn.supcom.basilcare.repositories.IncidentStore;
import tn.supcom.basilcare.repositories.TelemetryStore;

import java.time.Clock;
import java.time.Instant;
import java.util.Collection;
import java.util.List;
import java.util.Locale;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;

/**
 * Turns device messages into incidents (FR-03) and records how people handle them (FR-04).
 *
 * Incident types:
 * <ul>
 *   <li>threshold: a live reading outside the administrator's alert range</li>
 *   <li>stale: an online device stopped sending one sensor (3 x telemetry interval)</li>
 *   <li>offline: the device said goodbye, or the broker published its Last Will</li>
 *   <li>pump_fault: the device put the pump in fault</li>
 *   <li>invalid_message: the device sent something that breaks the MQTT contract (sensor or software fault)</li>
 *   <li>leaf_anomaly: a confident, good-quality screening that is not "healthy" (never a diagnosis)</li>
 * </ul>
 */
@ApplicationScoped
public class IncidentService {

    public static final String WARNING = "warning";
    public static final String CRITICAL = "critical";
    private static final Set<String> NOT_ANOMALIES = Set.of("healthy", "unknown");

    @Inject
    IncidentStore store;

    @Inject
    TelemetryStore telemetry;

    @Inject
    Notifier notifier;

    @Inject
    Clock clock;

    public IncidentService() {
    }

    IncidentService(IncidentStore store, TelemetryStore telemetry, Notifier notifier, Clock clock) {
        this.store = store;
        this.telemetry = telemetry;
        this.notifier = notifier;
        this.clock = clock;
    }

    // ---- rules fed by the ingestion ---------------------------------------------------

    /** Called for the newest live reading of a sensor only (never for buffered history). */
    public void onLiveReading(Reading reading) {
        String deviceId = reading.getDeviceId();
        String sensor = reading.getSensor();
        // A fresh reading always ends staleness.
        clear(Incident.keyOf(deviceId, "stale", sensor));

        Optional<Threshold> threshold = store.threshold(sensor).filter(Threshold::isEnabled);
        if (threshold.isEmpty()) {
            return;
        }
        Threshold t = threshold.get();
        String label = SensorCatalog.find(sensor).map(SensorCatalog.Sensor::label).orElse(sensor);
        String value = format(reading.getValue()) + " " + reading.getUnit();
        String problem = null;
        if (t.getMin() != null && reading.getValue() < t.getMin()) {
            problem = value + " is below the minimum " + format(t.getMin());
        } else if (t.getMax() != null && reading.getValue() > t.getMax()) {
            problem = value + " is above the maximum " + format(t.getMax());
        }
        String key = Incident.keyOf(deviceId, "threshold", sensor);
        if (problem == null) {
            clear(key);
            return;
        }
        if (!t.isVerified()) {
            problem += " (alert range not yet verified)";
        }
        if (!reading.isCalibrated()) {
            problem += "; the probe is not calibrated, check it before acting";
        }
        raise(deviceId, "threshold", sensor, t.getSeverity() == null ? WARNING : t.getSeverity(),
                label + " out of range", problem, reading.getValue());
    }

    public void onDeviceStatus(DeviceState state) {
        String key = Incident.keyOf(state.getDeviceId(), "offline", null);
        if (state.isOnline()) {
            clear(key);
        } else {
            String how = state.getReportedAt() == null
                    ? "Connection lost: the broker published the device's Last Will."
                    : "The device disconnected cleanly.";
            raise(state.getDeviceId(), "offline", null, CRITICAL, "Device offline",
                    how + " Pump safety stays enforced on the device.", null);
        }
    }

    public void onPumpStatus(PumpStatus status) {
        String key = Incident.keyOf(status.getDeviceId(), "pump_fault", null);
        if ("fault".equals(status.getState())) {
            raise(status.getDeviceId(), "pump_fault", null, CRITICAL, "Pump fault",
                    "The device stopped the pump after detecting a failure. Maintenance is needed on the device.",
                    null);
        } else {
            clear(key);
        }
    }

    public void onScreening(ScreeningResult result) {
        String key = Incident.keyOf(result.getDeviceId(), "leaf_anomaly", null);
        if (result.isReviewRequired()) {
            return;   // uncertain or poor image: shown as "review required", not an alert
        }
        if (NOT_ANOMALIES.contains(result.getLabel().toLowerCase(Locale.ROOT))) {
            clear(key);
            return;
        }
        raise(result.getDeviceId(), "leaf_anomaly", null, WARNING, "Visible leaf abnormality",
                "Screening " + result.getImageId() + " says '" + result.getLabel() + "' (confidence "
                        + Math.round(result.getConfidence() * 100) + " %, model " + result.getModelVersion()
                        + "). This is a screening, not a diagnosis: inspect the plant.",
                result.getConfidence());
    }

    public void onInvalidMessage(String deviceId, String topic, List<String> errors) {
        raise(deviceId, "invalid_message", null, WARNING, "Invalid message from device",
                topic + ": " + String.join("; ", errors) + ". Possible sensor, wiring or software fault.", null);
    }

    /** Periodic check (StaleWatcher): sensors of online devices that stopped reporting. */
    public int checkStale() {
        int stale = 0;
        long now = clock.millis();
        for (DeviceState state : telemetry.deviceStates()) {
            if (!state.isOnline()) {
                continue;
            }
            long limitMs = 1000L * TelemetryService.STALE_INTERVALS * Math.max(1, state.getTelemetryIntervalS());
            for (SensorCatalog.Sensor sensor : SensorCatalog.all()) {
                Optional<Reading> last = telemetry.latestLive(state.getDeviceId(), sensor.name());
                if (last.isEmpty()) {
                    continue;   // a sensor this device never had
                }
                long ageMs = now - last.get().getMeasuredAtEpoch();
                // the device restarted after this reading: give it one full window to report again
                long sinceStatusMs = now - state.getReceivedAtEpoch();
                if (ageMs > limitMs && sinceStatusMs > limitMs) {
                    stale++;
                    raise(state.getDeviceId(), "stale", sensor.name(), WARNING, sensor.label() + " not reporting",
                            "No reading for " + (ageMs / 1000) + " s while the device is online (expected every "
                                    + state.getTelemetryIntervalS() + " s).", null);
                }
            }
        }
        return stale;
    }

    // ---- actions of people --------------------------------------------------------------

    public List<Incident> list(String deviceId, Collection<String> statuses, int limit) {
        return store.list(deviceId, statuses, limit);
    }

    public Optional<Incident> find(String id) {
        return store.find(id);
    }

    /** @throws IllegalStateException when the incident is already resolved */
    public Optional<Incident> acknowledge(String id, String user) {
        Optional<Incident> found = store.find(id);
        found.ifPresent(incident -> {
            if (Incident.RESOLVED.equals(incident.getStatus())) {
                throw new IllegalStateException("The incident is already resolved.");
            }
            if (Incident.OPEN.equals(incident.getStatus())) {
                incident.setStatus(Incident.ACKNOWLEDGED);
                incident.setAcknowledgedBy(user);
                incident.setAcknowledgedAt(now());
                store.save(incident);
            }
        });
        return found;
    }

    /** @throws IllegalStateException when already resolved; IllegalArgumentException for a bad note */
    public Optional<Incident> resolve(String id, String user, String note) {
        String cleaned = note == null ? null : note.trim();
        if (cleaned == null || cleaned.length() < 3 || cleaned.length() > 500) {
            throw new IllegalArgumentException("Describe what was done: a note of 3 to 500 characters is required.");
        }
        Optional<Incident> found = store.find(id);
        found.ifPresent(incident -> {
            if (Incident.RESOLVED.equals(incident.getStatus())) {
                throw new IllegalStateException("The incident is already resolved.");
            }
            String now = now();
            if (incident.getAcknowledgedAt() == null) {   // resolving implies having seen it
                incident.setAcknowledgedBy(user);
                incident.setAcknowledgedAt(now);
            }
            incident.setStatus(Incident.RESOLVED);
            incident.setResolvedBy(user);
            incident.setResolvedAt(now);
            incident.setResolutionNote(cleaned);
            store.save(incident);
        });
        return found;
    }

    // ---- core -----------------------------------------------------------------------------

    void raise(String deviceId, String type, String sensor, String severity, String title, String detail,
               Double value) {
        String key = Incident.keyOf(deviceId, type, sensor);
        String now = now();
        Optional<Incident> existing = store.findUnresolved(key);
        if (existing.isPresent()) {
            Incident incident = existing.get();
            boolean reactivated = !incident.isActive();
            if (reactivated) {
                incident.setOccurrences(incident.getOccurrences() + 1);
                incident.setActive(true);
                incident.setClearedAt(null);
            }
            incident.setDetail(detail);
            incident.setSeverity(severity);
            incident.setLastValue(value);
            incident.setLastSeenAt(now);
            store.save(incident);
            if (reactivated) {
                notifier.incidentRaised(incident);
            }
            return;
        }
        Incident incident = new Incident();
        incident.setId(UUID.randomUUID().toString());
        incident.setKey(key);
        incident.setDeviceId(deviceId);
        incident.setType(type);
        incident.setSensor(sensor);
        incident.setSeverity(severity);
        incident.setTitle(title);
        incident.setDetail(detail);
        incident.setLastValue(value);
        incident.setStatus(Incident.OPEN);
        incident.setActive(true);
        incident.setOccurrences(1);
        incident.setOpenedAt(now);
        incident.setOpenedAtEpoch(clock.millis());
        incident.setLastSeenAt(now);
        store.save(incident);
        notifier.incidentRaised(incident);
    }

    void clear(String key) {
        store.findUnresolved(key).filter(Incident::isActive).ifPresent(incident -> {
            incident.setActive(false);
            incident.setClearedAt(now());
            store.save(incident);
        });
    }

    private String now() {
        return Timestamps.now(clock);
    }

    private static String format(double value) {
        return String.format(Locale.ROOT, "%.2f", value).replaceAll("\\.?0+$", "");
    }
}
