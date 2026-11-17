package tn.supcom.basilcare.services;

import org.junit.jupiter.api.Test;
import tn.supcom.basilcare.entities.Threshold;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class ThresholdServiceTest {

    @Test
    void seedsUnverifiedDefaultsOnceAndNeverOverwritesAnAdminChoice() {
        var w = new Fakes.World();   // seeds once
        assertEquals(6, w.store.thresholds.size());
        assertFalse(w.store.thresholds.get("ph").isVerified());

        w.thresholds.update("ph", range(5.8, 6.2, true, "Basil grower guide, p. 12"), "admin");
        assertEquals(0, w.thresholds.seedDefaults());
        assertEquals(5.8, w.store.thresholds.get("ph").getMin());
        assertTrue(w.store.thresholds.get("ph").isVerified());
        assertEquals("admin", w.store.thresholds.get("ph").getUpdatedBy());
    }

    @Test
    void rejectsUnusableRanges() {
        var w = new Fakes.World();
        assertThrows(IllegalArgumentException.class, () -> w.thresholds.update("ph", range(7, 6, false, null), "a"));
        assertThrows(IllegalArgumentException.class, () -> w.thresholds.update("ph", range(-1, 6, false, null), "a"));
        assertThrows(IllegalArgumentException.class, () -> w.thresholds.update("co2", range(1, 2, false, null), "a"));
        assertThrows(IllegalArgumentException.class, () -> w.thresholds.update("ph", range(5, 6, true, ""), "a"),
                "a verified range must cite its source");
    }

    private static Threshold range(double min, double max, boolean verified, String source) {
        Threshold t = new Threshold();
        t.setMin(min);
        t.setMax(max);
        t.setEnabled(true);
        t.setVerified(verified);
        t.setSource(source);
        return t;
    }
}
