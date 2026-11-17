package tn.supcom.basilcare.repositories;

import jakarta.data.repository.CrudRepository;
import jakarta.data.repository.Repository;
import tn.supcom.basilcare.entities.Device;

@Repository
public interface DeviceRepository extends CrudRepository<Device, String> {
}
