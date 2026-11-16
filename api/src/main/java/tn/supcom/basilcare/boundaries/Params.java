package tn.supcom.basilcare.boundaries;

import tn.supcom.basilcare.services.ContractValidator;
import tn.supcom.basilcare.services.Timestamps;

import java.time.Instant;

/** Validation of query parameters shared by the read endpoints. */
final class Params {

    private Params() {
    }

    static String deviceId(String value, boolean required) {
        if (value == null || value.isBlank()) {
            if (required) {
                throw new IllegalArgumentException("deviceId is required.");
            }
            return null;
        }
        if (!ContractValidator.DEVICE_ID.matcher(value).matches()) {
            throw new IllegalArgumentException("deviceId must contain 3 to 32 lowercase letters, digits or hyphens.");
        }
        return value;
    }

    static int limit(Integer value, int fallback, int max) {
        if (value == null) {
            return fallback;
        }
        if (value < 1 || value > max) {
            throw new IllegalArgumentException("limit must be between 1 and " + max + ".");
        }
        return value;
    }

    /** ISO 8601 with offset, e.g. 2026-11-04T14:05:00%2B01:00 (the + must be URL-encoded). */
    static Instant instant(String value, Instant fallback, String name) {
        if (value == null || value.isBlank()) {
            return fallback;
        }
        return Timestamps.parse(value)
                .orElseThrow(() -> new IllegalArgumentException(name + " must be ISO 8601 with an offset."))
                .toInstant();
    }
}
