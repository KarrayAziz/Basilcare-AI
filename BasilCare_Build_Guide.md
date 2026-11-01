# BasilCare: build Phase 0 yourself, step by step

This guide rebuilds the BasilCare repository from an empty folder. At each step it says **what to create, why, what to study in SmartHydro, and the code to write**.

How to use it:

- **Type the code, don't paste it.** Read each line as you go; the comments explain the non-obvious ones.
- SmartHydro is your **reference for ideas**, not a source of files. Each step has a *Study in SmartHydro* box: open that file, understand what it does, then write the BasilCare version shown here. The BasilCare code is deliberately simpler in places and fixes several SmartHydro weaknesses (listed in each step), so you will understand *why* it is written that way.
- **Commit after every step.** XP rule: every commit compiles.
- All commands are for **Git Bash** on Windows (it understands `mkdir -p`, `touch`, `/`).

> This guide lives outside the repository on purpose: it mentions SmartHydro, and the repository should not.

---

## Contents

0. Tools and starting point
1. Create the repository
2. `api/`: first a running "hello" API
3. `iam/`: identity service (the big one)
4. `api/`: protect endpoints with the IAM's tokens
5. Run everything together (Docker: MongoDB + WildFly + Mosquitto)
6. `pwa-farmer/` and `pwa-admin/`
7. `simulator/` and the MQTT contract
8. The other folders (`edge`, `ai-service`, `nodered`, `model`, `postman`, `deploy`, `docs`)
9. Phase 0 checklist

---

## 0. Tools and starting point

Install (or check) these:

| Tool | Check | Why |
|---|---|---|
| JDK 25 (Temurin) | `java -version` → 25 | compile the Java services |
| Maven 3.9 | `mvn -v` | build tool for `iam` and `api` |
| Git | `git --version` | version control |
| Python 3.10+ | `python --version` | simulator, edge, AI service |
| Docker Desktop | `docker version` | run MongoDB, WildFly, Mosquitto without installing them |
| VS Code or IntelliJ | | editor (VS Code: install "Extension Pack for Java" and "Live Server") |

`mvn -v` must print **Java version: 25**. If it prints 8, 17 or 21, set `JAVA_HOME` to the JDK 25 folder. (WildFly 41+ recommends Java SE 25, the current LTS.)

The folder `C:\Projet MBK\BasilCare` currently contains a finished version. Keep it as a reference to compare against and start clean:

```bash
cd "/c/Projet MBK"
mv BasilCare BasilCare-reference
mkdir BasilCare && cd BasilCare
```

Some parts of `BasilCare-reference` were written for this project and never came from SmartHydro: `docs/` (scope, diagrams, MQTT contract, user stories), `simulator/`, `deploy/`, `nodered/`, `postman/`. You may reuse or rewrite those. Everything in this guide is about building the parts yourself.

---

## 1. Create the repository

### 1.1 Folders

```bash
git init
mkdir -p iam api edge simulator nodered ai-service pwa-farmer pwa-admin model deploy postman docs
```

Git does not track empty folders, so each one needs at least one file. A README in each is the useful choice:

```bash
for d in iam api edge simulator nodered ai-service pwa-farmer pwa-admin model deploy postman docs; do
  echo "# $d" > $d/README.md
done
```

Copy your scope statement PDF into `docs/`.

### 1.2 `.gitignore` (root)

**Why:** build output, IDE settings and secrets must never be committed.

**File:** `.gitignore`
```gitignore
# Build output
target/
__pycache__/
.venv/

# IDE
.idea/
*.iml
.vscode/

# Secrets
.env
*.pem
*.key
```

### 1.3 Root `README.md`

Write it yourself: one paragraph on the project, a table of the folders, and "how to build". Update it as you go.

### 1.4 GitHub

Create an **empty** repository named `basilcare` on GitHub (no README, no license), then:

```bash
git add .
git commit -m "Create repository skeleton"
git branch -M main
git remote add origin https://github.com/<your-account>/basilcare.git
git push -u origin main
```

Add your teammates under *Settings → Collaborators*.

---

## 2. `api/`: first a running "hello" API

Start with the smallest thing that builds and runs, so you learn the Maven/WildFly cycle before writing security code.

### 2.1 Folder structure

```bash
mkdir -p api/src/main/java/tn/supcom/basilcare/boundaries
mkdir -p api/src/main/resources/META-INF
mkdir -p api/src/main/webapp/WEB-INF
```

Why these names:

- `src/main/java`, `src/main/resources`, `src/main/webapp` is the **standard Maven layout**: Maven finds code, classpath files and web files there with zero configuration. `src/test/java` will sit next to `main` for tests.
- `tn/supcom/basilcare` must match the `package` line in each Java file. A reversed domain makes the package name unique worldwide.
- `boundaries/` holds the classes that face the outside world (HTTP endpoints).

> **Alternative with a command:** `mvn archetype:generate -DarchetypeArtifactId=maven-archetype-webapp -DgroupId=tn.supcom.basilcare -DartifactId=api -DinteractiveMode=false` creates the same layout (plus an old `web.xml` you would delete). Creating it by hand is clearer the first time.

### 2.2 `pom.xml`

