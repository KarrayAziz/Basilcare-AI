package tn.supcom.basilcare.services;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.inject.Produces;

import java.time.Clock;

/** The services ask for a Clock instead of calling now() directly, so tests can freeze time. */
@ApplicationScoped
public class ClockProducer {

    @Produces
    public Clock clock() {
        return Clock.systemDefaultZone();
    }
}
