package tn.supcom.basilcare.boundaries;

import jakarta.annotation.security.RolesAllowed;
import jakarta.data.exceptions.EntityExistsException;
import jakarta.inject.Inject;
import jakarta.json.Json;
import jakarta.ws.rs.Consumes;
import jakarta.ws.rs.DELETE;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.POST;
import jakarta.ws.rs.PUT;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.PathParam;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.Context;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;
import jakarta.ws.rs.core.UriInfo;
import tn.supcom.basilcare.entities.Device;
import tn.supcom.basilcare.entities.DeviceRequest;
import tn.supcom.basilcare.repositories.DeviceRepository;
import tn.supcom.basilcare.security.Secured;
import tn.supcom.basilcare.services.DeviceValidator;

import java.time.OffsetDateTime;
import java.util.Comparator;
import java.util.List;
import java.util.Optional;

/** Role-protected CRUD API for physical and simulated BasilCare gateways. */
@Path("devices")
@Secured
@Produces(MediaType.APPLICATION_JSON)
@Consumes(MediaType.APPLICATION_JSON)
public class DeviceResource {

    @Inject
    DeviceRepository devices;

    @GET
    @RolesAllowed({"Farmer", "Admin"})
    public List<Device> list() {
        try (var found = devices.findAll()) {
            return found.sorted(Comparator.comparing(Device::getDeviceId)).toList();
        }
    }

    @GET
    @Path("{deviceId}")
    @RolesAllowed({"Farmer", "Admin"})
    public Response get(@PathParam("deviceId") String deviceId) {
        Optional<Device> found = devices.findById(deviceId);
        return found.<Response>map(device -> Response.ok(device).build())
                .orElseGet(() -> error(Response.Status.NOT_FOUND, "device_not_found",
                        "No device exists with id " + deviceId + "."));
    }

    @POST
    @RolesAllowed("Admin")
    public Response create(DeviceRequest request, @Context UriInfo uriInfo) {
        try {
            DeviceValidator.validateForCreate(request);
            String now = OffsetDateTime.now().toString();
            Device device = new Device();
            device.setDeviceId(request.getDeviceId());
            applyDetails(device, request);
            device.setEnabled(request.getEnabled() == null || request.getEnabled());
            device.setCreatedAt(now);
            device.setUpdatedAt(now);
            Device saved = devices.insert(device);
            return Response.created(uriInfo.getAbsolutePathBuilder().path(saved.getDeviceId()).build())
                    .entity(saved)
                    .build();
        } catch (EntityExistsException exception) {
            return error(Response.Status.CONFLICT, "device_exists",
                    "A device with this id already exists.");
        } catch (IllegalArgumentException exception) {
            return error(Response.Status.BAD_REQUEST, "invalid_device", exception.getMessage());
        }
    }

    @PUT
    @Path("{deviceId}")
    @RolesAllowed("Admin")
    public Response update(@PathParam("deviceId") String deviceId, DeviceRequest request) {
        try {
            DeviceValidator.validateForUpdate(deviceId, request);
            Optional<Device> found = devices.findById(deviceId);
            if (found.isEmpty()) {
                return error(Response.Status.NOT_FOUND, "device_not_found",
                        "No device exists with id " + deviceId + ".");
            }
            Device device = found.get();
            applyDetails(device, request);
            if (request.getEnabled() != null) {
                device.setEnabled(request.getEnabled());
            }
            device.setUpdatedAt(OffsetDateTime.now().toString());
            return Response.ok(devices.save(device)).build();
        } catch (IllegalArgumentException exception) {
            return error(Response.Status.BAD_REQUEST, "invalid_device", exception.getMessage());
        }
    }

    @DELETE
    @Path("{deviceId}")
    @RolesAllowed("Admin")
    public Response delete(@PathParam("deviceId") String deviceId) {
        Optional<Device> found = devices.findById(deviceId);
        if (found.isEmpty()) {
            return error(Response.Status.NOT_FOUND, "device_not_found",
                    "No device exists with id " + deviceId + ".");
        }
        devices.delete(found.get());
        return Response.noContent().build();
    }

    private static void applyDetails(Device device, DeviceRequest request) {
        device.setName(request.getName());
        device.setLocation(request.getLocation());
    }

    private static Response error(Response.Status status, String code, String message) {
        return Response.status(status)
                .entity(Json.createObjectBuilder().add("error", code).add("message", message).build())
                .build();
    }
}
