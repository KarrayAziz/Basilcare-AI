package tn.supcom.basilcare.repositories;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import jakarta.nosql.QueryMapper;
import org.eclipse.jnosql.mapping.document.DocumentTemplate;
import tn.supcom.basilcare.entities.Incident;
import tn.supcom.basilcare.entities.Threshold;

import java.util.Collection;
import java.util.List;
import java.util.Optional;

/** MongoDB implementation of IncidentStore. */
@ApplicationScoped
public class MongoIncidentStore implements IncidentStore {

    private static final List<String> UNRESOLVED = List.of(Incident.OPEN, Incident.ACKNOWLEDGED);

    @Inject
    DocumentTemplate template;

    @Override
    public Optional<Incident> findUnresolved(String key) {
        List<Incident> found = template.select(Incident.class)
                .where("key").eq(key)
                .and("status").in(UNRESOLVED)
                .limit(1)
                .result();
        return found.stream().findFirst();
    }

    @Override
    public Optional<Incident> find(String id) {
        return template.find(Incident.class, id);
    }

    @Override
    public void save(Incident incident) {
        if (template.find(Incident.class, incident.getId()).isPresent()) {
            template.update(incident);
        } else {
            template.insert(incident);
        }
    }

    @Override
    public List<Incident> list(String deviceId, Collection<String> statuses, int limit) {
        QueryMapper.MapperFrom from = template.select(Incident.class);
        QueryMapper.MapperWhere where = null;
        if (deviceId != null) {
            where = from.where("deviceId").eq(deviceId);
        }
        if (statuses != null && !statuses.isEmpty()) {
            where = where == null ? from.where("status").in(statuses) : where.and("status").in(statuses);
        }
        QueryMapper.MapperOrder order = where == null ? from.orderBy("openedAtEpoch") : where.orderBy("openedAtEpoch");
        return order.desc().limit(limit).result();
    }

    @Override
    public Optional<Threshold> threshold(String sensor) {
        return template.find(Threshold.class, sensor);
    }

    @Override
    public List<Threshold> thresholds() {
        return template.select(Threshold.class).orderBy("sensor").asc().result();
    }

    @Override
    public void saveThreshold(Threshold threshold) {
        if (template.find(Threshold.class, threshold.getSensor()).isPresent()) {
            template.update(threshold);
        } else {
            template.insert(threshold);
        }
    }
}
