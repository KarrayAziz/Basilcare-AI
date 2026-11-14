package tn.supcom.basilcare.entities;

import jakarta.nosql.Column;
import jakarta.nosql.Entity;
import jakarta.nosql.Id;

/**
 * Something that needs a person's attention (FR-03), with its acknowledgement and
 * resolution (FR-04).
 *
 * Life cycle: open -> acknowledged -> resolved. Independently, "active" says whether the
 * condition is still present right now. When the condition disappears the incident is NOT
 * closed automatically: a person resolves it and writes what was done, so the resolution
 * is recorded (FR-04). If the condition comes back before that, the same incident is
 * re-activated and its occurrence counter goes up, instead of flooding the farmer with copies.
 */
@Entity("incidents")
public class Incident {

    public static final String OPEN = "open";
    public static final String ACKNOWLEDGED = "acknowledged";
    public static final String RESOLVED = "resolved";

    @Id
    private String id;

    /** "{deviceId}|{type}|{sensor or -}": at most one unresolved incident per key. */
    @Column
    private String key;

    @Column
    private String deviceId;

    /** threshold, stale, offline, pump_fault, invalid_message, leaf_anomaly */
    @Column
    private String type;

    @Column
    private String sensor;

    /** warning or critical */
    @Column
    private String severity;

    @Column
    private String title;

    @Column
    private String detail;

    @Column
    private Double lastValue;

    @Column
    private String status;

    @Column
    private boolean active;

    @Column
    private int occurrences;

    @Column
    private String openedAt;

    @Column
    private long openedAtEpoch;

    @Column
    private String lastSeenAt;

    @Column
    private String clearedAt;

    @Column
    private String acknowledgedBy;

    @Column
    private String acknowledgedAt;

    @Column
    private String resolvedBy;

    @Column
    private String resolvedAt;

    @Column
    private String resolutionNote;

    public static String keyOf(String deviceId, String type, String sensor) {
        return deviceId + "|" + type + "|" + (sensor == null ? "-" : sensor);
    }

    public String getId() { return id; }
    public void setId(String id) { this.id = id; }

    public String getKey() { return key; }
    public void setKey(String key) { this.key = key; }

    public String getDeviceId() { return deviceId; }
    public void setDeviceId(String deviceId) { this.deviceId = deviceId; }

    public String getType() { return type; }
    public void setType(String type) { this.type = type; }

    public String getSensor() { return sensor; }
    public void setSensor(String sensor) { this.sensor = sensor; }

    public String getSeverity() { return severity; }
    public void setSeverity(String severity) { this.severity = severity; }

    public String getTitle() { return title; }
    public void setTitle(String title) { this.title = title; }

    public String getDetail() { return detail; }
    public void setDetail(String detail) { this.detail = detail; }

    public Double getLastValue() { return lastValue; }
    public void setLastValue(Double lastValue) { this.lastValue = lastValue; }

    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }

    public boolean isActive() { return active; }
    public void setActive(boolean active) { this.active = active; }

    public int getOccurrences() { return occurrences; }
    public void setOccurrences(int occurrences) { this.occurrences = occurrences; }

    public String getOpenedAt() { return openedAt; }
    public void setOpenedAt(String openedAt) { this.openedAt = openedAt; }

    public long getOpenedAtEpoch() { return openedAtEpoch; }
    public void setOpenedAtEpoch(long openedAtEpoch) { this.openedAtEpoch = openedAtEpoch; }

    public String getLastSeenAt() { return lastSeenAt; }
    public void setLastSeenAt(String lastSeenAt) { this.lastSeenAt = lastSeenAt; }

    public String getClearedAt() { return clearedAt; }
    public void setClearedAt(String clearedAt) { this.clearedAt = clearedAt; }

    public String getAcknowledgedBy() { return acknowledgedBy; }
    public void setAcknowledgedBy(String acknowledgedBy) { this.acknowledgedBy = acknowledgedBy; }

    public String getAcknowledgedAt() { return acknowledgedAt; }
    public void setAcknowledgedAt(String acknowledgedAt) { this.acknowledgedAt = acknowledgedAt; }

    public String getResolvedBy() { return resolvedBy; }
    public void setResolvedBy(String resolvedBy) { this.resolvedBy = resolvedBy; }

    public String getResolvedAt() { return resolvedAt; }
    public void setResolvedAt(String resolvedAt) { this.resolvedAt = resolvedAt; }

    public String getResolutionNote() { return resolutionNote; }
    public void setResolutionNote(String resolutionNote) { this.resolutionNote = resolutionNote; }
}
