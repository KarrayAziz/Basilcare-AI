package tn.supcom.basilcare.services;

import jakarta.ejb.Schedule;
import jakarta.ejb.Singleton;
import jakarta.inject.Inject;

import java.util.logging.Level;
import java.util.logging.Logger;

/**
 * Every 15 seconds, looks for sensors that stopped reporting (contract section 7).
 * A missing reading produces no message, so this cannot be done at ingestion time.
 * persistent=false: a missed run after a restart is simply skipped.
 */
@Singleton
public class StaleWatcher {

    private static final Logger LOG = Logger.getLogger(StaleWatcher.class.getName());

    @Inject
    IncidentService incidents;

    @Schedule(hour = "*", minute = "*", second = "*/15", persistent = false)
    public void check() {
        try {
            incidents.checkStale();
        } catch (RuntimeException e) {
            // never let one failure (e.g. database briefly down) cancel the timer
            LOG.log(Level.WARNING, "stale check failed", e);
        }
    }
}
