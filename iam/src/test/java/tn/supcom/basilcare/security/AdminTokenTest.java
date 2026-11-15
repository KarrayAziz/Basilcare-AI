package tn.supcom.basilcare.security;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import java.util.Optional;
import static org.junit.jupiter.api.Assertions.*;

class AdminTokenTest {
    JwtIssuer jwt;

    @BeforeEach void setup() {
        jwt = new JwtIssuer();
        jwt.issuer = "urn:basilcare:iam";
        jwt.lifetimeSeconds = 3600;
        jwt.generateKey();
    }

    @Test void acceptsAdminClientToken() {
        assertEquals(Optional.of("admin"), jwt.adminSubject(
                jwt.issue("basilcare-pwa-admin", "admin", "Admin", "")));
    }

    @Test void rejectsFarmerRoleAndWrongClient() {
        assertTrue(jwt.adminSubject(jwt.issue("basilcare-pwa-admin", "farmer", "Farmer", "")).isEmpty());
        assertTrue(jwt.adminSubject(jwt.issue("basilcare-pwa-farmer", "admin", "Admin", "")).isEmpty());
    }

    @Test void rejectsExpiredMalformedAndForeignTokens() {
        jwt.lifetimeSeconds = -1;
        assertTrue(jwt.adminSubject(jwt.issue("basilcare-pwa-admin", "admin", "Admin", "")).isEmpty());
        assertTrue(jwt.adminSubject("not-a-token").isEmpty());
        assertTrue(jwt.adminSubject(null).isEmpty());
        jwt.lifetimeSeconds = 3600;
        String token = jwt.issue("basilcare-pwa-admin", "admin", "Admin", "");
        jwt.generateKey();
        assertTrue(jwt.adminSubject(token).isEmpty());
    }

    @Test void rejectsTamperedSignature() {
        String token = jwt.issue("basilcare-pwa-admin", "admin", "Admin", "");
        int start = token.lastIndexOf('.') + 1;
        String tampered = token.substring(0, start) + (token.charAt(start) == 'A' ? "B" : "A")
                + token.substring(start + 1);
        assertTrue(jwt.adminSubject(tampered).isEmpty());
    }
}
