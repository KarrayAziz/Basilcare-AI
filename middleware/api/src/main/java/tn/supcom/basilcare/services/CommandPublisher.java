package tn.supcom.basilcare.services;

/** Sends a message to the MQTT broker. An interface so PumpService is tested without a broker. */
public interface CommandPublisher {

    /** Publishes with QoS 1, never retained (contract section 5.1). Throws when the broker did not confirm. */
    void publish(String topic, String json) throws PublishException;

    class PublishException extends Exception {
        public PublishException(String message, Throwable cause) {
            super(message, cause);
        }
    }
}