> **Study in SmartHydro:** `api/pom.xml`. Notice `groupId`, `artifactId`, `packaging war`, and the `jakartaee-api` dependency. Two things to do better: the API jar must be `provided` (the server already has it; otherwise it's bundled into your WAR), and the scope requires **Jakarta EE 11**, not 10.

**File:** `api/pom.xml`
```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <!-- Identity of this module: who (groupId), what (artifactId), which version -->
    <groupId>tn.supcom.basilcare</groupId>
    <artifactId>api</artifactId>
    <version>0.1.0-SNAPSHOT</version>
    <!-- war = Web ARchive, the format WildFly deploys -->
    <packaging>war</packaging>

    <properties>
        <maven.compiler.release>25</maven.compiler.release>
        <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
        <!-- we don't use the old web.xml file -->
        <failOnMissingWebXml>false</failOnMissingWebXml>
    </properties>

    <dependencies>
        <!-- All Jakarta EE 11 APIs (REST, CDI, JSON...). "provided": WildFly already has them -->
        <dependency>
            <groupId>jakarta.platform</groupId>
            <artifactId>jakarta.jakartaee-api</artifactId>
            <version>11.0.0</version>
            <scope>provided</scope>
        </dependency>
        <!-- Read settings from microprofile-config.properties / environment variables -->
        <dependency>
            <groupId>org.eclipse.microprofile.config</groupId>
            <artifactId>microprofile-config-api</artifactId>
            <version>3.1</version>
            <scope>provided</scope>
        </dependency>
    </dependencies>

    <build>
        <!-- produces target/api.war, deployed at http://host:8080/api -->
        <finalName>api</finalName>
        <plugins>
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-war-plugin</artifactId>
                <version>3.4.0</version>
            </plugin>
        </plugins>
    </build>
</project>
```

### 2.3 Activate REST

> **Study in SmartHydro:** `APIApplication.java`. An empty class with `@ApplicationPath` is all JAX-RS needs.

**File:** `api/src/main/java/tn/supcom/basilcare/ApiApplication.java`
```java
package tn.supcom.basilcare;

import jakarta.ws.rs.ApplicationPath;
import jakarta.ws.rs.core.Application;

/**
 * Turns on Jakarta REST for this WAR. The WAR is deployed under /api (its file name),
 * and "/" here means resources are directly under it: /api/health, /api/me, ...
 */
@ApplicationPath("/")
public class ApiApplication extends Application {
}
```

### 2.4 First endpoint

**File:** `api/src/main/java/tn/supcom/basilcare/boundaries/HealthResource.java`
```java
package tn.supcom.basilcare.boundaries;

import jakarta.json.Json;
import jakarta.json.JsonObject;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.MediaType;

import java.time.OffsetDateTime;

/** Public liveness check: GET /api/health. Used by the deploy script and Postman. */
@Path("health")
public class HealthResource {

    @GET
    @Produces(MediaType.APPLICATION_JSON)
    public JsonObject health() {
        return Json.createObjectBuilder()
                .add("service", "basilcare-api")
                .add("status", "UP")
                .add("time", OffsetDateTime.now().toString())
                .build();
    }
}
```

### 2.5 `beans.xml` and configuration

**File:** `api/src/main/webapp/WEB-INF/beans.xml`
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!-- Enables CDI (@Inject) for classes that carry a bean annotation such as @ApplicationScoped -->
<beans xmlns="https://jakarta.ee/xml/ns/jakartaee"
       xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
       xsi:schemaLocation="https://jakarta.ee/xml/ns/jakartaee https://jakarta.ee/xml/ns/jakartaee/beans_4_1.xsd"
       version="4.1" bean-discovery-mode="annotated">
</beans>
```

Create an empty `api/src/main/resources/META-INF/microprofile-config.properties` for now (filled in step 4).

`api/.gitignore`: one line, `target/`.

### 2.6 Build

```bash
cd api
mvn package
ls target/api.war
cd ..
```

`BUILD SUCCESS` + `target/api.war` = done. You'll run it on WildFly in step 5.

```bash
git add api && git commit -m "api: Maven skeleton with /health endpoint"
```

---

## 3. `iam/`: identity service

The IAM lets people **sign up**, **activate** their account with an e-mailed code, **sign in**, and gives the PWA a signed **access token (JWT)**. The API will trust that token without ever seeing passwords.

### 3.0 Understand the flow first

Read this until it makes sense. Everything in this step implements it.

```
PWA                                IAM                                     MongoDB
 |  1. random verifier V, challenge C = SHA256(V)                             |
 |-- 2. GET /iam/authorize?client_id&redirect_uri&code_challenge=C ---------->|
 |<------------------------------- 3. login page ------------------------------|
 |-- 4. POST /iam/login (username, password) -----------> check hash -------->|
 |<-- 5. redirect to redirect_uri?code=K   (K remembers C, 2 min, single use)  |
 |-- 6. POST /iam/oauth/token (code=K, code_verifier=V) ---------------------->|
 |      IAM checks SHA256(V) == C  -> proves the same app that started step 2 |
 |<-- 7. { access_token: JWT signed with the IAM's Ed25519 private key }      |
 |                                                                             |
 |-- 8. GET /api/me  Authorization: Bearer JWT  --> API                        |
 |      API fetches the IAM public key from /iam/jwk and checks the signature  |
```

This is **OAuth 2.0 authorization code + PKCE** (RFC 7636): the standard for browser apps, because a browser app cannot keep a secret. PKCE replaces the secret with a one-time verifier.

### 3.1 Folder structure

```bash
B=iam/src/main/java/tn/supcom/basilcare
mkdir -p $B/{boundaries,entities,repositories,security,services}
mkdir -p iam/src/main/resources/META-INF iam/src/main/webapp/WEB-INF
```

| Package | Role |
|---|---|
| `boundaries/` | HTTP endpoints (authorize, login, token, register, jwk) |
| `services/` | business rules (registration, activation, e-mail, startup data) |
| `repositories/` | database access (MongoDB) |
| `entities/` | the stored data (`Identity`, `Tenant`) |
| `security/` | cryptography (password hashing, codes, JWT) |

Each layer only calls the layer below it: boundaries → services → repositories → entities.

### 3.2 `pom.xml`

> **Study in SmartHydro:** `iam/pom.xml`. It adds Argon2 (password hashing), JNoSQL MongoDB (database), Jakarta Mail and commons-lang3. We keep Argon2 and JNoSQL. We drop the separate mail dependency (WildFly provides Jakarta Mail) and commons-lang3 (unused once you write it yourself).

**File:** `iam/pom.xml`
```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <groupId>tn.supcom.basilcare</groupId>
    <artifactId>iam</artifactId>
    <version>0.1.0-SNAPSHOT</version>
    <packaging>war</packaging>

    <properties>
        <maven.compiler.release>25</maven.compiler.release>
        <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
        <failOnMissingWebXml>false</failOnMissingWebXml>
    </properties>

    <dependencies>
        <dependency>
            <groupId>jakarta.platform</groupId>
            <artifactId>jakarta.jakartaee-api</artifactId>
            <version>11.0.0</version>
            <scope>provided</scope>
        </dependency>
        <dependency>
            <groupId>org.eclipse.microprofile.config</groupId>
            <artifactId>microprofile-config-api</artifactId>
            <version>3.1</version>
            <scope>provided</scope>
        </dependency>
        <!-- Argon2id password hashing (not provided by WildFly, so bundled in the WAR) -->
        <dependency>
            <groupId>de.mkammerer</groupId>
            <artifactId>argon2-jvm</artifactId>
            <version>2.11</version>
        </dependency>
        <!-- Jakarta NoSQL + Jakarta Data repositories on MongoDB -->
        <dependency>
            <groupId>org.eclipse.jnosql.databases</groupId>
            <artifactId>jnosql-mongodb</artifactId>
            <version>1.0.3</version>
        </dependency>
    </dependencies>

    <build>
        <finalName>iam</finalName>
        <plugins>
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-war-plugin</artifactId>
                <version>3.4.0</version>
            </plugin>
        </plugins>
    </build>
</project>
```

Copy `api/src/main/webapp/WEB-INF/beans.xml` to `iam/src/main/webapp/WEB-INF/beans.xml` (same content) and add `iam/.gitignore` with `target/`.

### 3.3 Configuration

> **Study in SmartHydro:** `iam/.../microprofile-config.properties`. Two problems to avoid: a **real SMTP password is committed** in the file, and keys are mixed with no explanation. Here, secrets are never in the file; they come from environment variables (MicroProfile Config: `smtp.password` is overridden by `SMTP_PASSWORD`).

**File:** `iam/src/main/resources/META-INF/microprofile-config.properties`
```properties
# Development defaults. Any key can be overridden by an environment variable:
# dots -> underscores, upper case. Example: jnosql.mongodb.host -> JNOSQL_MONGODB_HOST
# Secrets (smtp.username, smtp.password, admin.password) are NEVER written here.

## MongoDB
jnosql.document.database=basilcare_iam
jnosql.mongodb.host=localhost:27017
jnosql.document.provider=org.eclipse.jnosql.databases.mongodb.communication.MongoDBDocumentConfiguration

## Tokens
jwt.issuer=urn:basilcare:iam
jwt.lifetime.seconds=3600

## Argon2id cost (OWASP baseline: 64 MiB, 3 iterations)
argon2.iterations=3
argon2.memoryKb=65536
argon2.parallelism=1

## E-mail. false = activation codes are printed in the server log (handy in development)
smtp.enabled=false
smtp.host=smtp.gmail.com
smtp.port=587

## Registered client applications (OAuth "tenants") and where they may be redirected
tenant.farmer.redirect=http://localhost:5500/
tenant.admin.redirect=http://localhost:5501/

## Browser origins allowed to call the IAM from JavaScript (the two PWAs)
cors.allowed.origins=http://localhost:5500,http://localhost:5501
```

### 3.4 Entities (what is stored)

> **Study in SmartHydro:** `entities/Identity.java` and `entities/Tenant.java`. Notice `@Entity`, `@Column`, `@Id` from `jakarta.nosql`. Weaknesses to fix: `Identity.id` is never set by the code; `Tenant` has no `@Id` at all; roles are a bit mask (`Long`) that needs a 60-line enum to decode. Here the **username is the id**, the **client id is the tenant id**, and the role is a plain string.

**File:** `iam/src/main/java/tn/supcom/basilcare/entities/Role.java`
```java
package tn.supcom.basilcare.entities;

/** Application roles. The string value is what goes into the JWT "groups" claim. */
public enum Role {
    FARMER("Farmer"),
    ADMIN("Admin");

    private final String value;

    Role(String value) {
        this.value = value;
    }

    public String value() {
        return value;
    }
}
```

**File:** `iam/src/main/java/tn/supcom/basilcare/entities/Identity.java`
```java
package tn.supcom.basilcare.entities;

import jakarta.nosql.Column;
import jakarta.nosql.Entity;
import jakarta.nosql.Id;

/** A user account, stored in the MongoDB collection "identities". */
@Entity("identities")
public class Identity {

    @Id
    private String username;          // unique, so it is the document id

    @Column
    private String email;

    @Column
    private String passwordHash;      // Argon2id hash, never the password itself

    @Column
    private String role;              // "Farmer" or "Admin"

    @Column
    private boolean active;           // false until the e-mailed code is entered

    @Column
    private String activationCode;

    @Column
    private String activationExpiresAt; // ISO 8601 instant

    @Column
    private String createdAt;

    public String getUsername() { return username; }
    public void setUsername(String username) { this.username = username; }

    public String getEmail() { return email; }
    public void setEmail(String email) { this.email = email; }

    public String getPasswordHash() { return passwordHash; }
    public void setPasswordHash(String passwordHash) { this.passwordHash = passwordHash; }

    public String getRole() { return role; }
    public void setRole(String role) { this.role = role; }

    public boolean isActive() { return active; }
    public void setActive(boolean active) { this.active = active; }

    public String getActivationCode() { return activationCode; }
    public void setActivationCode(String activationCode) { this.activationCode = activationCode; }

    public String getActivationExpiresAt() { return activationExpiresAt; }
    public void setActivationExpiresAt(String activationExpiresAt) { this.activationExpiresAt = activationExpiresAt; }

    public String getCreatedAt() { return createdAt; }
    public void setCreatedAt(String createdAt) { this.createdAt = createdAt; }
}
```

**File:** `iam/src/main/java/tn/supcom/basilcare/entities/Tenant.java`
```java
package tn.supcom.basilcare.entities;

import jakarta.nosql.Column;
import jakarta.nosql.Entity;
import jakarta.nosql.Id;

/**
 * A client application allowed to use the IAM (in OAuth terms, a "client").
 * BasilCare has two: the farmer PWA and the admin PWA.
 */
@Entity("tenants")
public class Tenant {

    @Id
    private String clientId;          // e.g. "basilcare-pwa-farmer"

    @Column
    private String redirectUri;       // the only URL the IAM will send codes to

    @Column
    private String allowedRoles;      // comma-separated, e.g. "Farmer,Admin"

    public String getClientId() { return clientId; }
    public void setClientId(String clientId) { this.clientId = clientId; }

    public String getRedirectUri() { return redirectUri; }
    public void setRedirectUri(String redirectUri) { this.redirectUri = redirectUri; }

    public String getAllowedRoles() { return allowedRoles; }
    public void setAllowedRoles(String allowedRoles) { this.allowedRoles = allowedRoles; }

    public boolean allows(String role) {
        return allowedRoles != null && java.util.List.of(allowedRoles.split(",")).contains(role);
    }
}
```

### 3.5 Repositories (database access)

> **Study in SmartHydro:** `repositories/IdentityRepository.java`. A Jakarta Data repository is **just an interface**: JNoSQL writes the implementation from the method names (`findByEmail` → query on `email`). `CrudRepository` already gives `save`, `findById`, `delete`.

**File:** `iam/src/main/java/tn/supcom/basilcare/repositories/IdentityRepository.java`
```java
package tn.supcom.basilcare.repositories;

import jakarta.data.repository.CrudRepository;
import jakarta.data.repository.Repository;
import tn.supcom.basilcare.entities.Identity;

import java.util.Optional;

@Repository
public interface IdentityRepository extends CrudRepository<Identity, String> {

    // Implemented automatically from the method name
    Optional<Identity> findByEmail(String email);
}
```

**File:** `iam/src/main/java/tn/supcom/basilcare/repositories/TenantRepository.java`
```java
package tn.supcom.basilcare.repositories;

import jakarta.data.repository.CrudRepository;
import jakarta.data.repository.Repository;
import tn.supcom.basilcare.entities.Tenant;

@Repository
public interface TenantRepository extends CrudRepository<Tenant, String> {
}
```

### 3.6 Security: password hashing

> **Study in SmartHydro:** `security/Argon2Utils.java`. Good ideas to keep: Argon2**id**, and wiping the password array after use. Differences here: settings are injected with `@ConfigProperty` instead of static fields read at class-load time, and the cost uses OWASP-recommended values.

**File:** `iam/src/main/java/tn/supcom/basilcare/security/PasswordHasher.java`
```java
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
```

### 3.7 Security: authorization codes and PKCE

> **Study in SmartHydro:** `security/AuthorizationCode.java`. It packs everything into the code itself and encrypts the challenge with ChaCha20-Poly1305: clever, but 150 lines, the **expiry is never checked**, and the same code can be **used twice**. Simpler and stricter: keep codes **on the server** in a map, remove them on first use, check expiry.

**File:** `iam/src/main/java/tn/supcom/basilcare/security/AuthorizationCodeStore.java`
```java
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
```

**File:** `iam/src/main/java/tn/supcom/basilcare/security/Pkce.java`
```java
package tn.supcom.basilcare.security;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Base64;

/** PKCE S256 check (RFC 7636): BASE64URL(SHA-256(verifier)) must equal the challenge. */
public final class Pkce {

    private Pkce() {
    }

    public static boolean matches(String verifier, String challenge) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256")
                    .digest(verifier.getBytes(StandardCharsets.US_ASCII));
            String computed = Base64.getUrlEncoder().withoutPadding().encodeToString(digest);
            // constant-time comparison
            return MessageDigest.isEqual(computed.getBytes(StandardCharsets.US_ASCII),
                    challenge.getBytes(StandardCharsets.US_ASCII));
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException(e);
        }
    }
}
```

### 3.8 Security: issuing JWTs

> **Study in SmartHydro:** `security/JwtManager.java`. Keep the key ideas: **Ed25519** signatures, a `kid` (key id) in the header so verifiers know which public key to use, `iss`/`sub`/`groups`/`exp` claims, base64url encoding. Simplifications: one key pair per server start (rotation is a good later exercise), and the public key is published in the **standard JWK form for Ed25519** (`kty: "OKP"`, `x` = the 32 raw key bytes) instead of a `substring(16)` trick.

A JWT is three base64url parts joined by dots: `header.payload.signature`, where the signature covers `header.payload`.

**File:** `iam/src/main/java/tn/supcom/basilcare/security/JwtIssuer.java`
```java
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

    private static String b64(byte[] bytes) {
        return Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
    }
}
```

### 3.9 Services

> **Study in SmartHydro:** `services/IdentityServices.java` and `services/EmailService.java`. Fixes: activation codes were kept in a `HashMap` in memory (lost on restart) and never tied to the user, and login never checked that the account was activated. Here the code is **stored on the Identity**, and in development e-mails are **printed to the log** so you can test without a mail account.

**File:** `iam/src/main/java/tn/supcom/basilcare/services/Mailer.java`
```java
package tn.supcom.basilcare.services;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import jakarta.mail.Authenticator;
import jakarta.mail.Message;
import jakarta.mail.MessagingException;
import jakarta.mail.PasswordAuthentication;
import jakarta.mail.Session;
import jakarta.mail.Transport;
import jakarta.mail.internet.InternetAddress;
import jakarta.mail.internet.MimeMessage;
import org.eclipse.microprofile.config.inject.ConfigProperty;

