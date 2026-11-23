package tn.supcom.basilcare.services;

import jakarta.json.Json;
import jakarta.json.JsonObject;
import jakarta.json.JsonObjectBuilder;
import org.junit.jupiter.api.Test;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class LiveFrameStoreTest {

    private static JsonObjectBuilder frame(String device, int frameId) {
        return Json.createObjectBuilder()
                .add("device_id", device).add("frame_id", frameId).add("model_version", "basil-detect-0.1")
                .add("captured_at", "2026-11-23T18:00:00+01:00").add("width", 640).add("height", 480)
                .add("image_jpeg", "/9j/4AAQSkZJRg==")
                .add("detections", Json.createArrayBuilder().add(Json.createObjectBuilder()
                        .add("label", "downy_mildew").add("confidence", 0.71)
                        .add("box", Json.createArrayBuilder().add(0.1).add(0.2).add(0.5).add(0.6))))
                .add("inference_ms", 180.5).add("fps", 2.1);
    }

    @Test
    void keepsOnlyTheLatestFramePerDevice() {
        var store = new LiveFrameStore();
        store.setClock(Clock.fixed(Instant.parse("2026-11-23T17:00:00Z"), ZoneOffset.UTC));
        assertEquals(IngestResult.Outcome.STORED, store.accept(frame("basil-pi-01", 1).build()).outcome());
        assertEquals(IngestResult.Outcome.STORED, store.accept(frame("basil-pi-01", 2).build()).outcome());
        store.accept(frame("basil-pi-02", 7).build());
        assertEquals(2, store.latest("basil-pi-01").orElseThrow().payload().getInt("frame_id"));
        assertEquals(7, store.latest("basil-pi-02").orElseThrow().payload().getInt("frame_id"));
        assertTrue(store.latest("basil-pi-03").isEmpty());
    }

    @Test
    void rejectsMalformedFrames() {
        var store = new LiveFrameStore();
        JsonObject noImage = frame("basil-pi-01", 1).remove("image_jpeg").build();
        JsonObject badBox = frame("basil-pi-01", 1).add("detections", Json.createArrayBuilder()
                .add(Json.createObjectBuilder().add("label", "healthy").add("confidence", 0.5)
                        .add("box", Json.createArrayBuilder().add(0.1).add(1.7)))).build();
        JsonObject huge = frame("basil-pi-01", 1)
                .add("image_jpeg", "A".repeat(LiveFrameStore.MAX_IMAGE_CHARS + 1)).build();
        JsonObject badDevice = frame("Basil/Pi", 1).build();
        for (JsonObject bad : new JsonObject[]{noImage, badBox, huge, badDevice}) {
            assertEquals(IngestResult.Outcome.INVALID, store.accept(bad).outcome());
        }
        assertTrue(store.latest("basil-pi-01").isEmpty());
    }
}
