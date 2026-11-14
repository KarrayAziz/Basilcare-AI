package tn.supcom.basilcare.services;

import jakarta.json.Json;
import org.junit.jupiter.api.Test;
import tn.supcom.basilcare.entities.Incident;

import java.time.Duration;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class IncidentServiceTest {

    private static final String DEVICE = "basil-sim-01";

    @Test
    void phAboveTheRangeOpensOneIncidentNotOnePerReading() {
        var w = new Fakes.World();
        w.online(DEVICE);
        for (int i = 0; i < 5; i++) {
            w.read(DEVICE, "ph", 7.2);
            w.clock.advance(Duration.ofSeconds(5));
        }
        assertEquals(1, w.store.unresolved("threshold"));
        assertEquals(1, w.notifier.raised.size());
        Incident incident = w.store.incident("threshold").orElseThrow();
        assertTrue(incident.getDetail().contains("above the maximum 6.5"), incident.getDetail());
        assertTrue(incident.getDetail().contains("not yet verified"), "seeded ranges are flagged");
    }

    @Test
    void conditionClearingKeepsTheIncidentForAPersonToResolve() {
        var w = new Fakes.World();
        w.online(DEVICE);
        w.read(DEVICE, "ph", 7.2);
        w.clock.advance(Duration.ofSeconds(5));
        w.read(DEVICE, "ph", 6.0);

        Incident incident = w.store.incident("threshold").orElseThrow();
        assertEquals(Incident.OPEN, incident.getStatus());
        assertFalse(incident.isActive());
        assertNotNull(incident.getClearedAt());
    }

    @Test
    void recurrenceReactivatesTheSameIncident() {
        var w = new Fakes.World();
        w.online(DEVICE);
        w.read(DEVICE, "ph", 7.2);
        w.clock.advance(Duration.ofSeconds(5));
        w.read(DEVICE, "ph", 6.0);
        w.clock.advance(Duration.ofSeconds(5));
        w.read(DEVICE, "ph", 7.4);

        assertEquals(1, w.store.incidents.size());
        Incident incident = w.store.incident("threshold").orElseThrow();
        assertEquals(2, incident.getOccurrences());
        assertTrue(incident.isActive());
        assertEquals(2, w.notifier.raised.size());
    }

    @Test
    void bufferedReadingNeverRaisesAnIncident() {
        var w = new Fakes.World();
        w.online(DEVICE);
        w.telemetry.ingestReading(Fakes.reading(DEVICE, "ph", 7.9, w.now(), true));
        assertEquals(0, w.store.incidents.size());
    }

    @Test
    void acknowledgeThenResolveRecordsWhoAndWhat() {
        var w = new Fakes.World();
        w.online(DEVICE);
        w.read(DEVICE, "water_level", 10);
        String id = w.store.incident("threshold").orElseThrow().getId();
        assertEquals(IncidentService.CRITICAL, w.store.incidents.get(id).getSeverity());

        w.incidents.acknowledge(id, "farmer1");
        assertEquals(Incident.ACKNOWLEDGED, w.store.incidents.get(id).getStatus());

        assertThrows(IllegalArgumentException.class, () -> w.incidents.resolve(id, "farmer1", " "));
        w.incidents.resolve(id, "farmer1", "Refilled the reservoir to 90 %.");
        Incident done = w.store.incidents.get(id);
        assertEquals(Incident.RESOLVED, done.getStatus());
        assertEquals("farmer1", done.getResolvedBy());
        assertEquals("Refilled the reservoir to 90 %.", done.getResolutionNote());
        assertThrows(IllegalStateException.class, () -> w.incidents.acknowledge(id, "farmer1"));
    }

    @Test
    void afterResolutionANewProblemOpensANewIncident() {
        var w = new Fakes.World();
        w.online(DEVICE);
        w.read(DEVICE, "ph", 7.2);
        String first = w.store.incident("threshold").orElseThrow().getId();
        w.incidents.resolve(first, "farmer1", "Adjusted pH down.");
        w.clock.advance(Duration.ofSeconds(5));
        w.read(DEVICE, "ph", 7.3);
        assertEquals(2, w.store.incidents.size());
    }

    @Test
    void lastWillOpensAnOfflineIncidentAndReconnectionClearsIt() {
        var w = new Fakes.World();
        w.online(DEVICE);
        w.telemetry.ingestStatus(Fakes.status(DEVICE, false, null));
        Incident offline = w.store.incident("offline").orElseThrow();
        assertTrue(offline.isActive());
        assertTrue(offline.getDetail().contains("Last Will"));

        w.clock.advance(Duration.ofSeconds(30));
        w.online(DEVICE);
        assertFalse(w.store.incident("offline").orElseThrow().isActive());
    }

    @Test
    void staleCheckFindsTheSilentSensorAndAFreshReadingClearsIt() {
        var w = new Fakes.World();
        w.online(DEVICE);
        w.read(DEVICE, "ph", 6.0);
        w.read(DEVICE, "ec", 1.4);
        w.clock.advance(Duration.ofSeconds(20));
        w.read(DEVICE, "ec", 1.4);   // ec keeps reporting, ph does not

        assertEquals(1, w.incidents.checkStale());
        Incident stale = w.store.incident("stale").orElseThrow();
        assertEquals("ph", stale.getSensor());

        w.read(DEVICE, "ph", 6.0);
        assertFalse(w.store.incident("stale").orElseThrow().isActive());
    }

    @Test
    void pumpFaultAndInvalidMessagesAreDeviceIncidents() {
        var w = new Fakes.World();
        w.pump.ingestPumpState(Json.createObjectBuilder()
                .add("device_id", DEVICE).add("state", "fault").addNull("until").addNull("command_id")
                .addNull("result").add("reason", "pump_fault").add("reported_at", w.now()).build());
        assertEquals(1, w.store.unresolved("pump_fault"));

        w.incidents.onInvalidMessage(DEVICE, "basilcare/v1/" + DEVICE + "/telemetry/ph", List.of("unit must be pH"));
        assertTrue(w.store.incident("invalid_message").orElseThrow().getDetail().contains("unit must be pH"));
    }

    @Test
    void onlyAConfidentGoodQualityScreeningRaisesALeafIncident() {
        var w = new Fakes.World();
        w.telemetry.ingestScreening(screening("img-1", "abnormal", 0.9, true));   // uncertain: no alert
        assertEquals(0, w.store.incidents.size());
        w.telemetry.ingestScreening(screening("img-2", "abnormal", 0.9, false));
        assertEquals(1, w.store.unresolved("leaf_anomaly"));
        w.telemetry.ingestScreening(screening("img-3", "healthy", 0.95, false));
        assertFalse(w.store.incident("leaf_anomaly").orElseThrow().isActive());
    }

    private static jakarta.json.JsonObject screening(String id, String label, double confidence, boolean review) {
        return Json.createObjectBuilder()
                .add("device_id", DEVICE).add("image_id", id).add("captured_at", "2026-11-04T14:05:00+01:00")
                .add("model_version", "test").add("label", label).add("confidence", confidence)
                .add("quality_ok", true).add("quality_issues", Json.createArrayBuilder())
                .add("review_required", review).build();
    }
}
