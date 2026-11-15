package tn.supcom.basilcare.security;

import jakarta.annotation.PostConstruct;
import jakarta.ejb.Singleton;
import jakarta.ejb.Startup;
import jakarta.inject.Inject;
import jakarta.json.Json;
import jakarta.json.JsonObject;
import org.eclipse.microprofile.config.inject.ConfigProperty;

import java.nio.charset.StandardCharsets;
import java.security.GeneralSecurityException;
import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.security.Signature;
import java.time.Instant;
import java.util.Arrays;
import java.util.Base64;
import java.util.UUID;
import java.util.Optional;
import java.io.StringReader;

/**
 * Creates and signs access tokens. @Singleton + @Startup: one instance, created when
 * the application starts, and the container serialises calls (thread safe).
 */
@Singleton
@Startup
public class JwtIssuer {

    @Inject
    @ConfigProperty(name = "jwt.issuer")
    String issuer;

    @Inject
    @ConfigProperty(name = "jwt.lifetime.seconds")
    long lifetimeSeconds;

    private KeyPair keyPair;
    private String kid;

    @PostConstruct
    void generateKey() {
        try {
            keyPair = KeyPairGenerator.getInstance("Ed25519").generateKeyPair();
            kid = UUID.randomUUID().toString();
        } catch (GeneralSecurityException e) {
            throw new IllegalStateException(e);
        }
    }

    public String issue(String clientId, String subject, String role, String scope) {
        long now = Instant.now().getEpochSecond();
        String header = Json.createObjectBuilder()
                .add("alg", "EdDSA")
                .add("typ", "JWT")
                .add("kid", kid)
                .build().toString();
        String payload = Json.createObjectBuilder()
                .add("iss", issuer)
                .add("sub", subject)
                .add("aud", clientId)
                .add("groups", Json.createArrayBuilder().add(role))
                .add("scope", scope)
                .add("iat", now)
                .add("exp", now + lifetimeSeconds)
                .add("jti", UUID.randomUUID().toString())
                .build().toString();
        String signingInput = b64(header.getBytes(StandardCharsets.UTF_8)) + "."
                + b64(payload.getBytes(StandardCharsets.UTF_8));
        try {
            Signature signer = Signature.getInstance("Ed25519");
            signer.initSign(keyPair.getPrivate());
            signer.update(signingInput.getBytes(StandardCharsets.US_ASCII));
            return signingInput + "." + b64(signer.sign());
        } catch (GeneralSecurityException e) {
            throw new IllegalStateException(e);
        }
    }

    /** Public key set in JWKS format, served at GET /iam/jwk. */
    public JsonObject publicKeys() {
        byte[] x509 = keyPair.getPublic().getEncoded();                       // 12-byte header + 32-byte key
        byte[] raw = Arrays.copyOfRange(x509, x509.length - 32, x509.length);
        JsonObject jwk = Json.createObjectBuilder()
                .add("kty", "OKP")
                .add("crv", "Ed25519")
                .add("kid", kid)
                .add("use", "sig")
                .add("x", b64(raw))
                .build();
        return Json.createObjectBuilder().add("keys", Json.createArrayBuilder().add(jwk)).build();
    }

    /** Verify an Admin PWA access token before allowing account-management requests. */
    public Optional<String> adminSubject(String token) {
        try {
            String[] parts = token.split("\\.", -1);
            if (parts.length != 3) return Optional.empty();
            JsonObject header = decode(parts[0]);
            if (!"EdDSA".equals(header.getString("alg", ""))
                    || !kid.equals(header.getString("kid", ""))) return Optional.empty();
            Signature verifier = Signature.getInstance("Ed25519");
            verifier.initVerify(keyPair.getPublic());
            verifier.update((parts[0] + "." + parts[1]).getBytes(StandardCharsets.US_ASCII));
            if (!verifier.verify(Base64.getUrlDecoder().decode(parts[2]))) return Optional.empty();
            JsonObject claims = decode(parts[1]);
            if (!issuer.equals(claims.getString("iss", ""))
                    || !"basilcare-pwa-admin".equals(claims.getString("aud", ""))
                    || claims.getJsonNumber("exp").longValue() <= Instant.now().getEpochSecond()
                    || !claims.getJsonArray("groups").contains(Json.createValue("Admin"))) {
                return Optional.empty();
            }
            String subject = claims.getString("sub");
            return subject.isBlank() ? Optional.empty() : Optional.of(subject);
        } catch (RuntimeException | GeneralSecurityException exception) {
            return Optional.empty();
        }
    }

    private static JsonObject decode(String part) {
        try (var reader = Json.createReader(new StringReader(
                new String(Base64.getUrlDecoder().decode(part), StandardCharsets.UTF_8)))) {
            return reader.readObject();
        }
    }

    private static String b64(byte[] bytes) {
        return Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
    }
}
