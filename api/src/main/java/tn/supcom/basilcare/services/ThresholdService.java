package tn.supcom.basilcare.services;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import tn.supcom.basilcare.entities.Threshold;
import tn.supcom.basilcare.repositories.IncidentStore;

import java.time.Clock;
import java.util.List;
import java.util.Set;

/** Reads and changes the agronomic alert ranges (administrators only, see ThresholdResource). */
@ApplicationScoped
public class ThresholdService {

    private static final Set<String> SEVERITIES = Set.of(IncidentService.WARNING, IncidentService.CRITICAL);

    @Inject
    IncidentStore store;

    @Inject
    Clock clock;

    public ThresholdService() {
    }

    ThresholdService(IncidentStore store, Clock clock) {
        this.store = store;
        this.clock = clock;
    }

    /** Writes the default ranges for sensors that have none yet. Never overwrites an admin's choice. */
    public int seedDefaults() {
        int added = 0;
        for (Threshold threshold : DefaultThresholds.all()) {
            if (store.threshold(threshold.getSensor()).isEmpty()) {
                threshold.setUpdatedAt(Timestamps.now(clock));
                store.saveThreshold(threshold);
                added++;
            }
        }
        return added;
    }

    public List<Threshold> list() {
        return store.thresholds();
    }

    /** @throws IllegalArgumentException when the range is not usable */
    public Threshold update(String sensor, Threshold request, String user) {
        var catalog = SensorCatalog.find(sensor)
                .orElseThrow(() -> new IllegalArgumentException("Unknown sensor " + sensor + "."));
        if (request == null) {
            throw new IllegalArgumentException("A JSON request body is required.");
        }
        Double min = request.getMin();
        Double max = request.getMax();
        if (min == null && max == null) {
            throw new IllegalArgumentException("Give at least a min or a max.");
        }
        if ((min != null && !catalog.plausible(min)) || (max != null && !catalog.plausible(max))) {
            throw new IllegalArgumentException("Limits must be inside the plausible range " + catalog.min()
                    + " to " + catalog.max() + " " + catalog.unit() + ".");
        }
        if (min != null && max != null && min >= max) {
            throw new IllegalArgumentException("min must be lower than max.");
        }
        String severity = request.getSeverity() == null ? IncidentService.WARNING : request.getSeverity();
        if (!SEVERITIES.contains(severity)) {
            throw new IllegalArgumentException("severity must be warning or critical.");
        }
        String source = request.getSource() == null ? null : request.getSource().trim();
        if (request.isVerified() && (source == null || source.length() < 5)) {
            throw new IllegalArgumentException("A verified range must name its source (document, page).");
        }
        Threshold saved = new Threshold();
        saved.setSensor(sensor);
        saved.setMin(min);
        saved.setMax(max);
        saved.setEnabled(request.isEnabled());
        saved.setSeverity(severity);
        saved.setVerified(request.isVerified());
        saved.setSource(source);
        saved.setUpdatedBy(user);
        saved.setUpdatedAt(Timestamps.now(clock));
        store.saveThreshold(saved);
        return saved;
    }
}
