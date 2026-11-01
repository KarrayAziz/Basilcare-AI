package tn.supcom.basilcare;

import jakarta.ws.rs.ApplicationPath;
import jakarta.ws.rs.core.Application;

/**
 * Turns on Jakarta REST for this WAR. The WAR is deployed under /api (its file name),
 * and "/" here means resources are directly under it: /api/health, /api/me, ...
 */
@ApplicationPath("/")
public class ApiApplication extends Application {
}