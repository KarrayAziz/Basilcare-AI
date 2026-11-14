package tn.supcom.basilcare.services;

import jakarta.annotation.PreDestroy;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import org.eclipse.microprofile.config.inject.ConfigProperty;
import org.eclipse.paho.client.mqttv3.MqttClient;
import org.eclipse.paho.client.mqttv3.MqttConnectOptions;
import org.eclipse.paho.client.mqttv3.MqttException;
import org.eclipse.paho.client.mqttv3.MqttMessage;
import org.eclipse.paho.client.mqttv3.persist.MemoryPersistence;

import java.nio.charset.StandardCharsets;
import java.util.Optional;
import java.util.UUID;

/**
 * Publishes pump commands to Mosquitto (Eclipse Paho client).
 *
 * The API is the only component allowed to publish on pump/cmd (contract section 5),
 * so it talks to the broker directly instead of going through Node-RED: one hop less
 * between the safety policy and the device.
 * Connects on first use and reconnects if the broker restarted.
 */
@ApplicationScoped
public class MqttCommandPublisher implements CommandPublisher {

    @Inject
    @ConfigProperty(name = "mqtt.broker.url")
    String brokerUrl;

    @Inject
    @ConfigProperty(name = "mqtt.username")
    Optional<String> username;

    @Inject
    @ConfigProperty(name = "mqtt.password")
    Optional<String> password;

    private MqttClient client;

    @Override
    public synchronized void publish(String topic, String json) throws PublishException {
        try {
            MqttMessage message = new MqttMessage(json.getBytes(StandardCharsets.UTF_8));
            message.setQos(1);
            message.setRetained(false);   // a retained command could start the pump after a reconnection
            connected().publish(topic, message);   // blocks until the broker's PUBACK
        } catch (MqttException e) {
            throw new PublishException("MQTT broker unavailable at " + brokerUrl, e);
        }
    }

    private MqttClient connected() throws MqttException {
        if (client == null) {
            client = new MqttClient(brokerUrl, "basilcare-api-" + UUID.randomUUID(), new MemoryPersistence());
            client.setTimeToWait(5000);
        }
        if (!client.isConnected()) {
            MqttConnectOptions options = new MqttConnectOptions();
            options.setCleanSession(true);
            options.setConnectionTimeout(5);
            options.setKeepAliveInterval(30);
            username.filter(u -> !u.isBlank()).ifPresent(options::setUserName);
            password.filter(p -> !p.isBlank()).ifPresent(p -> options.setPassword(p.toCharArray()));
            client.connect(options);
        }
        return client;
    }

    @PreDestroy
    synchronized void close() {
        try {
            if (client != null && client.isConnected()) {
                client.disconnect();
            }
        } catch (MqttException ignored) {
            // shutting down anyway
        }
    }
}
