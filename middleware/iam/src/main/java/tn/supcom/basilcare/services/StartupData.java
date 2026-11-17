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