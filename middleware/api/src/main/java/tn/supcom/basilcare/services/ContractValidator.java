package tn.supcom.basilcare.services;

import jakarta.json.JsonNumber;
import jakarta.json.JsonObject;
import jakarta.json.JsonValue;

import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.regex.Pattern;

/**
 * Re-checks the messages forwarded by Node-RED against docs/mqtt-contract.md.
 * Node-RED already validates them; the API checks again because it is the last
 * line before the database (defence in depth: an HTTP client other than Node-RED,
 * or a bug in a flow, must never store an invalid reading).
 *
 * Every method returns the list of problems; an empty list means valid.
 */
public final class ContractValidator {

    public static final Pattern DEVICE_ID = Pattern.compile("^[a-z0-9-]{3,32}$");
    private static final Set<String> PUMP_STATES = Set.of("on", "off", "fault");
    private static final Set<String> PUMP_RESULTS = Set.of("executed", "rejected");

    private ContractValidator() {
    }

    public static List<String> telemetry(JsonObject p) {
        List<String> errors = new ArrayList<>();
        if (p == null) {
            return List.of("a JSON object is required");
        }
        deviceId(p, errors);
        String sensorName = text(p, "sensor");
        var sensor = SensorCatalog.find(sensorName);
        if (sensor.isEmpty()) {
            errors.add("unknown sensor " + sensorName);
        } else {
            if (!sensor.get().unit().equals(text(p, "unit"))) {
                errors.add("unit must be " + sensor.get().unit());
            }
            Double value = number(p, "value");
            if (value == null || !sensor.get().plausible(value)) {
                errors.add("value outside the plausible range " + sensor.get().min() + " to " + sensor.get().max());
            }
        }
        timestamp(p, "measured_at", false, errors);
        bool(p, "calibrated", errors);
        bool(p, "buffered", errors);
        if (!isInteger(p, "seq") || p.getJsonNumber("seq").longValue() < 1) {
            errors.add("seq must be a positive integer");
        }
        return errors;
    }

    public static List<String> status(JsonObject p) {
        List<String> errors = new ArrayList<>();
        if (p == null) {
            return List.of("a JSON object is required");
        }
        deviceId(p, errors);
        bool(p, "online", errors);
        timestamp(p, "started_at", false, errors);
        timestamp(p, "reported_at", true, errors);   // null in the Last Will
        if (!isInteger(p, "telemetry_interval_s") || p.getJsonNumber("telemetry_interval_s").intValue() < 1) {
            errors.add("telemetry_interval_s must be a positive integer");
        }
        return errors;
    }

    public static List<String> pumpState(JsonObject p) {
        List<String> errors = new ArrayList<>();
        if (p == null) {
            return List.of("a JSON object is required");
        }
        deviceId(p, errors);
        if (!PUMP_STATES.contains(text(p, "state"))) {
            errors.add("state must be on, off or fault");
        }
        timestamp(p, "until", true, errors);
        timestamp(p, "reported_at", false, errors);
        String result = nullableText(p, "result");
        if (result != null && !PUMP_RESULTS.contains(result)) {
            errors.add("result must be executed, rejected or null");
        }
        return errors;
    }

    public static List<String> screening(JsonObject p) {
        List<String> errors = new ArrayList<>();
        if (p == null) {
            return List.of("a JSON object is required");
        }
        deviceId(p, errors);
        if (text(p, "image_id") == null) {
            errors.add("image_id is required");
        }
        if (text(p, "label") == null) {
            errors.add("label is required");
        }
        if (text(p, "model_version") == null) {
            errors.add("model_version is required");
        }
        timestamp(p, "captured_at", false, errors);
        Double confidence = number(p, "confidence");
        if (confidence == null || confidence < 0 || confidence > 1) {
            errors.add("confidence must be a number between 0 and 1");
        }
        bool(p, "quality_ok", errors);
        bool(p, "review_required", errors);
        if (p.get("quality_issues") == null || p.get("quality_issues").getValueType() != JsonValue.ValueType.ARRAY) {
            errors.add("quality_issues must be a list");
        }
        return errors;
    }

    // ---- helpers ---------------------------------------------------------------

    private static void deviceId(JsonObject p, List<String> errors) {
        String id = text(p, "device_id");
        if (id == null || !DEVICE_ID.matcher(id).matches()) {
            errors.add("invalid device_id");
        }
    }

    private static void timestamp(JsonObject p, String field, boolean nullable, List<String> errors) {
        JsonValue value = p.get(field);
        if (nullable && (value == null || value.getValueType() == JsonValue.ValueType.NULL)) {
            return;
        }
        if (Timestamps.parse(text(p, field)).isEmpty()) {
            errors.add(field + " must be ISO 8601 with an offset");
        }
    }

    private static void bool(JsonObject p, String field, List<String> errors) {
        JsonValue value = p.get(field);
        if (value != JsonValue.TRUE && value != JsonValue.FALSE) {
            errors.add(field + " must be true or false");
        }
    }

    static String text(JsonObject p, String field) {
        JsonValue value = p.get(field);
        if (value == null || value.getValueType() != JsonValue.ValueType.STRING) {
            return null;
        }
        String text = p.getString(field);
        return text.isEmpty() ? null : text;
    }

    static String nullableText(JsonObject p, String field) {
        return text(p, field);
    }

    static Double number(JsonObject p, String field) {
        JsonValue value = p.get(field);
        return value != null && value.getValueType() == JsonValue.ValueType.NUMBER
                ? ((JsonNumber) value).doubleValue() : null;
    }

    private static boolean isInteger(JsonObject p, String field) {
        JsonValue value = p.get(field);
        return value != null && value.getValueType() == JsonValue.ValueType.NUMBER
                && ((JsonNumber) value).isIntegral();
    }
}
