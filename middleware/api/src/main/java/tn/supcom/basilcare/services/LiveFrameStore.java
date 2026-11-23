package tn.supcom.basilcare.services;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.json.JsonNumber;
import jakarta.json.JsonObject;
import jakarta.json.JsonValue;

import java.time.Clock;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Latest live camera frame of each device (contract section 6a), in memory only.
 *
 * Frames are transient on purpose: nothing is written to MongoDB, a restart forgets them, and
 * each new frame replaces the previous one. The 10-minute screenings remain the stored record.
 */
@ApplicationScoped
public class LiveFrameStore {

    /** Largest accepted JPEG, base64-encoded (a 640 px frame at quality 70 is about 60 KB). */
    public static final int MAX_IMAGE_CHARS = 700_000;

    public record Frame(JsonObject payload, Instant receivedAt) {
    }

    private final Map<String, Frame> latest = new ConcurrentHashMap<>();
    private Clock clock = Clock.systemUTC();

    void setClock(Clock clock) {   // tests
        this.clock = clock;
    }

    public IngestResult accept(JsonObject p) {
        List<String> errors = validate(p);
        if (!errors.isEmpty()) {
            return IngestResult.invalid(errors);
        }
        latest.put(p.getString("device_id"), new Frame(p, clock.instant()));
        return IngestResult.stored();
    }

    public Optional<Frame> latest(String deviceId) {
        return Optional.ofNullable(latest.get(deviceId));
    }

    public Instant now() {
        return clock.instant();
    }

    static List<String> validate(JsonObject p) {
        List<String> errors = new ArrayList<>();
        if (p == null) {
            return List.of("body is required");
        }
        String id = text(p, "device_id");
        if (id == null || !ContractValidator.DEVICE_ID.matcher(id).matches()) {
            errors.add("device_id is invalid");
        }
        String image = text(p, "image_jpeg");
        if (image == null || image.isEmpty()) {
            errors.add("image_jpeg is required");
        } else if (image.length() > MAX_IMAGE_CHARS) {
            errors.add("image_jpeg is larger than " + MAX_IMAGE_CHARS + " characters");
        }
        if (text(p, "model_version") == null) {
            errors.add("model_version is required");
        }
        if (!(p.get("frame_id") instanceof JsonNumber n) || !n.isIntegral() || n.longValue() < 1) {
            errors.add("frame_id must be an integer >= 1");
        }
        JsonValue detections = p.get("detections");
        if (detections == null || detections.getValueType() != JsonValue.ValueType.ARRAY) {
            errors.add("detections must be a list");
        } else {
            for (JsonValue d : detections.asJsonArray()) {
                if (!validDetection(d)) {
                    errors.add("each detection needs a label, a confidence 0..1 and a box of 4 numbers 0..1");
                    break;
                }
            }
        }
        return errors;
    }

    private static boolean validDetection(JsonValue value) {
        if (value.getValueType() != JsonValue.ValueType.OBJECT) {
            return false;
        }
        JsonObject d = value.asJsonObject();
        if (text(d, "label") == null || !(d.get("confidence") instanceof JsonNumber c)
                || c.doubleValue() < 0 || c.doubleValue() > 1) {
            return false;
        }
        JsonValue box = d.get("box");
        if (box == null || box.getValueType() != JsonValue.ValueType.ARRAY || box.asJsonArray().size() != 4) {
            return false;
        }
        for (JsonValue v : box.asJsonArray()) {
            if (!(v instanceof JsonNumber n) || n.doubleValue() < 0 || n.doubleValue() > 1) {
                return false;
            }
        }
        return true;
    }

    private static String text(JsonObject p, String field) {
        JsonValue v = p.get(field);
        return v != null && v.getValueType() == JsonValue.ValueType.STRING ? p.getString(field) : null;
    }
}
