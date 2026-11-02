package tn.supcom.basilcare.security;

import jakarta.enterprise.context.ApplicationScoped;

import java.security.SecureRandom;
import java.time.Instant;
import java.util.Base64;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Short-lived, single-use authorization codes (OAuth step 5 -> step 6).
 * Kept in memory: a restart only forces users to sign in again.
 */
@ApplicationScoped
public class AuthorizationCodeStore {

    /** What the code stands for. */
    public record Grant(String clientId, String username, String scope,
                        String redirectUri, String codeChallenge, Instant expiresAt) {
    }

    private final Map<String, Grant> codes = new ConcurrentHashMap<>();
    private final SecureRandom random = new SecureRandom();

    public String create(Grant grant) {
        codes.values().removeIf(g -> Instant.now().isAfter(g.expiresAt())); // housekeeping
        byte[] bytes = new byte[32];
        random.nextBytes(bytes);
        String code = Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
        codes.put(code, grant);
        return code;
    }

    /** Returns the grant and deletes it, so a code can never be used twice. */
    public Optional<Grant> consume(String code) {
        Grant grant = codes.remove(code);
        if (grant == null || Instant.now().isAfter(grant.expiresAt())) {
            return Optional.empty();
        }
        return Optional.of(grant);
    }
}