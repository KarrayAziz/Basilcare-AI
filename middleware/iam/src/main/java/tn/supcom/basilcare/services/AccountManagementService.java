package tn.supcom.basilcare.services;

import jakarta.ejb.ApplicationException;
import jakarta.ejb.Lock;
import jakarta.ejb.LockType;
import jakarta.ejb.Singleton;
import jakarta.inject.Inject;
import tn.supcom.basilcare.entities.Identity;
import tn.supcom.basilcare.repositories.IdentityRepository;

/** Serializes account mutations on the single IAM instance, including the guard and write. */
@Singleton
@Lock(LockType.WRITE)
public class AccountManagementService {
    @Inject
    IdentityRepository identities;

    @ApplicationException
    public static class AccountProblem extends RuntimeException {
        public final int status;
        public final String code;

        public AccountProblem(int status, String code, String message) {
            super(message);
            this.status = status;
            this.code = code;
        }
    }

    public void delete(String actor, String username) {
        requireAdmin(actor);
        Identity target = find(username);
        protectLastAdmin(target, false);
        identities.delete(target);
    }

    /** Omitted values are preserved. Reactivation does not bypass email activation. */
    public void update(String actor, String username, String role, Boolean active) {
        requireAdmin(actor);
        if (role == null && active == null) {
            throw new AccountProblem(400, "invalid_update", "Supply role or active.");
        }
        if (role != null && !role.equals("Admin") && !role.equals("Farmer")) {
            throw new AccountProblem(400, "invalid_role", "role must be Admin or Farmer.");
        }
        Identity target = find(username);
        String nextRole = role == null ? target.getRole() : role;
        boolean nextActive = active == null ? target.isActive() : active;
        if (nextActive && target.getActivationCode() != null) {
            throw new AccountProblem(409, "activation_required", "The user must complete email activation first.");
        }
        protectLastAdmin(target, nextActive && "Admin".equals(nextRole));
        target.setRole(nextRole);
        target.setActive(nextActive);
        identities.save(target);
    }

    private void requireAdmin(String actor) {
        Identity caller = identities.findById(actor).orElse(null);
        if (caller == null || !isActiveAdmin(caller)) {
            throw new AccountProblem(403, "admin_required", "An active administrator account is required.");
        }
    }

    private Identity find(String username) {
        return identities.findById(username).orElseThrow(() ->
                new AccountProblem(404, "account_not_found", "Account not found."));
    }

    private void protectLastAdmin(Identity target, boolean remainsActiveAdmin) {
        if (!isActiveAdmin(target) || remainsActiveAdmin) return;
        try (var accounts = identities.findAll()) {
            boolean otherAdmin = accounts.anyMatch(account ->
                    !account.getUsername().equals(target.getUsername()) && isActiveAdmin(account));
            if (!otherAdmin) {
                throw new AccountProblem(409, "last_active_admin",
                        "Cannot delete, disable or demote the last active administrator.");
            }
        }
    }

    private static boolean isActiveAdmin(Identity identity) {
        return identity.isActive() && "Admin".equals(identity.getRole());
    }
}
