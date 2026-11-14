package tn.supcom.basilcare.services;

import tn.supcom.basilcare.entities.Device;
import tn.supcom.basilcare.entities.DeviceState;
import tn.supcom.basilcare.entities.PumpStatus;
import tn.supcom.basilcare.entities.Reading;

import java.util.Optional;

/**
 * Deterministic safety check of a pump request, BEFORE anything is sent to the device
 * (scope section 5.3: "mutating operations require user confirmation and a deterministic
 * safety-policy check"). Pure function: same facts, same answer; no AI involved.
 *
 * The device applies its own rules again (contract section 5.2), so this policy is the first
 * of two independent barriers, not the only one.
 */
public final class PumpSafetyPolicy {

    public record Limits(int maxDurationS, double minWaterLevel, int commandTtlS) {
    }

    public record Facts(Optional<Device> device, Optional<DeviceState> state, Optional<PumpStatus> pump,
                        Optional<Reading> waterLevel, long nowMs) {
    }

    public record Decision(boolean accepted, String reason, String message) {
        static Decision accept() {
            return new Decision(true, null, "Command accepted and sent to the device.");
        }

        static Decision reject(String reason, String message) {
            return new Decision(false, reason, message);
        }
    }

    private PumpSafetyPolicy() {
    }

    /**
     * Rules, applied in order; the first that matches decides.
     * action and duration were already checked for shape (PumpService).
     */
    public static Decision evaluate(String action, Integer durationS, Facts facts, Limits limits) {
        if (facts.device().isEmpty()) {
            return Decision.reject("device_not_registered",
                    "This device is not in the registry. An administrator must register it first.");
        }
        if (!facts.device().get().isEnabled()) {
            return Decision.reject("device_disabled", "This device is disabled in the registry.");
        }
        if ("off".equals(action)) {
            return Decision.accept();   // stopping is always allowed, like on the device
        }
        if (facts.state().isEmpty() || !facts.state().get().isOnline()) {
            return Decision.reject("device_offline",
                    "The device is offline: a start command could not be confirmed.");
        }
        if (facts.pump().isPresent() && "fault".equals(facts.pump().get().getState())) {
            return Decision.reject("pump_fault", "The pump is in fault. Maintenance is needed on the device.");
        }
        if (durationS > limits.maxDurationS()) {
            return Decision.reject("duration_too_long",
                    "The maximum run is " + limits.maxDurationS() + " s.");
        }
        int interval = Math.max(1, facts.state().get().getTelemetryIntervalS());
        long maxAgeMs = 1000L * TelemetryService.STALE_INTERVALS * interval;
        if (facts.waterLevel().isEmpty() || facts.nowMs() - facts.waterLevel().get().getMeasuredAtEpoch() > maxAgeMs) {
            return Decision.reject("water_level_unknown",
                    "No recent water-level reading: running the pump dry cannot be excluded.");
        }
        double level = facts.waterLevel().get().getValue();
        if (level < limits.minWaterLevel()) {
            return Decision.reject("low_water_level",
                    "Water level " + level + " % is below the minimum " + limits.minWaterLevel() + " %. Refill first.");
        }
        return Decision.accept();
    }
}
