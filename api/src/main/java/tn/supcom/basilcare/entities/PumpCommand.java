package tn.supcom.basilcare.entities;

import jakarta.nosql.Column;
import jakarta.nosql.Entity;
import jakarta.nosql.Id;

/**
 * Audit record of one pump-control request (scope sections 4.2, 6.2: every control action is
 * attributable to a role and a timestamp). Rejected requests are recorded too, with the reason,
 * so a refused AI-assistant request is as visible as an executed farmer request.
 *
 * Two decisions are recorded: the API's safety policy (decision/decisionReason), then, for an
 * accepted command, the device's own check (deviceResult/deviceReason from pump/state).
 */
@Entity("pump_commands")
public class PumpCommand {

    public static final String ACCEPTED = "accepted";
    public static final String REJECTED = "rejected";

    @Id
    private String commandId;

    @Column
    private String deviceId;

    /** on or off */
    @Column
    private String action;

    @Column
    private Integer durationS;

    @Column
    private String requestedBy;

    /** Farmer or Admin, from the token */
    @Column
    private String requesterRole;

    /** OAuth client that sent the request (farmer PWA, admin PWA, MCP server...) */
    @Column
    private String clientId;

    @Column
    private String requestedAt;

    @Column
    private long requestedAtEpoch;

    @Column
    private String expiresAt;

    @Column
    private String decision;

    @Column
    private String decisionReason;

    @Column
    private boolean published;

    @Column
    private String deviceResult;

    @Column
    private String deviceReason;

    @Column
    private String deviceReportedAt;

    public String getCommandId() { return commandId; }
    public void setCommandId(String commandId) { this.commandId = commandId; }

    public String getDeviceId() { return deviceId; }
    public void setDeviceId(String deviceId) { this.deviceId = deviceId; }

    public String getAction() { return action; }
    public void setAction(String action) { this.action = action; }

    public Integer getDurationS() { return durationS; }
    public void setDurationS(Integer durationS) { this.durationS = durationS; }

    public String getRequestedBy() { return requestedBy; }
    public void setRequestedBy(String requestedBy) { this.requestedBy = requestedBy; }

    public String getRequesterRole() { return requesterRole; }
    public void setRequesterRole(String requesterRole) { this.requesterRole = requesterRole; }

    public String getClientId() { return clientId; }
    public void setClientId(String clientId) { this.clientId = clientId; }

    public String getRequestedAt() { return requestedAt; }
    public void setRequestedAt(String requestedAt) { this.requestedAt = requestedAt; }

    public long getRequestedAtEpoch() { return requestedAtEpoch; }
    public void setRequestedAtEpoch(long requestedAtEpoch) { this.requestedAtEpoch = requestedAtEpoch; }

    public String getExpiresAt() { return expiresAt; }
    public void setExpiresAt(String expiresAt) { this.expiresAt = expiresAt; }

    public String getDecision() { return decision; }
    public void setDecision(String decision) { this.decision = decision; }

    public String getDecisionReason() { return decisionReason; }
    public void setDecisionReason(String decisionReason) { this.decisionReason = decisionReason; }

    public boolean isPublished() { return published; }
    public void setPublished(boolean published) { this.published = published; }

    public String getDeviceResult() { return deviceResult; }
    public void setDeviceResult(String deviceResult) { this.deviceResult = deviceResult; }

    public String getDeviceReason() { return deviceReason; }
    public void setDeviceReason(String deviceReason) { this.deviceReason = deviceReason; }

    public String getDeviceReportedAt() { return deviceReportedAt; }
    public void setDeviceReportedAt(String deviceReportedAt) { this.deviceReportedAt = deviceReportedAt; }
}
