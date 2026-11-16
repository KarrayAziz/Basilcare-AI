package tn.supcom.basilcare.entities;

import jakarta.nosql.Column;
import jakarta.nosql.Entity;
import jakarta.nosql.Id;

/**
 * One validated sensor reading (MQTT contract section 3.2).
 *
 * The id is "{deviceId}:{sensor}:{measuredAtEpochMs}", so the duplicate rule of contract
 * section 7 (same device, sensor and measured_at) is enforced by the primary key itself:
 * a QoS 1 redelivery cannot create a second document.
 */
@Entity("readings")
public class Reading {

    @Id
    private String id;

    @Column
    private String deviceId;

    @Column
    private String sensor;

    @Column
    private double value;

    @Column
    private String unit;

    /** As sent by the device, with its UTC offset. */
    @Column
    private String measuredAt;

    /** Same instant in epoch milliseconds, for sorting and range queries. */
    @Column
    private long measuredAtEpoch;

    @Column
    private boolean calibrated;

    @Column
    private long seq;

    /** true = sent late from the device queue: history, never displayed as a live value. */
    @Column
    private boolean buffered;

    @Column
    private String receivedAt;

    public static String idOf(String deviceId, String sensor, long measuredAtEpoch) {
        return deviceId + ":" + sensor + ":" + measuredAtEpoch;
    }

    public String getId() { return id; }
    public void setId(String id) { this.id = id; }

    public String getDeviceId() { return deviceId; }
    public void setDeviceId(String deviceId) { this.deviceId = deviceId; }

    public String getSensor() { return sensor; }
    public void setSensor(String sensor) { this.sensor = sensor; }

    public double getValue() { return value; }
    public void setValue(double value) { this.value = value; }

    public String getUnit() { return unit; }
    public void setUnit(String unit) { this.unit = unit; }

    public String getMeasuredAt() { return measuredAt; }
    public void setMeasuredAt(String measuredAt) { this.measuredAt = measuredAt; }

    public long getMeasuredAtEpoch() { return measuredAtEpoch; }
    public void setMeasuredAtEpoch(long measuredAtEpoch) { this.measuredAtEpoch = measuredAtEpoch; }

    public boolean isCalibrated() { return calibrated; }
    public void setCalibrated(boolean calibrated) { this.calibrated = calibrated; }

    public long getSeq() { return seq; }
    public void setSeq(long seq) { this.seq = seq; }

    public boolean isBuffered() { return buffered; }
    public void setBuffered(boolean buffered) { this.buffered = buffered; }

    public String getReceivedAt() { return receivedAt; }
    public void setReceivedAt(String receivedAt) { this.receivedAt = receivedAt; }
}
