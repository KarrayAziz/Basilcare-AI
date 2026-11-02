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