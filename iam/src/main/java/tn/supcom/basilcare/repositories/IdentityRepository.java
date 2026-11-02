package tn.supcom.basilcare.repositories;

import jakarta.data.repository.CrudRepository;
import jakarta.data.repository.Repository;
import tn.supcom.basilcare.entities.Identity;

import java.util.Optional;

@Repository
public interface IdentityRepository extends CrudRepository<Identity, String> {

    // Implemented automatically from the method name
    Optional<Identity> findByEmail(String email);
}