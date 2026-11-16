package tn.supcom.basilcare.services;

import jakarta.json.Json;
import jakarta.json.JsonObject;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class ContractValidatorTest {

    private static final String T = "2026-11-04T14:05:00+01:00";

    @Test
    void acceptsTheContractExample() {
        assertEquals(List.of(), ContractValidator.telemetry(Fakes.reading("basil-pi-01", "ph", 6.04, T, false)));
    }

    @Test
    void rejectsWrongUnitOutOfRangeValueAndTimeWithoutOffset() {
        JsonObject p = Json.createObjectBuilder(Fakes.reading("basil-pi-01", "ph", 15, "2026-11-04T14:05:00", false))
                .add("unit", "mV").build();
        var errors = ContractValidator.telemetry(p);
        assertTrue(errors.contains("unit must be pH"), errors.toString());
        assertTrue(errors.stream().anyMatch(e -> e.startsWith("value outside")), errors.toString());
        assertTrue(errors.contains("measured_at must be ISO 8601 with an offset"), errors.toString());
    }

    @Test
    void rejectsStringValuesAndUnknownSensors() {
        JsonObject p = Json.createObjectBuilder(Fakes.reading("basil-pi-01", "ph", 6, T, false))
                .add("value", "6.0").build();
        assertTrue(ContractValidator.telemetry(p).stream().anyMatch(e -> e.startsWith("value outside")));
        JsonObject unknown = Json.createObjectBuilder(Fakes.reading("basil-pi-01", "ph", 6, T, false))
                .add("sensor", "co2").build();
        assertTrue(ContractValidator.telemetry(unknown).contains("unknown sensor co2"));
    }

    @Test
    void lastWillMayHaveANullReportedAt() {
        assertTrue(ContractValidator.status(Fakes.status("basil-pi-01", false, null)).isEmpty());
    }

    @Test
    void pumpStateNeedsAKnownState() {
        JsonObject p = Json.createObjectBuilder()
                .add("device_id", "basil-pi-01").add("state", "running").addNull("until")
                .addNull("command_id").addNull("result").addNull("reason").add("reported_at", T).build();
        assertEquals(List.of("state must be on, off or fault"), ContractValidator.pumpState(p));
    }
}
