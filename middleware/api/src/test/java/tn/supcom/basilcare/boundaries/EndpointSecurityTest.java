package tn.supcom.basilcare.boundaries;

import jakarta.annotation.security.RolesAllowed;
import jakarta.ws.rs.DELETE;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.POST;
import jakarta.ws.rs.PUT;
import org.junit.jupiter.api.Test;
import tn.supcom.basilcare.security.IngestKeyRequired;
import tn.supcom.basilcare.security.Secured;

import java.lang.reflect.Method;
import java.util.Arrays;
import java.util.List;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.fail;

/** Guards against an endpoint being added without protection. */
class EndpointSecurityTest {

    private static final List<Class<?>> USER_RESOURCES = List.of(
            TelemetryResource.class, DeviceStateResource.class, ScreeningResource.class,
            IncidentResource.class, ThresholdResource.class, PumpResource.class, CameraResource.class);

    @Test
    void everyUserEndpointNeedsAValidTokenAndDeclaresItsRoles() {
        for (Class<?> resource : USER_RESOURCES) {
            assertNotNull(resource.getAnnotation(Secured.class), resource.getSimpleName() + " must be @Secured");
            for (Method method : endpoints(resource)) {
                RolesAllowed roles = method.getAnnotation(RolesAllowed.class);
                if (roles == null) {
                    roles = resource.getAnnotation(RolesAllowed.class);
                }
                if (roles == null) {
                    fail(resource.getSimpleName() + "." + method.getName() + " declares no roles");
                }
            }
        }
    }

    @Test
    void onlyAdministratorsChangeAlertRanges() throws NoSuchMethodException {
        Method update = Arrays.stream(ThresholdResource.class.getDeclaredMethods())
                .filter(m -> m.isAnnotationPresent(PUT.class)).findFirst().orElseThrow();
        assertEquals(Set.of("Admin"), Set.of(update.getAnnotation(RolesAllowed.class).value()));
    }

    @Test
    void ingestionUsesTheServiceKeyNotUserTokens() {
        assertNotNull(IngestResource.class.getAnnotation(IngestKeyRequired.class));
        assertNull(IngestResource.class.getAnnotation(Secured.class));
    }

    private static List<Method> endpoints(Class<?> resource) {
        return Arrays.stream(resource.getDeclaredMethods())
                .filter(m -> m.isAnnotationPresent(GET.class) || m.isAnnotationPresent(POST.class)
                        || m.isAnnotationPresent(PUT.class) || m.isAnnotationPresent(DELETE.class))
                .toList();
    }
}
