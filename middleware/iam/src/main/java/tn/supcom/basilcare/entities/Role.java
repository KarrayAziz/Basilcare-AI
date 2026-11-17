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