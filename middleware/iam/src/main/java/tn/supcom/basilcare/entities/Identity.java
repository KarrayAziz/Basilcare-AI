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