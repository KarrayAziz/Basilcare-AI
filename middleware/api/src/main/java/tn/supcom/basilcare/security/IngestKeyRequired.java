package tn.supcom.basilcare.security;

import jakarta.ws.rs.NameBinding;

import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

/**
 * Marks the machine-to-machine endpoints called by Node-RED (/api/ingest/...).
 * They are not called by people, so they use a service key (X-Ingest-Key header)
 * instead of a user's JWT. See IngestKeyFilter.
 */
@NameBinding
@Retention(RetentionPolicy.RUNTIME)
@Target({ElementType.TYPE, ElementType.METHOD})
public @interface IngestKeyRequired {
}
