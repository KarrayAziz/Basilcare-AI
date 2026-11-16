package tn.supcom.basilcare.services;

import jakarta.json.Json;
import jakarta.json.JsonObject;
import jakarta.json.JsonObjectBuilder;
import tn.supcom.basilcare.entities.Device;
import tn.supcom.basilcare.entities.DeviceState;
import tn.supcom.basilcare.entities.Incident;
import tn.supcom.basilcare.entities.PumpCommand;
import tn.supcom.basilcare.entities.PumpStatus;
import tn.supcom.basilcare.entities.Reading;
import tn.supcom.basilcare.entities.ScreeningResult;
import tn.supcom.basilcare.entities.Threshold;
import tn.supcom.basilcare.repositories.IncidentStore;
import tn.supcom.basilcare.repositories.PumpStore;
import tn.supcom.basilcare.repositories.TelemetryStore;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneId;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.Collection;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

/** In-memory test doubles: the services are tested without MongoDB, WildFly or a broker. */
final class Fakes {

    static final ZoneOffset TUNIS = ZoneOffset.ofHours(1);
    static final Instant T0 = Instant.parse("2026-11-04T13:05:00Z");   // 14:05:00+01:00

    private Fakes() {
    }

    /** A clock the test moves forward by hand. */
    static final class MutableClock extends Clock {
        private Instant now;

        MutableClock(Instant start) {
            this.now = start;
        }

        void advance(Duration duration) {
            now = now.plus(duration);
        }

        @Override
        public ZoneId getZone() {
            return TUNIS;
        }

        @Override
        public Clock withZone(ZoneId zone) {
            return this;
        }

        @Override
        public Instant instant() {
            return now;
        }
    }

    static final class Store implements TelemetryStore, IncidentStore, PumpStore {
        final Map<String, Reading> readings = new LinkedHashMap<>();
        final Map<String, DeviceState> states = new LinkedHashMap<>();
        final Map<String, ScreeningResult> screenings = new LinkedHashMap<>();
        final Map<String, Incident> incidents = new LinkedHashMap<>();
        final Map<String, Threshold> thresholds = new LinkedHashMap<>();
        final Map<String, Device> devices = new LinkedHashMap<>();
        final Map<String, PumpStatus> pumps = new LinkedHashMap<>();
        final Map<String, PumpCommand> commands = new LinkedHashMap<>();

        @Override
        public boolean insertReading(Reading reading) {
            return readings.putIfAbsent(reading.getId(), reading) == null;
        }

        @Override
        public Optional<Reading> latestLive(String deviceId, String sensor) {
            return readings.values().stream()
                    .filter(r -> r.getDeviceId().equals(deviceId) && r.getSensor().equals(sensor) && !r.isBuffered())
                    .max(Comparator.comparingLong(Reading::getMeasuredAtEpoch));
        }

        @Override
        public List<Reading> history(String deviceId, String sensor, long fromEpoch, long toEpoch, int limit) {
            return readings.values().stream()
                    .filter(r -> r.getDeviceId().equals(deviceId) && r.getSensor().equals(sensor))
                    .filter(r -> r.getMeasuredAtEpoch() >= fromEpoch && r.getMeasuredAtEpoch() <= toEpoch)
                    .sorted(Comparator.comparingLong(Reading::getMeasuredAtEpoch))
                    .limit(limit).toList();
        }

        @Override
        public Optional<DeviceState> deviceState(String deviceId) {
            return Optional.ofNullable(states.get(deviceId));
        }

        @Override
        public List<DeviceState> deviceStates() {
            return new ArrayList<>(states.values());
        }

        @Override
        public void saveDeviceState(DeviceState state) {
            states.put(state.getDeviceId(), state);
        }

        @Override
        public boolean insertScreening(ScreeningResult result) {
            return screenings.putIfAbsent(result.getImageId(), result) == null;
        }

        @Override
        public List<ScreeningResult> screenings(String deviceId, int limit) {
            return screenings.values().stream()
                    .filter(s -> deviceId == null || s.getDeviceId().equals(deviceId)).limit(limit).toList();
        }

        @Override
        public Optional<Incident> findUnresolved(String key) {
            return incidents.values().stream()
                    .filter(i -> i.getKey().equals(key) && !Incident.RESOLVED.equals(i.getStatus())).findFirst();
        }

        @Override
        public Optional<Incident> find(String id) {
            return Optional.ofNullable(incidents.get(id));
        }

        @Override
        public void save(Incident incident) {
            incidents.put(incident.getId(), incident);
        }

