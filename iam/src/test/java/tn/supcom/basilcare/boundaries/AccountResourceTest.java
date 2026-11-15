package tn.supcom.basilcare.boundaries;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import jakarta.json.JsonObject;
import tn.supcom.basilcare.security.JwtIssuer;
import tn.supcom.basilcare.services.AccountManagementService;

import java.util.Optional;
import static org.junit.jupiter.api.Assertions.*;

/** Direct resource tests with real REST response building; not a deployed HTTP test. */
class AccountResourceTest {
    AccountResource resource;
    boolean called;

    @BeforeEach void setup() {
        resource = new AccountResource();
        resource.jwt = new JwtIssuer() {
            @Override public Optional<String> adminSubject(String token) {
                return "valid".equals(token) ? Optional.of("admin") : Optional.empty();
            }
        };
        resource.accounts = new AccountManagementService() {
            @Override public void delete(String actor, String username) {
                called = true;
                assertEquals("admin", actor);
                if ("admin".equals(username)) {
                    throw new AccountProblem(409, "last_active_admin", "Last administrator.");
                }
            }
            @Override public void update(String actor, String username, String role, Boolean active) {
                called = true;
                assertEquals("admin", actor);
                assertEquals("farmer", username);
                assertNull(role);
                assertEquals(Boolean.FALSE, active);
            }
        };
    }

    @Test void missingAndInvalidTokensNeverReachTheService() {
        assertEquals(401, resource.delete(null, "admin").getStatus());
        var response = resource.delete("Bearer bad", "admin");
        assertEquals(401, response.getStatus());
        assertEquals("Bearer", response.getHeaderString("WWW-Authenticate"));
        assertFalse(called);
    }

    @Test void conflictIsReturnedAsJson() {
        var response = resource.delete("Bearer valid", "admin");
        assertEquals(409, response.getStatus());
        assertEquals("last_active_admin", ((JsonObject) response.getEntity()).getString("error"));
    }

    @Test void successfulDeletionHasNoResponseBody() {
        var response = resource.delete("Bearer valid", "farmer");
        assertEquals(204, response.getStatus());
        assertNull(response.getEntity());
        assertTrue(called);
    }

    @Test void patchForwardsOnlySuppliedProperties() {
        AccountResource.Update update = new AccountResource.Update();
        update.setActive(false);
        assertEquals(204, resource.update("Bearer valid", "farmer", update).getStatus());
        assertTrue(called);
    }

    @Test void missingBodyIsBadRequest() {
        assertEquals(400, resource.update("Bearer valid", "farmer", null).getStatus());
        assertFalse(called);
    }
}
