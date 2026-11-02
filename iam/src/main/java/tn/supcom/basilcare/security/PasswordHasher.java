package tn.supcom.basilcare.security;

import de.mkammerer.argon2.Argon2;
import de.mkammerer.argon2.Argon2Factory;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import org.eclipse.microprofile.config.inject.ConfigProperty;

/**
 * Hashes and checks passwords with Argon2id. The hash string contains the salt
 * and the parameters, so verify() needs nothing else.
 */
@ApplicationScoped
public class PasswordHasher {

    private final Argon2 argon2 = Argon2Factory.create(Argon2Factory.Argon2Types.ARGON2id);

    @Inject
    @ConfigProperty(name = "argon2.iterations")
    int iterations;

    @Inject
    @ConfigProperty(name = "argon2.memoryKb")
    int memoryKb;

    @Inject
    @ConfigProperty(name = "argon2.parallelism")
    int parallelism;

    public String hash(char[] password) {
        try {
            return argon2.hash(iterations, memoryKb, parallelism, password);
        } finally {
            argon2.wipeArray(password); // don't leave the password in memory
        }
    }

    public boolean verify(String hash, char[] password) {
        try {
            return argon2.verify(hash, password);
        } finally {
            argon2.wipeArray(password);
        }
    }
}