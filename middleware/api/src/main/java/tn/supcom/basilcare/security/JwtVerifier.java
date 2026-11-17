package tn.supcom.basilcare.security;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import jakarta.json.Json;
import jakarta.json.JsonObject;
import org.eclipse.microprofile.config.inject.ConfigProperty;

import java.io.IOException;
import java.io.StringReader;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.GeneralSecurityException;
import java.security.KeyFactory;
import java.security.PublicKey;
import java.security.Signature;
import java.security.spec.X509EncodedKeySpec;
import java.time.Instant;
import java.util.Base64;
import java.util.HexFormat;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;

/** Verifies tokens signed by the IAM. Public keys are fetched once per kid and cached. */
@ApplicationScoped
public class JwtVerifier {

    // DER header that turns 32 raw Ed25519 key bytes into a standard X.509 public key
    private static final byte[] ED25519_X509_PREFIX = HexFormat.of().parseHex("302a300506032b6570032100");

    @Inject
    @ConfigProperty(name = "jwt.issuer")
    String issuer;

    @Inject
    @ConfigProperty(name = "jwt.jwks.url")
    String jwksUrl;

    private final Map<String, PublicKey> keys = new ConcurrentHashMap<>();
    private final HttpClient http = HttpClient.newHttpClient();

    /** Returns the token's claims if signature, issuer and expiry are valid. */
    public Optional<JsonObject> verify(String token) {
        String[] parts = token.split("\\.");
        if (parts.length != 3) {
            return Optional.empty();
        }
        try {
            JsonObject header = decode(parts[0]);
            PublicKey key = key(header.getString("kid", ""));
            if (key == null) {
                return Optional.empty();
            }
            Signature verifier = Signature.getInstance("Ed25519");
            verifier.initVerify(key);
            verifier.update((parts[0] + "." + parts[1]).getBytes(StandardCharsets.US_ASCII));
            if (!verifier.verify(Base64.getUrlDecoder().decode(parts[2]))) {
                return Optional.empty();
            }
            JsonObject claims = decode(parts[1]);
            if (!issuer.equals(claims.getString("iss", ""))
                    || claims.getJsonNumber("exp").longValue() < Instant.now().getEpochSecond()) {
                return Optional.empty();
            }
            return Optional.of(claims);
        } catch (RuntimeException | GeneralSecurityException e) {
            return Optional.empty();   // any malformed token is simply rejected
        }
    }

    private PublicKey key(String kid) throws GeneralSecurityException {
        PublicKey key = keys.get(kid);
        if (key == null) {          // unknown kid: the IAM may have restarted with a new key
            refreshKeys();
            key = keys.get(kid);
        }
        return key;
    }

    private void refreshKeys() throws GeneralSecurityException {
        try {
            HttpResponse<String> response = http.send(
                    HttpRequest.newBuilder(URI.create(jwksUrl)).build(), HttpResponse.BodyHandlers.ofString());
            KeyFactory factory = KeyFactory.getInstance("Ed25519");
            JsonObject jwks = Json.createReader(new StringReader(response.body())).readObject();
            for (JsonObject jwk : jwks.getJsonArray("keys").getValuesAs(JsonObject.class)) {
                byte[] raw = Base64.getUrlDecoder().decode(jwk.getString("x"));
                byte[] x509 = ByteBuffer.allocate(ED25519_X509_PREFIX.length + raw.length)
                        .put(ED25519_X509_PREFIX).put(raw).array();
                keys.put(jwk.getString("kid"), factory.generatePublic(new X509EncodedKeySpec(x509)));
            }
        } catch (IOException e) {
            throw new GeneralSecurityException("Cannot reach " + jwksUrl, e);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new GeneralSecurityException(e);
        }
    }

    private static JsonObject decode(String part) {
        String json = new String(Base64.getUrlDecoder().decode(part), StandardCharsets.UTF_8);
        return Json.createReader(new StringReader(json)).readObject();
    }
}