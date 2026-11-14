package tn.supcom.basilcare.services;

import com.mongodb.client.MongoClient;
import com.mongodb.client.MongoClients;
import com.mongodb.client.MongoDatabase;
import com.mongodb.client.model.Indexes;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.context.Initialized;
import jakarta.enterprise.event.Observes;
import jakarta.inject.Inject;
import org.eclipse.microprofile.config.inject.ConfigProperty;

import java.util.logging.Level;
import java.util.logging.Logger;

/**
 * Runs once when the API is deployed:
 * creates the MongoDB indexes the queries rely on, and seeds the default alert ranges.
 * Both are idempotent, so a restart changes nothing.
 */
@ApplicationScoped
public class Startup {

    private static final Logger LOG = Logger.getLogger(Startup.class.getName());

    @Inject
    @ConfigProperty(name = "jnosql.mongodb.host")
    String mongoHost;

    @Inject
    @ConfigProperty(name = "jnosql.document.database")
    String database;

    @Inject
    ThresholdService thresholds;

    void onStart(@Observes @Initialized(ApplicationScoped.class) Object event) {
        try {
            createIndexes();
            int added = thresholds.seedDefaults();
            LOG.info(() -> "BasilCare API ready (" + added + " default alert ranges added)");
        } catch (RuntimeException e) {
            // The API still starts: queries work without indexes, only slower.
            LOG.log(Level.WARNING, "startup tasks failed; is MongoDB reachable at " + mongoHost + "?", e);
        }
    }

    private void createIndexes() {
        String uri = mongoHost.startsWith("mongodb") ? mongoHost : "mongodb://" + mongoHost;
        try (MongoClient client = MongoClients.create(uri)) {
            MongoDatabase db = client.getDatabase(database);
            // latest live value, history and stale check
            db.getCollection("readings").createIndex(
                    Indexes.compoundIndex(Indexes.ascending("deviceId", "sensor", "buffered"),
                            Indexes.descending("measuredAtEpoch")));
            db.getCollection("readings").createIndex(
                    Indexes.compoundIndex(Indexes.ascending("deviceId", "sensor"), Indexes.ascending("measuredAtEpoch")));
            db.getCollection("incidents").createIndex(Indexes.ascending("key", "status"));
            db.getCollection("incidents").createIndex(Indexes.descending("openedAtEpoch"));
            db.getCollection("screenings").createIndex(
                    Indexes.compoundIndex(Indexes.ascending("deviceId"), Indexes.descending("capturedAtEpoch")));
            db.getCollection("pump_commands").createIndex(
                    Indexes.compoundIndex(Indexes.ascending("deviceId"), Indexes.descending("requestedAtEpoch")));
        }
    }
}
