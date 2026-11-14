package tn.supcom.basilcare.entities;

import jakarta.nosql.Column;
import jakarta.nosql.Entity;
import jakarta.nosql.Id;

/**
 * Last known connection state of a device, from its retained status message
 * (MQTT contract section 4). Separate from Device (the registry managed by admins):
 * this one is written only by the devices themselves.
 */
@Entity("device_states")
public class DeviceState {

    @Id
    private String deviceId;

    @Column
    private boolean online;

    @Column
    private String startedAt;

    @Column
    private int telemetryIntervalS;

    @Column
    private String software;

    /** null for a Last Will: the broker sent it, the device could not date it. */
    @Column
    private String reportedAt;

    /** When the API received the status (used for a Last Will). */
    @Column
    private String receivedAt;

    @Column
    private long receivedAtEpoch;

    public String getDeviceId() { return deviceId; }
    public void setDeviceId(String deviceId) { this.deviceId = deviceId; }

    public boolean isOnline() { return online; }
    public void setOnline(boolean online) { this.online = online; }

    public String getStartedAt() { return startedAt; }
    public void setStartedAt(String startedAt) { this.startedAt = startedAt; }

    public int getTelemetryIntervalS() { return telemetryIntervalS; }
    public void setTelemetryIntervalS(int telemetryIntervalS) { this.telemetryIntervalS = telemetryIntervalS; }

    public String getSoftware() { return software; }
    public void setSoftware(String software) { this.software = software; }

    public String getReportedAt() { return reportedAt; }
    public void setReportedAt(String reportedAt) { this.reportedAt = reportedAt; }

    public String getReceivedAt() { return receivedAt; }
    public void setReceivedAt(String receivedAt) { this.receivedAt = receivedAt; }

    public long getReceivedAtEpoch() { return receivedAtEpoch; }
    public void setReceivedAtEpoch(long receivedAtEpoch) { this.receivedAtEpoch = receivedAtEpoch; }
}
