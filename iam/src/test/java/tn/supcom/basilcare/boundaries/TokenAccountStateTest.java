package tn.supcom.basilcare.boundaries;

import jakarta.json.JsonObject;
import org.junit.jupiter.api.Test;
import tn.supcom.basilcare.entities.Identity;
import tn.supcom.basilcare.repositories.IdentityRepository;
import tn.supcom.basilcare.security.AuthorizationCodeStore;

import java.lang.reflect.Proxy;
import java.time.Instant;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;

class TokenAccountStateTest {
    @Test void deletedAccountCannotExchangeItsPendingLoginCode() {
        rejected(Optional.empty());
    }

    @Test void disabledAccountCannotExchangeItsPendingLoginCode() {
        Identity identity = new Identity();
        identity.setUsername("admin");
        identity.setActive(false);
        rejected(Optional.of(identity));
    }

    private void rejected(Optional<Identity> account) {
        TokenEndpoint endpoint = new TokenEndpoint();
        endpoint.codes = new AuthorizationCodeStore();
        endpoint.identities = (IdentityRepository) Proxy.newProxyInstance(
                IdentityRepository.class.getClassLoader(), new Class<?>[]{IdentityRepository.class},
                (proxy, method, args) -> {
                    if (method.getName().equals("findById")) return account;
                    throw new UnsupportedOperationException(method.getName());
                });
        // RFC 7636 example verifier and corresponding S256 challenge.
        String verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk";
        String code = endpoint.codes.create(new AuthorizationCodeStore.Grant(
                "basilcare-pwa-admin", "admin", "", "http://localhost:5501/",
                "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM", Instant.now().plusSeconds(120)));
        var response = endpoint.token("authorization_code", code, "basilcare-pwa-admin",
                "http://localhost:5501/", verifier);
        assertEquals(400, response.getStatus());
        assertEquals("invalid_grant", ((JsonObject) response.getEntity()).getString("error"));
        assertTrue(endpoint.codes.consume(code).isEmpty());
    }
}
