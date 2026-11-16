package tn.supcom.basilcare.services;

import tn.supcom.basilcare.entities.Incident;

/**
 * Tells people about a new (or re-activated) incident (FR-04).
 * Strategy pattern: LogNotifier today; a Web Push or e-mail notifier can replace it
 * without touching the incident rules.
 */
public interface Notifier {

    void incidentRaised(Incident incident);
}
