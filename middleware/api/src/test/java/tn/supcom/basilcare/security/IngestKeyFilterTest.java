package tn.supcom.basilcare.security;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class IngestKeyFilterTest {

    @Test
    void acceptsOnlyTheExactKey() {
        assertTrue(IngestKeyFilter.matches("s3cret-key", "s3cret-key"));
        assertTrue(IngestKeyFilter.matches("s3cret-key", " s3cret-key "));
        assertFalse(IngestKeyFilter.matches("s3cret-key", "s3cret-kez"));
        assertFalse(IngestKeyFilter.matches("s3cret-key", "s3cret"));
        assertFalse(IngestKeyFilter.matches("s3cret-key", null));
    }
}
