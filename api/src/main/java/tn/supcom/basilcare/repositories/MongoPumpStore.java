package tn.supcom.basilcare.repositories;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import org.eclipse.jnosql.mapping.document.DocumentTemplate;
import tn.supcom.basilcare.entities.Device;
import tn.supcom.basilcare.entities.PumpCommand;
import tn.supcom.basilcare.entities.PumpStatus;

import java.util.List;
import java.util.Optional;

/** MongoDB implementation of PumpStore. */
@ApplicationScoped
public class MongoPumpStore implements PumpStore {

    @Inject
    DocumentTemplate template;

    @Override
    public Optional<Device> device(String deviceId) {
        return template.find(Device.class, deviceId);
    }

    @Override
    public Optional<PumpStatus> pumpStatus(String deviceId) {
        return template.find(PumpStatus.class, deviceId);
    }

    @Override
    public void savePumpStatus(PumpStatus status) {
        if (template.find(PumpStatus.class, status.getDeviceId()).isPresent()) {
            template.update(status);
        } else {
            template.insert(status);
        }
    }

    @Override
    public Optional<PumpCommand> command(String commandId) {
        return template.find(PumpCommand.class, commandId);
    }

    @Override
    public void saveCommand(PumpCommand command) {
        if (template.find(PumpCommand.class, command.getCommandId()).isPresent()) {
            template.update(command);
        } else {
            template.insert(command);
        }
    }

    @Override
    public List<PumpCommand> commands(String deviceId, int limit) {
        if (deviceId == null) {
            return template.select(PumpCommand.class).orderBy("requestedAtEpoch").desc().limit(limit).result();
        }
        return template.select(PumpCommand.class)
                .where("deviceId").eq(deviceId)
                .orderBy("requestedAtEpoch").desc().limit(limit).result();
    }
}
