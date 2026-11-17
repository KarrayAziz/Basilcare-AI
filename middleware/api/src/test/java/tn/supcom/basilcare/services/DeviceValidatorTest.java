package tn.supcom.basilcare.services;

import org.junit.jupiter.api.Test;
import tn.supcom.basilcare.entities.DeviceRequest;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

class DeviceValidatorTest {

    @Test
    void acceptsAndNormalizesAValidDevice() {
        DeviceRequest request = request("basil-pi-01", "  Greenhouse gateway  ", "  SUP'COM Lab  ");

        assertDoesNotThrow(() -> DeviceValidator.validateForCreate(request));
        assertEquals("Greenhouse gateway", request.getName());
        assertEquals("SUP'COM Lab", request.getLocation());
    }

    @Test
    void rejectsInvalidIdentifiersAndNames() {
        assertThrows(IllegalArgumentException.class,
                () -> DeviceValidator.validateForCreate(request("Bad_Id", "Gateway", null)));
        assertThrows(IllegalArgumentException.class,
                () -> DeviceValidator.validateForCreate(request("pi-01", "  ", null)));
    }

    @Test
    void updateBodyCannotAddressAnotherDevice() {
        DeviceRequest request = request("basil-pi-02", "Gateway", null);
        assertThrows(IllegalArgumentException.class,
                () -> DeviceValidator.validateForUpdate("basil-pi-01", request));
    }

    @Test
    void updateMayOmitTheBodyIdentifier() {
        DeviceRequest request = request(null, "Gateway", null);
        assertDoesNotThrow(() -> DeviceValidator.validateForUpdate("basil-pi-01", request));
    }

    private static DeviceRequest request(String id, String name, String location) {
        DeviceRequest request = new DeviceRequest();
        request.setDeviceId(id);
        request.setName(name);
        request.setLocation(location);
        return request;
    }
}
