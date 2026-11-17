package tn.supcom.basilcare.services;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import tn.supcom.basilcare.entities.Identity;
import tn.supcom.basilcare.entities.Role;
import tn.supcom.basilcare.repositories.IdentityRepository;
import tn.supcom.basilcare.security.PasswordHasher;

import java.security.SecureRandom;
import java.time.Instant;
import java.time.OffsetDateTime;
import java.time.temporal.ChronoUnit;

/** Sign-up and account activation rules. Throws IllegalArgumentException with a user-readable message. */
@ApplicationScoped
public class RegistrationService {

    @Inject
    IdentityRepository identities;

    @Inject
    PasswordHasher hasher;

    @Inject
    Mailer mailer;

    private final SecureRandom random = new SecureRandom();

    public void register(String username, String email, String password) {
        if (username == null || !username.matches("[a-z0-9._-]{3,32}")) {
            throw new IllegalArgumentException("Username: 3 to 32 characters, lowercase letters, digits, . _ -");
        }
        if (email == null || !email.matches("[^@\\s]+@[^@\\s]+\\.[^@\\s]+")) {
            throw new IllegalArgumentException("Please enter a valid e-mail address.");
        }
        if (password == null || password.length() < 10) {
            throw new IllegalArgumentException("Password: at least 10 characters.");
        }
        if (identities.findById(username).isPresent()) {
            throw new IllegalArgumentException("This username is already taken.");
        }
        if (identities.findByEmail(email).isPresent()) {
            throw new IllegalArgumentException("This e-mail is already registered.");
        }

        String code = String.format("%06d", random.nextInt(1_000_000));
        Identity identity = new Identity();
        identity.setUsername(username);
        identity.setEmail(email);
        identity.setPasswordHash(hasher.hash(password.toCharArray()));
        identity.setRole(Role.FARMER.value());                 // every sign-up is a farmer
        identity.setActive(false);
        identity.setActivationCode(code);
        identity.setActivationExpiresAt(Instant.now().plus(15, ChronoUnit.MINUTES).toString());
        identity.setCreatedAt(OffsetDateTime.now().toString());
        identities.save(identity);

        mailer.send(email, "BasilCare activation code",
                "Your BasilCare activation code is " + code + " (valid 15 minutes).");
    }

    public void activate(String username, String code) {
        Identity identity = identities.findById(username)
                .orElseThrow(() -> new IllegalArgumentException("Unknown username."));
        if (identity.isActive()) {
            return;
        }
        boolean expired = Instant.now().isAfter(Instant.parse(identity.getActivationExpiresAt()));
        if (code == null || !code.equals(identity.getActivationCode()) || expired) {
            throw new IllegalArgumentException("Wrong or expired code.");
        }
        identity.setActive(true);
        identity.setActivationCode(null);
        identities.save(identity);
    }
}