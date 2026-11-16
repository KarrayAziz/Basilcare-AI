package tn.supcom.basilcare.services;

import jakarta.enterprise.context.ApplicationScoped;
import tn.supcom.basilcare.entities.Incident;

import java.util.logging.Logger;

/**
 * Default notifier: writes the incident to the server log. The PWAs poll /api/incidents
 * and show a browser notification, so a farmer with the app open is told within seconds.
 * Push notifications to a closed app (Web Push, VAPID keys) are the next step.
 */
@ApplicationScoped
public class LogNotifier implements Notifier {

    private static final Logger LOG = Logger.getLogger(LogNotifier.class.getName());

    @Override
    public void incidentRaised(Incident incident) {
        LOG.warning(() -> "INCIDENT [" + incident.getSeverity() + "] " + incident.getDeviceId()
                + ": " + incident.getTitle() + " - " + incident.getDetail());
    }
}