import java.util.Optional;
import java.util.Properties;
import java.util.logging.Logger;

/** Sends e-mail through SMTP, or logs it when smtp.enabled=false (development). */
@ApplicationScoped
public class Mailer {

    private static final Logger LOG = Logger.getLogger(Mailer.class.getName());

    @Inject
    @ConfigProperty(name = "smtp.enabled")
    boolean enabled;

    @Inject
    @ConfigProperty(name = "smtp.host")
    String host;

    @Inject
    @ConfigProperty(name = "smtp.port")
    int port;

    @Inject
    @ConfigProperty(name = "smtp.username")
    Optional<String> username;   // Optional: only required when enabled

    @Inject
    @ConfigProperty(name = "smtp.password")
    Optional<String> password;

    public void send(String to, String subject, String body) {
        if (!enabled) {
            LOG.info(() -> "[mail disabled] to=" + to + " subject=" + subject + " body=" + body);
            return;
        }
        Properties props = new Properties();
        props.put("mail.smtp.host", host);
        props.put("mail.smtp.port", String.valueOf(port));
        props.put("mail.smtp.auth", "true");
        props.put("mail.smtp.starttls.enable", "true");
        Session session = Session.getInstance(props, new Authenticator() {
            @Override
            protected PasswordAuthentication getPasswordAuthentication() {
                return new PasswordAuthentication(username.orElseThrow(), password.orElseThrow());
            }
        });
        try {
            MimeMessage message = new MimeMessage(session);
            message.setFrom(new InternetAddress(username.orElseThrow()));
            message.setRecipients(Message.RecipientType.TO, InternetAddress.parse(to));
            message.setSubject(subject);
            message.setText(body);
            Transport.send(message);
        } catch (MessagingException e) {
            throw new IllegalStateException("Could not send e-mail", e);
        }
    }
}
```

**File:** `iam/src/main/java/tn/supcom/basilcare/services/RegistrationService.java`
```java
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
```

> **Study in SmartHydro:** SmartHydro has no code that creates tenants or the first admin; they had to be inserted into MongoDB by hand. The class below does it at start-up, so a fresh database just works.

**File:** `iam/src/main/java/tn/supcom/basilcare/services/StartupData.java`
```java
package tn.supcom.basilcare.services;

import jakarta.annotation.PostConstruct;
import jakarta.ejb.Singleton;
import jakarta.ejb.Startup;
import jakarta.inject.Inject;
import org.eclipse.microprofile.config.inject.ConfigProperty;
import tn.supcom.basilcare.entities.Identity;
import tn.supcom.basilcare.entities.Role;
import tn.supcom.basilcare.entities.Tenant;
import tn.supcom.basilcare.repositories.IdentityRepository;
import tn.supcom.basilcare.repositories.TenantRepository;
import tn.supcom.basilcare.security.PasswordHasher;

