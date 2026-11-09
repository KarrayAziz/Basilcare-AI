package tn.supcom.basilcare.services;

import tn.supcom.basilcare.entities.DeviceRequest;

/** Validation and normalization shared by device creation and updates. */
public final class DeviceValidator {

    private DeviceValidator() {
    }

    public static void validateForCreate(DeviceRequest request) {
        if (request == null) {
            throw new IllegalArgumentException("A JSON request body is required.");
        }
        validateDeviceId(request.getDeviceId());
        validateDetails(request);
    }

    public static void validateForUpdate(String pathDeviceId, DeviceRequest request) {
        validateDeviceId(pathDeviceId);
        if (request == null) {
            throw new IllegalArgumentException("A JSON request body is required.");
        }
        if (request.getDeviceId() != null && !pathDeviceId.equals(request.getDeviceId())) {
            throw new IllegalArgumentException("deviceId in the body must match the request path.");
        }
        validateDetails(request);
    }

    private static void validateDeviceId(String deviceId) {
        if (deviceId == null || !deviceId.matches("[a-z0-9-]{3,32}")) {
            throw new IllegalArgumentException(
                    "deviceId must contain 3 to 32 lowercase letters, digits or hyphens.");
        }
    }

    private static void validateDetails(DeviceRequest request) {
        String name = normalize(request.getName());
        if (name == null || name.length() < 3 || name.length() > 80) {
            throw new IllegalArgumentException("name must contain 3 to 80 characters.");
        }
        String location = normalize(request.getLocation());
        if (location != null && location.length() > 120) {
            throw new IllegalArgumentException("location must contain at most 120 characters.");
        }
        request.setName(name);
        request.setLocation(location);
    }

    private static String normalize(String value) {
        if (value == null) {
            return null;
        }
        String normalized = value.trim();
        return normalized.isEmpty() ? null : normalized;
    }
}
