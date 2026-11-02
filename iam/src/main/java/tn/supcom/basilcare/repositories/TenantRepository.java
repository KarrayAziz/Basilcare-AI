package tn.supcom.basilcare.repositories;

import jakarta.data.repository.CrudRepository;
import jakarta.data.repository.Repository;
import tn.supcom.basilcare.entities.Tenant;

@Repository
public interface TenantRepository extends CrudRepository<Tenant, String> {
}