import java.time.OffsetDateTime;
import java.util.Optional;
import java.util.logging.Logger;

/** Creates the two PWA tenants and, if ADMIN_PASSWORD is set, the first admin account. */
@Singleton
@Startup
public class StartupData {

    private static final Logger LOG = Logger.getLogger(StartupData.class.getName());

    @Inject
    TenantRepository tenants;

    @Inject
    IdentityRepository identities;

    @Inject
    PasswordHasher hasher;

    @Inject
    @ConfigProperty(name = "tenant.farmer.redirect")
    String farmerRedirect;

    @Inject
    @ConfigProperty(name = "tenant.admin.redirect")
    String adminRedirect;

    @Inject
    @ConfigProperty(name = "admin.password")
    Optional<String> adminPassword;

    @PostConstruct
    void init() {
        // the admin may also sign in to the farmer app; farmers may not use the admin app
        saveTenant("basilcare-pwa-farmer", farmerRedirect, "Farmer,Admin");
        saveTenant("basilcare-pwa-admin", adminRedirect, "Admin");

        if (adminPassword.isPresent() && identities.findById("admin").isEmpty()) {
            Identity admin = new Identity();
            admin.setUsername("admin");
            admin.setEmail("admin@basilcare.local");
            admin.setPasswordHash(hasher.hash(adminPassword.get().toCharArray()));
            admin.setRole(Role.ADMIN.value());
            admin.setActive(true);
            admin.setCreatedAt(OffsetDateTime.now().toString());
            identities.save(admin);
            LOG.info("Created the initial 'admin' account");
        }
    }

    private void saveTenant(String clientId, String redirectUri, String roles) {
        Tenant tenant = new Tenant();
        tenant.setClientId(clientId);
        tenant.setRedirectUri(redirectUri);   // always updated from configuration
        tenant.setAllowedRoles(roles);
        tenants.save(tenant);
    }
}
```

### 3.10 Boundaries (HTTP endpoints)

**File:** `iam/src/main/java/tn/supcom/basilcare/IamApplication.java`
```java
package tn.supcom.basilcare;

import jakarta.ws.rs.ApplicationPath;
import jakarta.ws.rs.core.Application;

/** Endpoints live directly under the WAR name: /iam/authorize, /iam/oauth/token, ... */
@ApplicationPath("/")
public class IamApplication extends Application {
}
```

A small helper to return HTML pages and error pages:

**File:** `iam/src/main/java/tn/supcom/basilcare/boundaries/Pages.java`
```java
package tn.supcom.basilcare.boundaries;

import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;

/** Serves the HTML pages from src/main/resources and builds error pages. */
final class Pages {

    private Pages() {
    }

    static Response page(String name) {
        return Response.ok(Pages.class.getResourceAsStream("/" + name), MediaType.TEXT_HTML).build();
    }

    static Response error(String message) {
        String safe = message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;");
        return Response.status(Response.Status.BAD_REQUEST)
                .type(MediaType.TEXT_HTML)
                .entity("<!doctype html><meta charset=\"utf-8\"><title>BasilCare</title>"
                        + "<p style=\"font-family:sans-serif\">" + safe + "</p>")
                .build();
    }
}
```

> **Study in SmartHydro:** `bounadaries/OAuthAuthorizationEndpoint.java`. It validates the request in `authorize`, then keeps the request in a **cookie** for the login step. Here the login page simply re-posts the same query string, and `login` **validates everything again**: no state to store, and tampering gains nothing. Added checks: the account must be **active**, and the user's role must be **allowed for that app**.

**File:** `iam/src/main/java/tn/supcom/basilcare/boundaries/AuthorizationEndpoint.java`
```java
package tn.supcom.basilcare.boundaries;

import jakarta.inject.Inject;
import jakarta.ws.rs.Consumes;
import jakarta.ws.rs.FormParam;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.POST;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.QueryParam;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;
import jakarta.ws.rs.core.UriBuilder;
import tn.supcom.basilcare.entities.Identity;
import tn.supcom.basilcare.entities.Tenant;
import tn.supcom.basilcare.repositories.IdentityRepository;
import tn.supcom.basilcare.repositories.TenantRepository;
import tn.supcom.basilcare.security.AuthorizationCodeStore;
import tn.supcom.basilcare.security.PasswordHasher;

import java.time.Instant;
import java.util.Optional;

/** OAuth steps 2 to 5: show the login page, check the password, redirect back with a code. */
@Path("/")
public class AuthorizationEndpoint {

    @Inject
    TenantRepository tenants;

    @Inject
    IdentityRepository identities;

    @Inject
    PasswordHasher hasher;

    @Inject
    AuthorizationCodeStore codes;

    @GET
    @Path("authorize")
    @Produces(MediaType.TEXT_HTML)
    public Response authorize(@QueryParam("client_id") String clientId,
                              @QueryParam("redirect_uri") String redirectUri,
                              @QueryParam("response_type") String responseType,
                              @QueryParam("code_challenge") String codeChallenge,
                              @QueryParam("code_challenge_method") String challengeMethod) {
        String problem = checkRequest(clientId, redirectUri, responseType, codeChallenge, challengeMethod);
        return problem != null ? Pages.error(problem) : Pages.page("login.html");
    }

    @POST
    @Path("login")
    @Consumes(MediaType.APPLICATION_FORM_URLENCODED)
    @Produces(MediaType.TEXT_HTML)
    public Response login(@QueryParam("client_id") String clientId,
                          @QueryParam("redirect_uri") String redirectUri,
                          @QueryParam("response_type") String responseType,
                          @QueryParam("code_challenge") String codeChallenge,
                          @QueryParam("code_challenge_method") String challengeMethod,
                          @QueryParam("scope") String scope,
                          @QueryParam("state") String state,
                          @FormParam("username") String username,
                          @FormParam("password") String password) {
        String problem = checkRequest(clientId, redirectUri, responseType, codeChallenge, challengeMethod);
        if (problem != null) {
            return Pages.error(problem);
        }
        if (username == null || password == null) {
            return Pages.error("Username and password are required.");
        }
        Optional<Identity> identity = identities.findById(username);
        if (identity.isEmpty() || !hasher.verify(identity.get().getPasswordHash(), password.toCharArray())) {
            return Pages.error("Wrong username or password.");
        }
        if (!identity.get().isActive()) {
            return Pages.error("Your account is not activated yet. Enter the code you received by e-mail.");
        }
        Tenant tenant = tenants.findById(clientId).orElseThrow();
        if (!tenant.allows(identity.get().getRole())) {
            return Pages.error("Your account cannot use this application.");
        }

        String code = codes.create(new AuthorizationCodeStore.Grant(
                clientId, username, scope == null ? "" : scope, redirectUri, codeChallenge,
                Instant.now().plusSeconds(120)));
        UriBuilder target = UriBuilder.fromUri(redirectUri).queryParam("code", code);
        if (state != null) {
            target.queryParam("state", state);   // lets the PWA check the answer belongs to its request
        }
        return Response.seeOther(target.build()).build();
    }

    /** Returns an error message, or null when the request is valid. */
    private String checkRequest(String clientId, String redirectUri, String responseType,
                                String codeChallenge, String challengeMethod) {
        if (clientId == null) {
            return "client_id is missing.";
        }
        Optional<Tenant> tenant = tenants.findById(clientId);
        if (tenant.isEmpty()) {
            return "Unknown application: " + clientId;
        }
        if (!tenant.get().getRedirectUri().equals(redirectUri)) {
            return "redirect_uri does not match the one registered for this application.";
        }
        if (!"code".equals(responseType)) {
            return "response_type must be 'code'.";
        }
        if (codeChallenge == null || !"S256".equals(challengeMethod)) {
            return "PKCE is required (code_challenge with code_challenge_method=S256).";
        }
        return null;
    }
}
```

> **Study in SmartHydro:** `bounadaries/OAuthTokenEndpoint.java`. Fixes: a failed PKCE check led to `assert decoded != null` (asserts are off in production, so it crashed later); `client_id` and `redirect_uri` were not compared with the code's; the refresh-token branch reads `"tenant_id"` while tokens contain `"tenant-id"`, so it never worked. Refresh tokens are left out here (users sign in again after an hour); add them later as an exercise.

**File:** `iam/src/main/java/tn/supcom/basilcare/boundaries/TokenEndpoint.java`
```java
package tn.supcom.basilcare.boundaries;

