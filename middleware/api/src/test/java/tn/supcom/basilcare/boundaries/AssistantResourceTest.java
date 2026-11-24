package tn.supcom.basilcare.boundaries;

import jakarta.ws.rs.core.SecurityContext;
import jakarta.json.Json;
import org.junit.jupiter.api.Test;
import tn.supcom.basilcare.services.AssistantClient;
import tn.supcom.basilcare.services.AssistantLimits;
import java.io.ByteArrayInputStream;
import java.nio.charset.StandardCharsets;
import java.security.Principal;
import static org.junit.jupiter.api.Assertions.*;

class AssistantResourceTest {
    static SecurityContext user(String role) {
        return new SecurityContext() {
            public Principal getUserPrincipal() { return () -> "aziz"; }
            public boolean isUserInRole(String value) { return role.equals(value); }
            public boolean isSecure() { return true; }
            public String getAuthenticationScheme() { return "Bearer"; }
        };
    }
    static ByteArrayInputStream body(String value) { return new ByteArrayInputStream(value.getBytes(StandardCharsets.UTF_8)); }
    static AssistantResource resource() {
        AssistantResource resource = new AssistantResource();
        resource.limits = new AssistantLimits();
        resource.assistant = new AssistantClient() {
            public jakarta.json.JsonObject ask(String question) { throw new Unavailable(); }
        };
        return resource;
    }

    @Test void authAndValidationFailBeforeAnUpstreamRequest() {
        AssistantResource resource = resource();
        assertEquals(401, resource.ask(body("{}"), null).getStatus());
        assertEquals(403, resource.ask(body("{}"), user("Guest")).getStatus());
        for (String json : new String[] {"{}", "[]", "{\"question\":null}", "{\"question\":123}",
                "{\"question\":\"  \"}", "{\"question\":\"basil\",\"key\":\"extra\"}",
                "{\"question\":\"" + "x".repeat(2001) + "\"}"}) {
            assertEquals(400, resource.ask(body(json), user("Farmer")).getStatus());
        }
        assertEquals(413, resource.ask(body("x".repeat(16385)), user("Farmer")).getStatus());
    }

    @Test void limitsAndProviderFailureHaveSafeNoncachedResponses() {
        AssistantResource resource = resource();
        for (int i = 0; i < 6; i++) {
            var response = resource.ask(body("{\"question\":\"basil light\"}"), user("Farmer"));
            assertEquals(503, response.getStatus());
            assertEquals("no-store", response.getHeaderString("Cache-Control"));
        }
        var response = resource.ask(body("{\"question\":\"basil light\"}"), user("Farmer"));
        assertEquals(429, response.getStatus());
        assertEquals("60", response.getHeaderString("Retry-After"));
    }
}
