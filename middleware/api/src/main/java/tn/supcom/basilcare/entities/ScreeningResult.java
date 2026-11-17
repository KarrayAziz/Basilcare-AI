package tn.supcom.basilcare.entities;

import jakarta.nosql.Column;
import jakarta.nosql.Entity;
import jakarta.nosql.Id;

import java.util.ArrayList;
import java.util.List;

/**
 * One edge image-screening result (MQTT contract section 6). The image itself stays on
 * the Raspberry Pi; imageId lets a person find it there for review.
 * A screening result is never a diagnosis (scope section 5.1).
 */
@Entity("screenings")
public class ScreeningResult {

    @Id
    private String imageId;

    @Column
    private String deviceId;

    @Column
    private String capturedAt;

    @Column
    private long capturedAtEpoch;

    @Column
    private String modelVersion;

    @Column
    private String label;

    @Column
    private double confidence;

    @Column
    private boolean qualityOk;

    @Column
    private List<String> qualityIssues = new ArrayList<>();

    @Column
    private boolean reviewRequired;

    @Column
    private String receivedAt;

    public String getImageId() { return imageId; }
    public void setImageId(String imageId) { this.imageId = imageId; }

    public String getDeviceId() { return deviceId; }
    public void setDeviceId(String deviceId) { this.deviceId = deviceId; }

    public String getCapturedAt() { return capturedAt; }
    public void setCapturedAt(String capturedAt) { this.capturedAt = capturedAt; }

    public long getCapturedAtEpoch() { return capturedAtEpoch; }
    public void setCapturedAtEpoch(long capturedAtEpoch) { this.capturedAtEpoch = capturedAtEpoch; }

    public String getModelVersion() { return modelVersion; }
    public void setModelVersion(String modelVersion) { this.modelVersion = modelVersion; }

    public String getLabel() { return label; }
    public void setLabel(String label) { this.label = label; }

    public double getConfidence() { return confidence; }
    public void setConfidence(double confidence) { this.confidence = confidence; }

    public boolean isQualityOk() { return qualityOk; }
    public void setQualityOk(boolean qualityOk) { this.qualityOk = qualityOk; }

    public List<String> getQualityIssues() { return qualityIssues; }
    public void setQualityIssues(List<String> qualityIssues) { this.qualityIssues = qualityIssues; }

    public boolean isReviewRequired() { return reviewRequired; }
    public void setReviewRequired(boolean reviewRequired) { this.reviewRequired = reviewRequired; }

    public String getReceivedAt() { return receivedAt; }
    public void setReceivedAt(String receivedAt) { this.receivedAt = receivedAt; }
}
