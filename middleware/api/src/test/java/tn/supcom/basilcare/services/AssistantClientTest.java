package tn.supcom.basilcare.services;

import com.sun.net.httpserver.HttpServer;
import jakarta.json.Json;
import jakarta.json.JsonObject;
import org.junit.jupiter.api.Test;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.Optional;
import java.util.concurrent.atomic.AtomicReference;
import static org.junit.jupiter.api.Assertions.*;

class AssistantClientTest {
    static JsonObject result(String url) {
        return Json.createObjectBuilder().add("status", "answered").add("answer", "Pinch the tips.")
                .add("citations", Json.createArrayBuilder().add(Json.createObjectBuilder().add("title", "NC State")
                        .add("text", "Pinch the tips.").add("url", url))).build();
    }

    @Test void bridgeSendsOnlyTheQuestionAndServiceCredential() throws Exception {
        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        AtomicReference<String> auth = new AtomicReference<>();
        AtomicReference<String> body = new AtomicReference<>();
        server.createContext("/ask", exchange -> {
            auth.set(exchange.getRequestHeaders().getFirst("Authorization"));
            body.set(new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8));
            byte[] bytes = result("https://plants.ces.ncsu.edu/plants/ocimum-basilicum/").toString().getBytes(StandardCharsets.UTF_8);
            exchange.sendResponseHeaders(200, bytes.length);
            exchange.getResponseBody().write(bytes);
            exchange.close();
        });
        server.start();
        try {
            AssistantClient client = new AssistantClient();
            client.url = "http://127.0.0.1:" + server.getAddress().getPort() + "/ask";
            client.key = Optional.of("service-credential-at-least-24-chars");
            assertEquals("answered", client.ask("How should I prune basil?").getString("status"));
            assertEquals("Bearer service-credential-at-least-24-chars", auth.get());
            assertEquals("{\"question\":\"How should I prune basil?\"}", body.get());
            client.key = Optional.empty();
            assertThrows(AssistantClient.Unavailable.class, () -> client.ask("basil"));
        } finally { server.stop(0); }
    }

    @Test void rejectsUnsafeLinksExtraMetadataAndUncitedAnswers() {
        assertThrows(AssistantClient.Unavailable.class, () -> AssistantClient.validate(result("javascript:alert(1)")));
        assertThrows(AssistantClient.Unavailable.class, () -> AssistantClient.validate(Json.createObjectBuilder()
                .add("status", "answered").add("answer", "Invented").add("citations", Json.createArrayBuilder()).build()));
        assertThrows(AssistantClient.Unavailable.class, () -> AssistantClient.validate(Json.createObjectBuilder(result(
                "https://plants.ces.ncsu.edu/plants/ocimum-basilicum/")).add("key", "not-for-the-browser").build()));
    }

    @Test void userAndConcurrencyLimitsAreBoundedAndRecover() {
        AssistantLimits limits = new AssistantLimits();
        for (int i = 0; i < 6; i++) assertTrue(limits.allow("aziz", 1000));
        assertFalse(limits.allow("aziz", 2000));
        assertTrue(limits.allow("other", 2000));
        assertTrue(limits.allow("aziz", 61000));
        assertTrue(limits.acquire()); assertTrue(limits.acquire()); assertFalse(limits.acquire());
        limits.release(); assertTrue(limits.acquire());
        for (int i = 0; i < 1024; i++) limits.allow("user" + i, 62000);
        assertFalse(limits.allow("extra-user", 62000));
        assertTrue(limits.allow("extra-user", 123000));
    }
}
