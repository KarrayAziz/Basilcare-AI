package tn.supcom.basilcare.services;

import tn.supcom.basilcare.entities.Reading;

/**
 * The current value of one sensor as shown on a dashboard.
 * stale = the device is online but this sensor stopped reporting (older than
 * 3 x telemetry_interval_s, contract section 7). ageSeconds lets the PWA show "12 s ago".
 */
public record LiveReading(String sensor, String label, double value, String unit, String measuredAt,
                          boolean calibrated, long ageSeconds, boolean stale) {

    public static LiveReading of(Reading reading, String label, long ageSeconds, boolean stale) {
        return new LiveReading(reading.getSensor(), label, reading.getValue(), reading.getUnit(),
                reading.getMeasuredAt(), reading.isCalibrated(), ageSeconds, stale);
    }
}
