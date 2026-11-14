package tn.supcom.basilcare.repositories;

import tn.supcom.basilcare.entities.Device;
import tn.supcom.basilcare.entities.PumpCommand;
import tn.supcom.basilcare.entities.PumpStatus;

import java.util.List;
import java.util.Optional;

/** Storage operations of pump control (see TelemetryStore for why an interface). */
public interface PumpStore {

    /** The device in the administrator's registry, if registered. */
    Optional<Device> device(String deviceId);

    Optional<PumpStatus> pumpStatus(String deviceId);

    void savePumpStatus(PumpStatus status);

    Optional<PumpCommand> command(String commandId);

    void saveCommand(PumpCommand command);

    /** Newest first. deviceId null = every device. */
    List<PumpCommand> commands(String deviceId, int limit);
}
