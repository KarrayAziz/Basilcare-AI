package tn.supcom.basilcare.entities;

import jakarta.nosql.Column;
import jakarta.nosql.Entity;
import jakarta.nosql.Id;

/** Last pump state reported by a device on its retained pump/state topic (MQTT contract section 5.3). */
@Entity("pump_states")
public class PumpStatus {

    @Id
    private String deviceId;

    /** on, off or fault */
    @Column
    private String state;

    @Column
    private String until;

    @Column
    private String commandId;

    @Column
    private String result;

    @Column
    private String reason;

    @Column
    private String reportedAt;

    @Column
    private String receivedAt;

    public String getDeviceId() { return deviceId; }
    public void setDeviceId(String deviceId) { this.deviceId = deviceId; }

    public String getState() { return state; }
    public void setState(String state) { this.state = state; }

    public String getUntil() { return until; }
    public void setUntil(String until) { this.until = until; }

    public String getCommandId() { return commandId; }
    public void setCommandId(String commandId) { this.commandId = commandId; }

    public String getResult() { return result; }
    public void setResult(String result) { this.result = result; }

    public String getReason() { return reason; }
    public void setReason(String reason) { this.reason = reason; }

    public String getReportedAt() { return reportedAt; }
    public void setReportedAt(String reportedAt) { this.reportedAt = reportedAt; }

    public String getReceivedAt() { return receivedAt; }
    public void setReceivedAt(String receivedAt) { this.receivedAt = receivedAt; }
}
