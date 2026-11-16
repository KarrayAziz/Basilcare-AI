package tn.supcom.basilcare.repositories;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import org.eclipse.jnosql.mapping.document.DocumentTemplate;
import tn.supcom.basilcare.entities.DeviceState;
import tn.supcom.basilcare.entities.Reading;
import tn.supcom.basilcare.entities.ScreeningResult;

import java.util.List;
import java.util.Optional;

/** MongoDB implementation of TelemetryStore, through the Jakarta NoSQL template. */
@ApplicationScoped
public class MongoTelemetryStore implements TelemetryStore {

    @Inject
    DocumentTemplate template;

    @Override
    public boolean insertReading(Reading reading) {
        if (template.find(Reading.class, reading.getId()).isPresent()) {
            return false;
        }
        template.insert(reading);
        return true;
    }

    @Override
    public Optional<Reading> latestLive(String deviceId, String sensor) {
        List<Reading> found = template.select(Reading.class)
                .where("deviceId").eq(deviceId)
                .and("sensor").eq(sensor)
                .and("buffered").eq(false)
                .orderBy("measuredAtEpoch").desc()
                .limit(1)
                .result();
        return found.stream().findFirst();
    }

    @Override
    public List<Reading> history(String deviceId, String sensor, long fromEpoch, long toEpoch, int limit) {
        return template.select(Reading.class)
                .where("deviceId").eq(deviceId)
                .and("sensor").eq(sensor)
                .and("measuredAtEpoch").gte(fromEpoch)
                .and("measuredAtEpoch").lte(toEpoch)
                .orderBy("measuredAtEpoch").asc()
                .limit(limit)
                .result();
    }

    @Override
    public Optional<DeviceState> deviceState(String deviceId) {
        return template.find(DeviceState.class, deviceId);
    }

    @Override
    public List<DeviceState> deviceStates() {
        return template.select(DeviceState.class).orderBy("deviceId").asc().result();
    }

    @Override
    public void saveDeviceState(DeviceState state) {
        // JNoSQL insert = MongoDB insertOne (fails on an existing _id), update = updateOne (no upsert)
        if (template.find(DeviceState.class, state.getDeviceId()).isPresent()) {
            template.update(state);
        } else {
            template.insert(state);
        }
    }

    @Override
    public boolean insertScreening(ScreeningResult result) {
        if (template.find(ScreeningResult.class, result.getImageId()).isPresent()) {
            return false;
        }
        template.insert(result);
        return true;
    }

    @Override
    public List<ScreeningResult> screenings(String deviceId, int limit) {
        if (deviceId == null) {
            return template.select(ScreeningResult.class)
                    .orderBy("capturedAtEpoch").desc().limit(limit).result();
        }
        return template.select(ScreeningResult.class)
                .where("deviceId").eq(deviceId)
                .orderBy("capturedAtEpoch").desc().limit(limit).result();
    }
}
