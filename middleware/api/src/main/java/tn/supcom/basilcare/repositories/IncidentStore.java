package tn.supcom.basilcare.repositories;

import tn.supcom.basilcare.entities.Incident;
import tn.supcom.basilcare.entities.Threshold;

import java.util.Collection;
import java.util.List;
import java.util.Optional;

/** Storage operations of incidents and alert thresholds (see TelemetryStore for why an interface). */
public interface IncidentStore {

    /** The open or acknowledged incident with this key, if any. */
    Optional<Incident> findUnresolved(String key);

    Optional<Incident> find(String id);

    void save(Incident incident);

    /** Newest first. deviceId null = every device; statuses empty = every status. */
    List<Incident> list(String deviceId, Collection<String> statuses, int limit);

    Optional<Threshold> threshold(String sensor);

    List<Threshold> thresholds();

    void saveThreshold(Threshold threshold);
}