import jakarta.inject.Inject;
import jakarta.json.Json;
import jakarta.ws.rs.Consumes;
import jakarta.ws.rs.FormParam;
import jakarta.ws.rs.POST;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;
import org.eclipse.microprofile.config.inject.ConfigProperty;
import tn.supcom.basilcare.entities.Identity;
import tn.supcom.basilcare.repositories.IdentityRepository;
import tn.supcom.basilcare.security.AuthorizationCodeStore;
import tn.supcom.basilcare.security.AuthorizationCodeStore.Grant;
import tn.supcom.basilcare.security.JwtIssuer;
import tn.supcom.basilcare.security.Pkce;

import java.util.Optional;

/** OAuth step 6-7: exchange code + PKCE verifier for an access token. */
@Path("oauth/token")
public class TokenEndpoint {

    @Inject
    AuthorizationCodeStore codes;

    @Inject
    IdentityRepository identities;

    @Inject
    JwtIssuer jwt;

    @Inject
    @ConfigProperty(name = "jwt.lifetime.seconds")
    long lifetimeSeconds;

    @POST
    @Consumes(MediaType.APPLICATION_FORM_URLENCODED)
    @Produces(MediaType.APPLICATION_JSON)
    public Response token(@FormParam("grant_type") String grantType,
                          @FormParam("code") String code,
                          @FormParam("client_id") String clientId,
                          @FormParam("redirect_uri") String redirectUri,
                          @FormParam("code_verifier") String codeVerifier) {
        if (!"authorization_code".equals(grantType)) {
            return error("unsupported_grant_type");
        }
        if (code == null || codeVerifier == null) {
            return error("invalid_request");
        }
        Optional<Grant> found = codes.consume(code);
        if (found.isEmpty()) {
            return error("invalid_grant");          // unknown, expired or already used
        }
        Grant grant = found.get();
        if (!grant.clientId().equals(clientId)
                || !grant.redirectUri().equals(redirectUri)
                || !Pkce.matches(codeVerifier, grant.codeChallenge())) {
            return error("invalid_grant");
        }
        Identity identity = identities.findById(grant.username()).orElseThrow();
        String accessToken = jwt.issue(grant.clientId(), identity.getUsername(), identity.getRole(), grant.scope());
        return Response.ok(Json.createObjectBuilder()
                        .add("access_token", accessToken)
                        .add("token_type", "Bearer")
                        .add("expires_in", lifetimeSeconds)
                        .build())
                .header("Cache-Control", "no-store")   // tokens must not be cached
                .build();
    }

    private Response error(String code) {
        return Response.status(Response.Status.BAD_REQUEST)
                .entity(Json.createObjectBuilder().add("error", code).build())
                .build();
    }
}
```

**File:** `iam/src/main/java/tn/supcom/basilcare/boundaries/JwkEndpoint.java`
```java
package tn.supcom.basilcare.boundaries;

import jakarta.inject.Inject;
import jakarta.json.JsonObject;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.MediaType;
import tn.supcom.basilcare.security.JwtIssuer;

/** GET /iam/jwk: the public key(s) other services use to verify our tokens. */
@Path("jwk")
public class JwkEndpoint {

    @Inject
    JwtIssuer jwt;

    @GET
    @Produces(MediaType.APPLICATION_JSON)
    public JsonObject keys() {
        return jwt.publicKeys();
    }
}
```

> **Study in SmartHydro:** `bounadaries/IdentityRegistration.java` (sign-up form, register, activate).

**File:** `iam/src/main/java/tn/supcom/basilcare/boundaries/RegistrationEndpoint.java`
```java
package tn.supcom.basilcare.boundaries;

import jakarta.inject.Inject;
import jakarta.ws.rs.Consumes;
import jakarta.ws.rs.FormParam;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.POST;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.QueryParam;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;
import tn.supcom.basilcare.repositories.TenantRepository;
import tn.supcom.basilcare.services.RegistrationService;

/** Sign-up: GET form, POST account, POST activation code. */
@Path("register")
public class RegistrationEndpoint {

    @Inject
    TenantRepository tenants;

    @Inject
    RegistrationService registration;

    @GET
    @Produces(MediaType.TEXT_HTML)
    public Response form(@QueryParam("client_id") String clientId) {
        if (clientId == null || tenants.findById(clientId).isEmpty()) {
            return Pages.error("Unknown application.");
        }
        return Pages.page("signup.html");
    }

    @POST
    @Consumes(MediaType.APPLICATION_FORM_URLENCODED)
    @Produces(MediaType.TEXT_HTML)
    public Response register(@FormParam("username") String username,
                             @FormParam("email") String email,
                             @FormParam("password") String password) {
        try {
            registration.register(username, email, password);
            return Pages.page("activate.html");
        } catch (IllegalArgumentException e) {
            return Pages.error(e.getMessage());
        }
    }

    @POST
    @Path("activate")
    @Consumes(MediaType.APPLICATION_FORM_URLENCODED)
    @Produces(MediaType.TEXT_HTML)
    public Response activate(@FormParam("username") String username,
                             @FormParam("code") String code) {
        try {
            registration.activate(username, code);
            return Pages.page("activated.html");
        } catch (IllegalArgumentException e) {
            return Pages.error(e.getMessage());
        }
    }
}
```

### 3.11 CORS (browser permission)

The PWA runs on `http://localhost:5500` and calls the IAM on `http://localhost:8080`: two different **origins**. Browsers block such JavaScript calls unless the server says the origin is allowed. (SmartHydro avoided this by serving everything from sub-domains of one host behind the same server; here it is explicit.)

**File:** `iam/src/main/java/tn/supcom/basilcare/boundaries/CorsFilter.java`
```java
package tn.supcom.basilcare.boundaries;

import jakarta.inject.Inject;
import jakarta.ws.rs.container.ContainerRequestContext;
import jakarta.ws.rs.container.ContainerResponseContext;
import jakarta.ws.rs.container.ContainerResponseFilter;
import jakarta.ws.rs.ext.Provider;
import org.eclipse.microprofile.config.inject.ConfigProperty;

import java.util.List;

/** Adds CORS headers for the PWA origins listed in cors.allowed.origins. */
@Provider
public class CorsFilter implements ContainerResponseFilter {

    @Inject
    @ConfigProperty(name = "cors.allowed.origins")
    List<String> allowedOrigins;

    @Override
    public void filter(ContainerRequestContext request, ContainerResponseContext response) {
        String origin = request.getHeaderString("Origin");
        if (origin != null && allowedOrigins.contains(origin)) {
            response.getHeaders().putSingle("Access-Control-Allow-Origin", origin);
            response.getHeaders().putSingle("Vary", "Origin");
            response.getHeaders().putSingle("Access-Control-Allow-Headers", "Authorization, Content-Type");
            response.getHeaders().putSingle("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS");
        }
    }
}
```

The API needs the same class in step 4 (`api/.../boundaries/CorsFilter.java`, same code).

### 3.12 HTML pages

> **Study in SmartHydro:** `iam/src/main/resources/login.html` (about 280 lines of styling). Write your own small pages first; style them later. The key trick in `login.html`: the form's `action` keeps the **query string** of the page, so the OAuth parameters travel to `POST /iam/login`.

**File:** `iam/src/main/resources/login.html`
```html
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>BasilCare - Sign in</title>
    <style>
        body { font-family: system-ui, sans-serif; background: #eef4ec; display: grid; place-items: center; min-height: 100vh; margin: 0; }
        form { background: #fff; padding: 2rem; border-radius: 12px; width: min(90vw, 340px); display: grid; gap: .8rem; }
        input, button { padding: .7rem; font-size: 1rem; border-radius: 8px; border: 1px solid #bbb; }
        button { background: #2f6b3a; color: #fff; border: 0; cursor: pointer; }
    </style>
</head>
<body>
<form id="login" method="post">
    <h1>BasilCare</h1>
    <input name="username" placeholder="Username" autocomplete="username" required>
    <input name="password" type="password" placeholder="Password" autocomplete="current-password" required>
    <button type="submit">Sign in</button>
</form>
<script>
    // Page URL: /iam/authorize?client_id=...  ->  form posts to /iam/login?client_id=...
    document.getElementById("login").action = "login" + window.location.search;
</script>
</body>
</html>
```

**File:** `iam/src/main/resources/signup.html`
```html
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>BasilCare - Sign up</title>
    <style>
        body { font-family: system-ui, sans-serif; background: #eef4ec; display: grid; place-items: center; min-height: 100vh; margin: 0; }
        form { background: #fff; padding: 2rem; border-radius: 12px; width: min(90vw, 340px); display: grid; gap: .8rem; }
        input, button { padding: .7rem; font-size: 1rem; border-radius: 8px; border: 1px solid #bbb; }
        button { background: #2f6b3a; color: #fff; border: 0; cursor: pointer; }
    </style>
</head>
<body>
<form method="post" action="register">
    <h1>Create your account</h1>
    <input name="username" placeholder="Username (lowercase)" pattern="[a-z0-9._-]{3,32}" required>
    <input name="email" type="email" placeholder="E-mail" required>
    <input name="password" type="password" placeholder="Password (10+ characters)" minlength="10" required>
    <button type="submit">Sign up</button>
</form>
</body>
</html>
```

