package tn.supcom.basilcare.services;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import tn.supcom.basilcare.entities.Identity;
import tn.supcom.basilcare.repositories.IdentityRepository;
import tn.supcom.basilcare.services.AccountManagementService.AccountProblem;

import java.lang.reflect.Proxy;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;

class AccountManagementServiceTest {
    Map<String, Identity> stored;
    AccountManagementService service;

    @BeforeEach
    void setup() {
        stored = new LinkedHashMap<>();
        add("admin", "Admin", true);
        add("farmer", "Farmer", true);
        service = new AccountManagementService();
        service.identities = (IdentityRepository) Proxy.newProxyInstance(
                IdentityRepository.class.getClassLoader(), new Class<?>[]{IdentityRepository.class},
                (proxy, method, args) -> switch (method.getName()) {
                    case "findById" -> Optional.ofNullable(stored.get(args[0]));
                    case "findAll" -> stored.values().stream();
                    case "delete" -> { stored.remove(((Identity) args[0]).getUsername()); yield null; }
                    case "save" -> { Identity user = (Identity) args[0]; stored.put(user.getUsername(), user); yield user; }
                    default -> throw new UnsupportedOperationException(method.getName());
                });
    }

    @Test void lastAdminCannotDeleteSelf() {
        rejected(409, "last_active_admin", () -> service.delete("admin", "admin"));
        assertTrue(stored.containsKey("admin"));
    }

    @Test void lastAdminCannotBeDisabledOrDemoted() {
        rejected(409, "last_active_admin", () -> service.update("admin", "admin", null, false));
        rejected(409, "last_active_admin", () -> service.update("admin", "admin", "Farmer", null));
        assertTrue(stored.get("admin").isActive());
        assertEquals("Admin", stored.get("admin").getRole());
    }

    @Test void inactiveAdminsDoNotCountAsReplacements() {
        add("inactive", "Admin", false);
        rejected(409, "last_active_admin", () -> service.delete("admin", "admin"));
    }

    @Test void adminMayDeleteSelfWhenAnotherActiveAdminExists() {
        add("second", "Admin", true);
        service.delete("admin", "admin");
        assertFalse(stored.containsKey("admin"));
        assertTrue(stored.get("second").isActive());
    }

    @Test void successiveRemovalsCannotRemoveBothAdmins() {
        add("second", "Admin", true);
        service.update("admin", "second", "Farmer", false);
        rejected(409, "last_active_admin", () -> service.delete("admin", "admin"));
    }

    @Test void farmerCanBeDeletedWithoutRemovingAdmin() {
        service.delete("admin", "farmer");
        assertFalse(stored.containsKey("farmer"));
        assertTrue(stored.containsKey("admin"));
    }

    @Test void liveRoleAndActivationAreCheckedForEveryMutation() {
        rejected(403, "admin_required", () -> service.delete("farmer", "admin"));
        stored.get("admin").setActive(false);
        rejected(403, "admin_required", () -> service.delete("admin", "farmer"));
        rejected(403, "admin_required", () -> service.delete("missing", "farmer"));
    }

    @Test void administratorCanBePromotedAndDemoted() {
        service.update("admin", "farmer", "Admin", null);
        service.update("farmer", "admin", "Farmer", null);
        assertEquals("Admin", stored.get("farmer").getRole());
        assertEquals("Farmer", stored.get("admin").getRole());
        rejected(403, "admin_required", () -> service.delete("admin", "farmer"));
    }

    @Test void invalidUpdatesAndUnknownAccountsAreRejected() {
        rejected(400, "invalid_role", () -> service.update("admin", "farmer", "SuperAdmin", null));
        rejected(400, "invalid_update", () -> service.update("admin", "farmer", null, null));
        rejected(404, "account_not_found", () -> service.delete("admin", "missing"));
    }

    @Test void activationCannotBypassEmailVerification() {
        Identity pending = add("pending", "Farmer", false);
        pending.setActivationCode("123456");
        rejected(409, "activation_required", () -> service.update("admin", "pending", "Admin", true));
        assertFalse(pending.isActive());
        assertEquals("Farmer", pending.getRole());
    }

    private Identity add(String username, String role, boolean active) {
        Identity identity = new Identity();
        identity.setUsername(username);
        identity.setRole(role);
        identity.setActive(active);
        stored.put(username, identity);
        return identity;
    }

    private void rejected(int status, String code, Runnable operation) {
        AccountProblem problem = assertThrows(AccountProblem.class, operation::run);
        assertEquals(status, problem.status);
        assertEquals(code, problem.code);
    }
}
