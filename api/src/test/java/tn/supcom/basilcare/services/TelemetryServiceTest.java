package tn.supcom.basilcare.services;

import org.junit.jupiter.api.Test;

import java.time.Duration;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class TelemetryServiceTest {

    private static final String DEVICE = "basil-sim-01";

    @Test
    void storesAReadingOnceAndIgnoresTheQos1Duplicate() {
        var w = new Fakes.World();
        var reading = Fakes.reading(DEVICE, "ph", 6.0, w.now(), false);
        assertEquals(IngestResult.Outcome.STORED, w.telemetry.ingestReading(reading).outcome());
        assertEquals(IngestResult.Outcome.DUPLICATE, w.telemetry.ingestReading(reading).outcome());
        assertEquals(1, w.store.readings.size());
    }

    @Test
    void sameInstantWithAnotherOffsetIsTheSameReading() {
        var w = new Fakes.World();
        w.telemetry.ingestReading(Fakes.reading(DEVICE, "ph", 6.0, "2026-11-04T14:05:00+01:00", false));
        var result = w.telemetry.ingestReading(Fakes.reading(DEVICE, "ph", 6.0, "2026-11-04T13:05:00Z", false));
        assertEquals(IngestResult.Outcome.DUPLICATE, result.outcome());
    }

    @Test
    void invalidReadingIsNeverStored() {
        var w = new Fakes.World();
        var result = w.telemetry.ingestReading(Fakes.reading(DEVICE, "ph", 99, w.now(), false));
        assertEquals(IngestResult.Outcome.INVALID, result.outcome());
        assertTrue(w.store.readings.isEmpty());
    }

    @Test
    void bufferedReadingIsHistoryNotTheLiveValue() {
        var w = new Fakes.World();
        w.online(DEVICE);
        w.read(DEVICE, "ph", 6.0);
        w.clock.advance(Duration.ofSeconds(5));
        // arrives now, measured later than the live one, but flagged as buffered
        w.telemetry.ingestReading(Fakes.reading(DEVICE, "ph", 6.3, w.now(), true));

        var live = w.telemetry.latest(DEVICE);
        assertEquals(1, live.size());
        assertEquals(6.0, live.get(0).value());
        assertEquals(2, w.store.readings.size());   // but the history keeps both
    }

    @Test
    void sensorIsStaleAfterThreeIntervalsOnlyWhileOnline() {
        var w = new Fakes.World();
        w.online(DEVICE);
        w.read(DEVICE, "ph", 6.0);
        w.clock.advance(Duration.ofSeconds(14));
        assertFalse(w.telemetry.latest(DEVICE).get(0).stale());
        w.clock.advance(Duration.ofSeconds(2));
        assertTrue(w.telemetry.latest(DEVICE).get(0).stale());

        w.telemetry.ingestStatus(Fakes.status(DEVICE, false, null));
        assertFalse(w.telemetry.latest(DEVICE).get(0).stale(), "offline is reported separately");
    }

    @Test
    void retainedStatusReplayIsADuplicate() {
        var w = new Fakes.World();
        var status = Fakes.status(DEVICE, true, w.now());
        assertEquals(IngestResult.Outcome.STORED, w.telemetry.ingestStatus(status).outcome());
        assertEquals(IngestResult.Outcome.DUPLICATE, w.telemetry.ingestStatus(status).outcome());
    }

    @Test
    void historyIsOrderedByMeasurementTimeNotArrival() {
        var w = new Fakes.World();
        String late = w.now();
        w.clock.advance(Duration.ofSeconds(10));
        w.read(DEVICE, "ec", 1.4);
        w.telemetry.ingestReading(Fakes.reading(DEVICE, "ec", 1.2, late, true));   // arrives last

        var points = w.telemetry.history(DEVICE, "ec", Fakes.T0.minusSeconds(60), w.clock.instant(), 100);
        assertEquals(1.2, points.get(0).getValue());
        assertEquals(1.4, points.get(1).getValue());
    }
}
