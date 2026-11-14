package tn.supcom.basilcare.repositories;

import tn.supcom.basilcare.entities.DeviceState;
import tn.supcom.basilcare.entities.Reading;
import tn.supcom.basilcare.entities.ScreeningResult;

import java.util.List;
import java.util.Optional;

/**
 * Storage operations needed by the telemetry services.
 *
 * A small interface instead of Jakarta Data repositories: the services are unit-tested
 * against an in-memory implementation, and MongoTelemetryStore is the only class that
 * knows about the database.
 */
public interface TelemetryStore {

    /** Stores the reading unless one with the same id exists. Returns false for a duplicate. */
    boolean insertReading(Reading reading);

    /** Newest NON-buffered reading of one sensor (the "live" value), if any. */
    Optional<Reading> latestLive(String deviceId, String sensor);

    /** Readings of one sensor between two instants (epoch ms, inclusive), oldest first. */
    List<Reading> history(String deviceId, String sensor, long fromEpoch, long toEpoch, int limit);

    Optional<DeviceState> deviceState(String deviceId);

    List<DeviceState> deviceStates();

    void saveDeviceState(DeviceState state);

    /** Stores the screening unless its imageId exists. Returns false for a duplicate. */
    boolean insertScreening(ScreeningResult result);

    /** Newest screenings first. deviceId null = every device. */
    List<ScreeningResult> screenings(String deviceId, int limit);
}
