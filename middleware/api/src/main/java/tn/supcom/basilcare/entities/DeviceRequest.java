package tn.supcom.basilcare.entities;

/** JSON body accepted when an administrator creates or updates a device. */
public class DeviceRequest {

    private String deviceId;
    private String name;
    private String location;
    private Boolean enabled;

    public String getDeviceId() { return deviceId; }
    public void setDeviceId(String deviceId) { this.deviceId = deviceId; }

    public String getName() { return name; }
    public void setName(String name) { this.name = name; }

    public String getLocation() { return location; }
    public void setLocation(String location) { this.location = location; }

    public Boolean getEnabled() { return enabled; }
    public void setEnabled(Boolean enabled) { this.enabled = enabled; }
}
