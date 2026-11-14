package tn.supcom.basilcare.services;

import tn.supcom.basilcare.entities.Threshold;

import java.util.List;

/**
 * Starting alert ranges, written to the database the first time the API starts.
 *
 * They are typical values quoted for hydroponic sweet basil and exist only so that the
 * demo raises realistic incidents. They are marked verified=false: an administrator must
 * check them against the selected cultivar, nutrient solution and agronomic sources, then
 * edit them with PUT /api/thresholds/{sensor} (scope section 1.4).
 */
final class DefaultThresholds {

    static final String PLACEHOLDER =
            "Placeholder typical of hydroponic basil - verify against agronomic sources before relying on it";

    private DefaultThresholds() {
    }

    static List<Threshold> all() {
        return List.of(
                of("ph", 5.5, 6.5, "warning"),
                of("ec", 1.0, 1.6, "warning"),
                of("water_temperature", 18.0, 24.0, "warning"),
                of("air_temperature", 18.0, 30.0, "warning"),
                of("air_humidity", 40.0, 70.0, "warning"),
                // above the pump's 20 % lock-out, so the farmer is warned before the pump refuses to start
                of("water_level", 25.0, null, "critical"));
    }

    private static Threshold of(String sensor, Double min, Double max, String severity) {
        Threshold t = new Threshold();
        t.setSensor(sensor);
        t.setMin(min);
        t.setMax(max);
        t.setEnabled(true);
        t.setSeverity(severity);
        t.setVerified(false);
        t.setSource(PLACEHOLDER);
        t.setUpdatedBy("system");
        return t;
    }
}