**File:** `iam/src/main/resources/activate.html`
```html
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>BasilCare - Activate</title>
    <style>
        body { font-family: system-ui, sans-serif; background: #eef4ec; display: grid; place-items: center; min-height: 100vh; margin: 0; }
        form { background: #fff; padding: 2rem; border-radius: 12px; width: min(90vw, 340px); display: grid; gap: .8rem; }
        input, button { padding: .7rem; font-size: 1rem; border-radius: 8px; border: 1px solid #bbb; }
        button { background: #2f6b3a; color: #fff; border: 0; cursor: pointer; }
    </style>
</head>
<body>
<!-- this page is returned by POST /iam/register, so "register/activate" -> /iam/register/activate -->
<form method="post" action="register/activate">
    <h1>Check your e-mail</h1>
    <p>Enter the 6-digit code we sent you.</p>
    <input name="username" placeholder="Username" required>
    <input name="code" placeholder="123456" pattern="[0-9]{6}" inputmode="numeric" required>
    <button type="submit">Activate</button>
</form>
</body>
</html>
```

**File:** `iam/src/main/resources/activated.html`
```html
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>BasilCare - Account activated</title>
</head>
<body style="font-family: system-ui, sans-serif; text-align: center; margin-top: 20vh">
<h1>Your account is active</h1>
<p>Go back to the BasilCare app and sign in.</p>
</body>
</html>
```

### 3.13 Build

```bash
cd iam && mvn package && cd ..
```

Read every compiler error carefully: it gives the file and line. Typical first mistakes: a missing `import`, a package line that does not match the folder, a typo in a getter name.

```bash
git add iam && git commit -m "iam: OAuth 2.0 authorization code + PKCE, registration, JWT signing"
```

---

## 4. `api/`: protect endpoints with the IAM's tokens

> **Study in SmartHydro:** `api/.../security/` (5 files). The idea: a `@Secured` annotation marks protected endpoints; a **filter** runs before them, verifies the JWT with the IAM's public key, and checks `@RolesAllowed`. SmartHydro splits this into two filters, looks the verifier up through JNDI, re-downloads the key on **every request**, and rebuilds the key with manual byte reversal. Here: one filter, CDI injection, keys **cached** by `kid`, and the key rebuilt with a fixed 12-byte X.509 prefix.

```bash
mkdir -p api/src/main/java/tn/supcom/basilcare/security
```

**File:** `api/src/main/resources/META-INF/microprofile-config.properties`
```properties
# Must match the IAM's jwt.issuer
jwt.issuer=urn:basilcare:iam
# Where the public keys are published (same WildFly in development)
jwt.jwks.url=http://localhost:8080/iam/jwk
cors.allowed.origins=http://localhost:5500,http://localhost:5501
```

**File:** `api/src/main/java/tn/supcom/basilcare/security/Secured.java`
```java
package tn.supcom.basilcare.security;

import jakarta.ws.rs.NameBinding;

import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

/**
 * Put @Secured on a resource method (or class) to require a valid token.
 * @NameBinding links this annotation to SecurityFilter, which carries it too.
 */
@NameBinding
@Retention(RetentionPolicy.RUNTIME)
@Target({ElementType.TYPE, ElementType.METHOD})
public @interface Secured {
}
```

**File:** `api/src/main/java/tn/supcom/basilcare/security/JwtVerifier.java`
```java
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
```

**File:** `api/src/main/java/tn/supcom/basilcare/security/SecurityFilter.java`
```java
package tn.supcom.basilcare.security;

import jakarta.annotation.Priority;
import jakarta.annotation.security.RolesAllowed;
import jakarta.inject.Inject;
import jakarta.json.JsonObject;
import jakarta.json.JsonString;
import jakarta.ws.rs.Priorities;
import jakarta.ws.rs.container.ContainerRequestContext;
import jakarta.ws.rs.container.ContainerRequestFilter;
import jakarta.ws.rs.container.ResourceInfo;
import jakarta.ws.rs.core.Context;
import jakarta.ws.rs.core.HttpHeaders;
import jakarta.ws.rs.core.Response;
import jakarta.ws.rs.core.SecurityContext;
import jakarta.ws.rs.ext.Provider;

import java.security.Principal;
import java.util.Arrays;
import java.util.Optional;
import java.util.Set;
import java.util.stream.Collectors;

/**
 * Runs before every @Secured endpoint:
 * 401 if the token is missing or invalid, 403 if the role is not in @RolesAllowed.
 */
@Secured
@Provider
@Priority(Priorities.AUTHENTICATION)
public class SecurityFilter implements ContainerRequestFilter {

    @Inject
    JwtVerifier verifier;

    @Context
    ResourceInfo resourceInfo;

    @Override
    public void filter(ContainerRequestContext request) {
        String header = request.getHeaderString(HttpHeaders.AUTHORIZATION);
        if (header == null || !header.startsWith("Bearer ")) {
            abort(request, Response.Status.UNAUTHORIZED);
            return;
        }
        Optional<JsonObject> claims = verifier.verify(header.substring("Bearer ".length()).trim());
        if (claims.isEmpty()) {
            abort(request, Response.Status.UNAUTHORIZED);
            return;
        }
        String subject = claims.get().getString("sub");
        Set<String> roles = claims.get().getJsonArray("groups").getValuesAs(JsonString.class).stream()
                .map(JsonString::getString)
                .collect(Collectors.toSet());

        RolesAllowed allowed = resourceInfo.getResourceMethod().getAnnotation(RolesAllowed.class);
        if (allowed == null) {
            allowed = resourceInfo.getResourceClass().getAnnotation(RolesAllowed.class);
        }
        if (allowed != null && Arrays.stream(allowed.value()).noneMatch(roles::contains)) {
            abort(request, Response.Status.FORBIDDEN);
            return;
        }

        // make the caller available to resources through @Context SecurityContext
        boolean secure = request.getSecurityContext().isSecure();
        Principal principal = () -> subject;
        request.setSecurityContext(new SecurityContext() {
            @Override
            public Principal getUserPrincipal() {
                return principal;
            }

            @Override
            public boolean isUserInRole(String role) {
                return roles.contains(role);
            }

            @Override
            public boolean isSecure() {
                return secure;
            }

            @Override
            public String getAuthenticationScheme() {
                return "Bearer";
            }
        });
    }

    private void abort(ContainerRequestContext request, Response.Status status) {
        request.abortWith(Response.status(status).header(HttpHeaders.WWW_AUTHENTICATE, "Bearer").build());
    }
}
```

A protected endpoint to test the whole chain:

**File:** `api/src/main/java/tn/supcom/basilcare/boundaries/MeResource.java`
```java
package tn.supcom.basilcare.boundaries;

import jakarta.annotation.security.RolesAllowed;
import jakarta.json.Json;
import jakarta.json.JsonObject;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.Context;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.SecurityContext;
import tn.supcom.basilcare.security.Secured;

/** GET /api/me: who am I according to my token? */
@Path("me")
public class MeResource {

    @GET
    @Secured
    @RolesAllowed({"Farmer", "Admin"})
    @Produces(MediaType.APPLICATION_JSON)
    public JsonObject me(@Context SecurityContext security) {
        return Json.createObjectBuilder()
                .add("username", security.getUserPrincipal().getName())
                .add("admin", security.isUserInRole("Admin"))
                .build();
    }
}
```

Create `api/src/main/java/tn/supcom/basilcare/boundaries/CorsFilter.java` with the same code as in step 3.11 (only the `package` line is the same too, since both use `tn.supcom.basilcare.boundaries`).

```bash
cd api && mvn package && cd ..
git add api && git commit -m "api: JWT verification filter, /me endpoint, CORS"
```

---

## 5. Run everything together

You need MongoDB (for the IAM), WildFly (runs both WARs) and Mosquitto (MQTT, for step 7). Docker runs all three without installing them.

> **Study in SmartHydro:** there is no deployment file; the README only shows screenshots. This step is new.

