package tn.supcom.basilcare.boundaries;

import jakarta.annotation.security.RolesAllowed;
import jakarta.ws.rs.DELETE;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.POST;
import jakarta.ws.rs.PUT;
import org.junit.jupiter.api.Test;
import tn.supcom.basilcare.security.Secured;

import java.lang.annotation.Annotation;
import java.lang.reflect.Method;
import java.util.Arrays;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

class DeviceResourceSecurityTest {

    @Test
    void everyEndpointIsSecuredWithTheExpectedRoles() {
        assertNotNull(DeviceResource.class.getAnnotation(Secured.class));
        assertRoles(GET.class, Set.of("Farmer", "Admin"));
        assertRoles(POST.class, Set.of("Admin"));
        assertRoles(PUT.class, Set.of("Admin"));
        assertRoles(DELETE.class, Set.of("Admin"));
    }

    private static void assertRoles(Class<? extends Annotation> verb, Set<String> expected) {
        Method[] methods = Arrays.stream(DeviceResource.class.getDeclaredMethods())
                .filter(method -> method.isAnnotationPresent(verb))
                .toArray(Method[]::new);
        assertTrue(methods.length > 0, "expected at least one " + verb.getSimpleName() + " endpoint");
        for (Method method : methods) {
            RolesAllowed roles = method.getAnnotation(RolesAllowed.class);
            assertNotNull(roles, method.getName() + " must declare roles");
            assertEquals(expected, Set.of(roles.value()), method.getName());
        }
    }
}
