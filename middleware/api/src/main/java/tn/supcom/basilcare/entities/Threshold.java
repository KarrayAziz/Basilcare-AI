package tn.supcom.basilcare.entities;

import jakarta.nosql.Column;
import jakarta.nosql.Entity;
import jakarta.nosql.Id;

/**
 * Agronomic alert range of one sensor, configured by an administrator (scope section 1.4,
 * contract section 3.1). Different from the plausible range of the contract: a pH of 7.2
 * is physically real, but too high for basil.
 *
 * "verified" records whether the range was checked against the selected cultivar and
 * agronomic sources. The seeded defaults are NOT verified; the PWAs show this.
 */
@Entity("thresholds")
public class Threshold {

    @Id
    private String sensor;

    @Column
    private Double min;

    @Column
    private Double max;

    @Column
    private boolean enabled;

    /** warning or critical */
    @Column
    private String severity;

    @Column
    private boolean verified;

    /** Where the range comes from (document, page), or why it is a placeholder. */
    @Column
    private String source;

    @Column
    private String updatedBy;

    @Column
    private String updatedAt;

    public String getSensor() { return sensor; }
    public void setSensor(String sensor) { this.sensor = sensor; }

    public Double getMin() { return min; }
    public void setMin(Double min) { this.min = min; }

    public Double getMax() { return max; }
    public void setMax(Double max) { this.max = max; }

    public boolean isEnabled() { return enabled; }
    public void setEnabled(boolean enabled) { this.enabled = enabled; }

    public String getSeverity() { return severity; }
    public void setSeverity(String severity) { this.severity = severity; }

    public boolean isVerified() { return verified; }
    public void setVerified(boolean verified) { this.verified = verified; }

    public String getSource() { return source; }
    public void setSource(String source) { this.source = source; }

    public String getUpdatedBy() { return updatedBy; }
    public void setUpdatedBy(String updatedBy) { this.updatedBy = updatedBy; }

    public String getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(String updatedAt) { this.updatedAt = updatedAt; }
}