**File:** `deploy/compose.yaml`
```yaml
# Development stack: docker compose -f deploy/compose.yaml up -d
name: basilcare

services:
  mongodb:
    image: mongo:7.0
    ports: ["27017:27017"]          # exposed so you can inspect it with MongoDB Compass
    volumes: [mongo-data:/data/db]

  mosquitto:
    image: eclipse-mosquitto:2.0.20
    command: mosquitto -c /mosquitto-no-auth.conf   # anonymous access: development only
    ports: ["1883:1883"]

  wildfly:
    image: quay.io/wildfly/wildfly:latest   # "latest" is the JDK 25 image since WildFly 41
    ports: ["8080:8080"]
    environment:
      JNOSQL_MONGODB_HOST: mongodb:27017     # overrides jnosql.mongodb.host
      ADMIN_PASSWORD: ${ADMIN_PASSWORD:-change-me-now}
    volumes:
      - ../iam/target/iam.war:/opt/jboss/wildfly/standalone/deployments/iam.war:ro
      - ../api/target/api.war:/opt/jboss/wildfly/standalone/deployments/api.war:ro
    depends_on: [mongodb]

volumes:
  mongo-data:
```

Once the stack works, pin the WildFly image to an exact version tag (the scope says WildFly 42, JDK 25 variant) instead of `latest`.

Start it:

```bash
export MSYS_NO_PATHCONV=1      # Git Bash: stop it rewriting /paths given to docker
docker compose -f deploy/compose.yaml up -d
docker compose -f deploy/compose.yaml logs -f wildfly      # wait for "Deployed iam.war" and "Deployed api.war"
```

Test, in this order:

```bash
curl http://localhost:8080/api/health          # {"service":"basilcare-api","status":"UP",...}
curl http://localhost:8080/iam/jwk             # {"keys":[{"kty":"OKP","crv":"Ed25519",...}]}
curl -i http://localhost:8080/api/me           # 401 Unauthorized: correct, no token
```

Then open in a browser:
`http://localhost:8080/iam/register?client_id=basilcare-pwa-farmer` → sign up → read the code with
`docker compose -f deploy/compose.yaml logs wildfly | grep "mail disabled"` → activate.

The full sign-in needs a PWA (step 6). After `mvn package`, restart WildFly to load the new WARs: `docker compose -f deploy/compose.yaml restart wildfly`.

**If something fails:**

| Symptom | Likely cause |
|---|---|
| `Failed to start service ... iam.war` mentioning `ConfigProperty` | a key is missing from `microprofile-config.properties` (spelling must match exactly) |
| errors about `IdentityRepository` not injectable | JNoSQL repositories not discovered: check `@Repository` and that `beans.xml` exists |
| `Connection refused` to MongoDB | `JNOSQL_MONGODB_HOST` not set, or MongoDB not started |
| `/api/me` always 401 with a fresh token | `jwt.issuer` differs between iam and api, or `jwt.jwks.url` is wrong |

```bash
git add deploy && git commit -m "deploy: development compose file"
```

---

## 6. `pwa-farmer/` and `pwa-admin/`

A PWA is a website with two extra files: a **manifest** (makes it installable) and a **service worker** (offline cache). Plain HTML/CSS/JS, no framework, no build step.

> **Study in SmartHydro:** `pwa/`. Look at how it is organised: `index.html` is the shell, `pages/` are fragments, `scripts/router.js` swaps pages without reloading, `scripts/iam.js` does PKCE, `ServiceWorker.js` caches files, `manifest.webmanifest` declares the app. The version below has the same ideas in fewer lines: a hash router (`#/dashboard`, no server configuration needed) and a shorter PKCE module.

### 6.1 Structure

```bash
cd pwa-farmer
mkdir -p pages scripts styles images
```

```
pwa-farmer/
├── index.html            the shell, loaded once
├── manifest.webmanifest  installability
├── sw.js                 service worker (must be at the root to control the whole app)
├── pages/                fragments shown inside the shell
├── scripts/app.js        router + buttons
├── scripts/auth.js       OAuth PKCE sign-in
├── styles/main.css
└── images/icon.svg
```

### 6.2 Files

**File:** `pwa-farmer/index.html`
```html
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>BasilCare Farmer</title>
    <link rel="manifest" href="manifest.webmanifest">
    <link rel="icon" href="images/icon.svg">
    <meta name="theme-color" content="#2f6b3a">
    <link rel="stylesheet" href="styles/main.css">
    <script type="module" src="scripts/app.js"></script>
</head>
<body>
<header>
    <strong>BasilCare</strong>
    <nav>
        <a href="#/">Home</a>
        <a href="#/dashboard">Dashboard</a>
        <a href="#/about">About</a>
    </nav>
    <span>
        <button id="signup">Sign up</button>
        <button id="signin">Sign in</button>
        <button id="signout" hidden>Sign out</button>
    </span>
</header>
<main id="main"></main>
</body>
</html>
```

**File:** `pwa-farmer/scripts/auth.js`
```javascript
// OAuth 2.0 authorization code + PKCE against the BasilCare IAM.
const config = {
    clientId: "basilcare-pwa-farmer",
    iam: "http://localhost:8080/iam",
    redirectUri: window.location.origin + "/",   // must equal tenant.farmer.redirect in the IAM
};

const base64url = (bytes) =>
    btoa(String.fromCharCode(...new Uint8Array(bytes)))
        .replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");

const randomString = () => base64url(crypto.getRandomValues(new Uint8Array(32)));

export async function signIn() {
    const verifier = randomString();
    const state = randomString();
    sessionStorage.setItem("pkce", JSON.stringify({ verifier, state }));
    const challenge = base64url(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier)));
    const query = new URLSearchParams({
        response_type: "code",
        client_id: config.clientId,
        redirect_uri: config.redirectUri,
        scope: "resource.read resource.write",
        state,
        code_challenge: challenge,
        code_challenge_method: "S256",
    });
    window.location.assign(`${config.iam}/authorize?${query}`);
}

export function signUp() {
    window.location.assign(`${config.iam}/register?client_id=${config.clientId}`);
}

export function signOut() {
    sessionStorage.removeItem("token");
    window.location.assign("/");
}

// Called on every page load: if the IAM sent us back with ?code=..., exchange it for a token.
export async function handleRedirect() {
    const query = new URLSearchParams(window.location.search);
    if (!query.has("code")) return;
    const saved = JSON.parse(sessionStorage.getItem("pkce") || "{}");
    sessionStorage.removeItem("pkce");
    window.history.replaceState({}, "", "/");           // remove ?code from the address bar
    if (query.get("state") !== saved.state) throw new Error("Sign-in answer does not match the request.");

    const response = await fetch(`${config.iam}/oauth/token`, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({
            grant_type: "authorization_code",
            code: query.get("code"),
            client_id: config.clientId,
            redirect_uri: config.redirectUri,
            code_verifier: saved.verifier,
        }),
    });
    if (!response.ok) throw new Error("Sign-in failed.");
    sessionStorage.setItem("token", (await response.json()).access_token);
}

// The token if present and not expired, otherwise null.
export function token() {
    const value = sessionStorage.getItem("token");
    if (!value) return null;
    const payload = JSON.parse(atob(value.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
    if (payload.exp * 1000 < Date.now()) {
        sessionStorage.removeItem("token");
        return null;
    }
    return value;
}
```

**File:** `pwa-farmer/scripts/app.js`
```javascript
import { signIn, signUp, signOut, handleRedirect, token } from "./auth.js";

const routes = {
    "/": "pages/welcome.html",
    "/dashboard": "pages/dashboard.html",
    "/about": "pages/about.html",
};
const needsSignIn = new Set(["/dashboard"]);

async function render() {
    const path = window.location.hash.slice(1) || "/";
    if (needsSignIn.has(path) && !token()) {
        window.location.hash = "#/";
        return;
    }
    const file = routes[path] ?? routes["/"];
    document.getElementById("main").innerHTML = await (await fetch(file)).text();

    const signedIn = token() !== null;
    document.getElementById("signin").hidden = signedIn;
    document.getElementById("signup").hidden = signedIn;
    document.getElementById("signout").hidden = !signedIn;

    if (path === "/dashboard") await showMe();
}

// Calls the protected API endpoint to prove the token works end to end.
async function showMe() {
    const response = await fetch("http://localhost:8080/api/me", {
        headers: { Authorization: `Bearer ${token()}` },
    });
    const me = response.ok ? await response.json() : { username: `error ${response.status}` };
    document.getElementById("who").textContent = me.username;
}

document.getElementById("signin").addEventListener("click", signIn);
document.getElementById("signup").addEventListener("click", signUp);
document.getElementById("signout").addEventListener("click", signOut);
window.addEventListener("hashchange", render);

if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js");

try {
    await handleRedirect();
} catch (e) {
    alert(e.message);
}
render();
```