        @Override
        public List<Incident> list(String deviceId, Collection<String> statuses, int limit) {
            return incidents.values().stream()
                    .filter(i -> deviceId == null || i.getDeviceId().equals(deviceId))
                    .filter(i -> statuses.isEmpty() || statuses.contains(i.getStatus()))
                    .limit(limit).toList();
        }

        @Override
        public Optional<Threshold> threshold(String sensor) {
            return Optional.ofNullable(thresholds.get(sensor));
        }

        @Override
        public List<Threshold> thresholds() {
            return new ArrayList<>(thresholds.values());
        }

        @Override
        public void saveThreshold(Threshold threshold) {
            thresholds.put(threshold.getSensor(), threshold);
        }

        @Override
        public Optional<Device> device(String deviceId) {
            return Optional.ofNullable(devices.get(deviceId));
        }

        @Override
        public Optional<PumpStatus> pumpStatus(String deviceId) {
            return Optional.ofNullable(pumps.get(deviceId));
        }

        @Override
        public void savePumpStatus(PumpStatus status) {
            pumps.put(status.getDeviceId(), status);
        }

        @Override
        public Optional<PumpCommand> command(String commandId) {
            return Optional.ofNullable(commands.get(commandId));
        }

        @Override
        public void saveCommand(PumpCommand command) {
            commands.put(command.getCommandId(), command);
        }

        @Override
        public List<PumpCommand> commands(String deviceId, int limit) {
            return commands.values().stream()
                    .filter(c -> deviceId == null || c.getDeviceId().equals(deviceId)).limit(limit).toList();
        }

        long unresolved(String type) {
            return incidents.values().stream()
                    .filter(i -> i.getType().equals(type) && !Incident.RESOLVED.equals(i.getStatus())).count();
        }

        Optional<Incident> incident(String type) {
            return incidents.values().stream().filter(i -> i.getType().equals(type)).findFirst();
        }
    }

    static final class RecordingNotifier implements Notifier {
        final List<Incident> raised = new ArrayList<>();

        @Override
        public void incidentRaised(Incident incident) {
            raised.add(incident);
        }
    }

    static final class RecordingPublisher implements CommandPublisher {
        final List<String[]> sent = new ArrayList<>();
        boolean fail;

        @Override
        public void publish(String topic, String json) throws PublishException {
            if (fail) {
                throw new PublishException("broker down", null);
            }
            sent.add(new String[]{topic, json});
        }
    }

    /** Everything wired together, like CDI does in WildFly. */
    static final class World {
        final MutableClock clock = new MutableClock(T0);
        final Store store = new Store();
        final RecordingNotifier notifier = new RecordingNotifier();
        final RecordingPublisher publisher = new RecordingPublisher();
        final IncidentService incidents = new IncidentService(store, store, notifier, clock);
        final TelemetryService telemetry = new TelemetryService(store, clock, incidents);
        final ThresholdService thresholds = new ThresholdService(store, clock);
        final PumpService pump = new PumpService(store, store, publisher, incidents, clock,
                new PumpSafetyPolicy.Limits(900, 20, 60));

        World() {
            thresholds.seedDefaults();
        }

        String now() {
            return Timestamps.format(clock.instant().atOffset(TUNIS));
        }

        void online(String deviceId) {
            telemetry.ingestStatus(status(deviceId, true, now()));
        }

        void register(String deviceId) {
            Device device = new Device();
            device.setDeviceId(deviceId);
            device.setName("Test gateway");
            device.setEnabled(true);
            store.devices.put(deviceId, device);
        }

        IngestResult read(String deviceId, String sensor, double value) {
            return telemetry.ingestReading(reading(deviceId, sensor, value, now(), false));
        }
    }

    static JsonObject reading(String deviceId, String sensor, double value, String measuredAt, boolean buffered) {
        String unit = SensorCatalog.find(sensor).map(SensorCatalog.Sensor::unit).orElse("?");
        return Json.createObjectBuilder()
                .add("device_id", deviceId).add("sensor", sensor).add("value", value).add("unit", unit)
                .add("measured_at", measuredAt).add("calibrated", true).add("seq", 1).add("buffered", buffered)
                .build();
    }

    static JsonObject status(String deviceId, boolean online, String reportedAt) {
        JsonObjectBuilder json = Json.createObjectBuilder()
                .add("device_id", deviceId).add("online", online)
                .add("started_at", "2026-11-04T08:00:00+01:00").add("telemetry_interval_s", 5)
                .add("software", "test");
        if (reportedAt == null) {
            json.addNull("reported_at");
        } else {
            json.add("reported_at", reportedAt);
        }
        return json.build();
    }
}
