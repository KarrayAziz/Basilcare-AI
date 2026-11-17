package tn.supcom.basilcare.services;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Optional;

/**
 * Sensors of MQTT contract section 3.1, with their unit and PLAUSIBLE range.
 * A plausible range is not an alert threshold: it only says whether a value can be physically real.
 * Agronomic thresholds live in the thresholds collection (see ThresholdService).
 */
public final class SensorCatalog {

    public record Sensor(String name, String unit, double min, double max, String label) {
        public boolean plausible(double value) {
            return value >= min && value <= max;
        }
    }

    private static final Map<String, Sensor> SENSORS = new LinkedHashMap<>();

    static {
        add(new Sensor("air_temperature", "degC", -10, 60, "Air temperature"));
        add(new Sensor("air_humidity", "%RH", 0, 100, "Air humidity"));
        add(new Sensor("ph", "pH", 0, 14, "Solution pH"));
        add(new Sensor("ec", "mS/cm", 0, 20, "Solution EC"));
        add(new Sensor("water_temperature", "degC", 0, 50, "Water temperature"));
        add(new Sensor("water_level", "%", 0, 100, "Water level"));
    }

    private SensorCatalog() {
    }

    private static void add(Sensor sensor) {
        SENSORS.put(sensor.name(), sensor);
    }

    public static Optional<Sensor> find(String name) {
        return Optional.ofNullable(name == null ? null : SENSORS.get(name));
    }

    public static Iterable<Sensor> all() {
        return SENSORS.values();
    }
}