**File:** `pwa-farmer/sw.js`
```javascript
// Cache the app shell so the PWA opens offline. Change the name to force an update.
const CACHE = "basilcare-farmer-v1";
const SHELL = [
    "/", "/index.html", "/styles/main.css", "/scripts/app.js", "/scripts/auth.js",
    "/pages/welcome.html", "/pages/dashboard.html", "/pages/about.html", "/images/icon.svg",
];

self.addEventListener("install", (event) => {
    event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(SHELL)));
});

self.addEventListener("activate", (event) => {
    event.waitUntil(caches.keys().then((names) =>
        Promise.all(names.filter((n) => n !== CACHE).map((n) => caches.delete(n)))));
});

// Network first (fresh data when online), cache as fallback (offline)
self.addEventListener("fetch", (event) => {
    if (event.request.method !== "GET") return;
    event.respondWith(fetch(event.request).catch(() => caches.match(event.request)));
});
```

**File:** `pwa-farmer/manifest.webmanifest`
```json
{
  "name": "BasilCare Farmer",
  "short_name": "BasilCare",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#ffffff",
  "theme_color": "#2f6b3a",
  "icons": [{ "src": "images/icon.svg", "sizes": "any", "type": "image/svg+xml" }]
}
```

**File:** `pwa-farmer/pages/welcome.html`
```html
<section>
    <h1>BasilCare</h1>
    <p>Live nutrient-solution readings, alerts and leaf screening for your hydroponic basil.</p>
</section>
```

**File:** `pwa-farmer/pages/dashboard.html`
```html
<section>
    <h1>Dashboard</h1>
    <p>Signed in as <strong id="who">...</strong></p>
    <div class="cards">
        <div class="card"><h3>pH</h3><p>&mdash;</p></div>
        <div class="card"><h3>EC</h3><p>&mdash; mS/cm</p></div>
        <div class="card"><h3>Water level</h3><p>&mdash; %</p></div>
    </div>
</section>
```

**File:** `pwa-farmer/pages/about.html`
```html
<section>
    <h1>About</h1>
    <p>Cloud of Things project, SUP'COM 2026-2027: Leith Ben Mabrouk, Aziz Karray, Amir Triki.</p>
</section>
```

**File:** `pwa-farmer/styles/main.css`
```css
body { margin: 0; font-family: system-ui, sans-serif; color: #1d3b22; background: #f6f9f5; }
header { display: flex; gap: 1rem; align-items: center; justify-content: space-between;
         padding: .8rem 1rem; background: #2f6b3a; color: #fff; flex-wrap: wrap; }
header a { color: #fff; margin-right: .8rem; text-decoration: none; }
button { padding: .4rem .9rem; border: 0; border-radius: 6px; cursor: pointer; }
main { padding: 1rem; max-width: 900px; margin: auto; }
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 1rem; }
.card { background: #fff; border-radius: 10px; padding: 1rem; box-shadow: 0 1px 4px #0002; }
```

**File:** `pwa-farmer/images/icon.svg`
```html
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect width="64" height="64" rx="14" fill="#2f6b3a"/>
  <path d="M32 50c-10-6-14-16-10-28 12 2 18 12 10 28z" fill="#9ad18b"/>
</svg>
```

### 6.3 Test the full sign-in

```bash
python -m http.server 5500       # inside pwa-farmer/
```

Open `http://localhost:5500` → *Sign in* → IAM login page → sign in with the account activated in step 5 → back on the PWA → *Dashboard* shows your username, which came from `GET /api/me` with your token. **That is the end-to-end proof that IAM and API work together.**

### 6.4 `pwa-admin/`

Same files, with these changes:

| File | Change |
|---|---|
| `scripts/auth.js` | `clientId: "basilcare-pwa-admin"` |
| `manifest.webmanifest` | name "BasilCare Admin" |
| `sw.js` | cache name `basilcare-admin-v1` |
| `pages/` | admin content (users, devices, thresholds, incidents) |

Serve it on port **5501** (`python -m http.server 5501`) and sign in with `admin` / the `ADMIN_PASSWORD` from the compose file. A farmer account must be **refused** by the IAM ("Your account cannot use this application"): test it.

```bash
git add pwa-farmer pwa-admin && git commit -m "PWAs: shell, router, PKCE sign-in, service worker"
```

---

## 7. `simulator/` and the MQTT contract

SmartHydro has no simulator or topic table, so this step is new.

### 7.1 Write the contract first: `docs/mqtt-contract.md`

Decide and write down, as a table:

- topic pattern: `basilcare/v1/{device_id}/telemetry/{sensor}`, plus `status`, `pump/cmd`, `pump/state`, `screening`;
- sensor names and units: `air_temperature` (degC), `air_humidity` (%RH), `ph` (pH), `ec` (mS/cm), `water_temperature` (degC), `water_level` (%);
- Reading payload fields: `device_id`, `sensor`, `value`, `unit`, `measured_at` (ISO 8601 with offset, e.g. `2026-11-02T14:05:00+01:00`), `calibrated` (true/false), plus `seq` and `buffered` (useful after network outages);
- QoS 1 for everything, `status` retained with a Last Will `online:false`.

### 7.2 Write the simulator: `simulator/simulator.py`

```bash
cd simulator
python -m venv .venv && source .venv/Scripts/activate
pip install paho-mqtt==2.1.0
pip freeze > requirements.txt
```

Write it yourself; aim for about 50 lines. Structure:

1. `argparse` options: `--host`, `--port`, `--device`, `--interval`, `--count`, `--fault {none,ph-drift,stale,pump-failure}`.
2. A dictionary `sensor -> (unit, nominal value, noise)`.
3. `mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=...)`, `will_set(...)` on the status topic, `connect`, `loop_start`.
4. Loop: for each sensor, `value = nominal + random.gauss(0, noise)`; apply the fault (`ph-drift`: add `0.08 * cycle` to pH; `stale`: skip telemetry after 3 cycles; `pump-failure`: pump state `fault` from cycle 2); build the dict; `publish(topic, json.dumps(msg), qos=1)`.
5. Timestamps: `datetime.now().astimezone().isoformat(timespec="seconds")` gives the `+01:00` offset.

Test against the Mosquitto container from step 5:

```bash
docker exec -it basilcare-mosquitto-1 mosquitto_sub -t 'basilcare/v1/#' -v    # terminal 1
python simulator.py --fault ph-drift --interval 1 --count 10                    # terminal 2
```

(Container name: check with `docker ps`.) Seeing the messages in terminal 1 is the Phase 0 "done" criterion.

```bash
git add simulator docs && git commit -m "simulator and MQTT contract"
```

---

## 8. The other folders

| Folder | What to put in Phase 0 | How |
|---|---|---|
| `edge/` | README describing the planned modules (sensors, camera, queue, pump guard, publisher); `basilcare_edge/__init__.py`; `requirements.txt` | by hand |
| `ai-service/` | README; empty `rag/`, `mcp/`, `evaluation/` (add a `.gitkeep` file in each so Git keeps them) | by hand |
| `model/` | README; `weights/`, `evaluation-images/` with `.gitkeep` | by hand |
| `nodered/` | `flows.json` with one *mqtt in* node on `basilcare/v1/+/#` wired to a *debug* node | add a `nodered/node-red:4.0.9` service to the compose file, build the flow in the editor at `http://localhost:1880`, then *Menu → Export → All flows* into `flows.json` |
| `postman/` | collection with `GET /api/health`, `GET /api/me` (Bearer token), `GET /iam/jwk` | build the requests in Postman, then *Export* (format v2.1) |
| `deploy/` | `compose.yaml` (done), `.env.example` (list of variables with fake values), `setup.sh` (install Docker/JDK/Maven on the VM, `git clone`), `deploy.sh` (`git pull`, `mvn package`, `docker compose up -d`, check `/api/health`) | by hand |
| `docs/` | scope PDF, `mqtt-contract.md`, user stories, UML diagrams, design statement PDF | user stories: one GitHub issue per story; diagrams: write PlantUML (`.puml`) text files and render them with the PlantUML jar or the VS Code "PlantUML" extension |

Then fill in every folder README with three parts: **what the folder does**, **why it is organised that way**, **how it works**.

---

## 9. Phase 0 checklist

- [ ] Repository on GitHub with the 12 folders, each with a README
- [ ] `mvn package` succeeds in `iam/` and in `api/`
- [ ] `curl localhost:8080/api/health` answers `UP`
- [ ] Sign up → activation code in the log → activate → sign in from the farmer PWA → dashboard shows your username from `/api/me`
- [ ] A farmer account is refused by the admin PWA
- [ ] `simulator.py` messages visible with `mosquitto_sub`
- [ ] `docs/mqtt-contract.md` written
- [ ] User stories in GitHub Issues, estimated
- [ ] Design statement PDF (use case, class, deployment, 3 sequence diagrams)
- [ ] No secret in Git: `git grep -i password` shows only placeholders
