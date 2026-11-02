package tn.supcom.basilcare;

import jakarta.ws.rs.ApplicationPath;
import jakarta.ws.rs.core.Application;

/** Endpoints live directly under the WAR name: /iam/authorize, /iam/oauth/token, ... */
@ApplicationPath("/")
public class IamApplication extends Application {
}