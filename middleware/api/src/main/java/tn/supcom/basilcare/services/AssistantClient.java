package tn.supcom.basilcare.services;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import jakarta.json.Json;
import jakarta.json.JsonObject;
import org.eclipse.microprofile.config.inject.ConfigProperty;
import java.io.StringReader;
import java.net.URI;
import java.net.HttpURLConnection;
import java.nio.charset.StandardCharsets;
import java.util.Optional;
import java.util.Set;

/** Server-only bridge. Neither the user JWT nor Gemini key is forwarded from this API. */
@ApplicationScoped
public class AssistantClient {
    @Inject @ConfigProperty(name = "assistant.url", defaultValue = "http://assistant:8090/ask")
    String url;
    @Inject @ConfigProperty(name = "assistant.service.key")
    Optional<String> key;

    public static class Unavailable extends RuntimeException { }

    public JsonObject ask(String question) {
        if (key.isEmpty() || key.get().length() < 24) throw new Unavailable();
        try {
            HttpURLConnection connection = (HttpURLConnection) URI.create(url).toURL().openConnection(java.net.Proxy.NO_PROXY);
            connection.setConnectTimeout(2000);
            connection.setReadTimeout(30000);
            connection.setInstanceFollowRedirects(false);
            connection.setRequestMethod("POST");
            connection.setRequestProperty("Content-Type", "application/json");
            connection.setRequestProperty("Authorization", "Bearer " + key.get());
            connection.setDoOutput(true);
            byte[] body = Json.createObjectBuilder().add("question", question).build().toString().getBytes(StandardCharsets.UTF_8);
            connection.setFixedLengthStreamingMode(body.length);
            try {
                try (var output = connection.getOutputStream()) { output.write(body); }
                if (connection.getResponseCode() != 200) throw new Unavailable();
                try (var stream = connection.getInputStream()) {
                    // Bounded read, even if an internal service is misconfigured.
                    byte[] raw = stream.readNBytes(32769);
                    if (raw.length > 32768) throw new Unavailable();
                    JsonObject result = Json.createReader(new StringReader(new String(raw, StandardCharsets.UTF_8))).readObject();
                    validate(result);
                    return result;
                }
            } finally { connection.disconnect(); }
        } catch (Exception e) {
            throw new Unavailable(); // No upstream body, headers, keys or questions in exception/log text.
        }
    }

    static void validate(JsonObject result) {
        Set<String> statuses = Set.of("answered", "insufficient_evidence", "action_unavailable", "live_data_unavailable", "diagnosis_unavailable");
        if (!result.keySet().equals(Set.of("status", "answer", "citations"))
                || !statuses.contains(result.getString("status")) || result.getString("answer").length() > 10000
                || result.getJsonArray("citations").size() > 2) throw new Unavailable();
        for (var value : result.getJsonArray("citations")) {
            JsonObject citation = value.asJsonObject();
            if (!citation.keySet().equals(Set.of("title", "url", "text"))
                    || citation.getString("title").length() > 500 || citation.getString("text").length() > 5000
                    || !Set.of("https://plants.ces.ncsu.edu/plants/ocimum-basilicum/",
                    "https://extension.usu.edu/yardandgarden/research/basil-in-the-garden").contains(citation.getString("url"))) {
                throw new Unavailable();
            }
        }
        boolean answered = result.getString("status").equals("answered");
        if (answered == result.getJsonArray("citations").isEmpty()) throw new Unavailable();
    }
}
