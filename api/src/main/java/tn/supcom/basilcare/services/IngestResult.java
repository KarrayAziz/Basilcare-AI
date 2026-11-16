package tn.supcom.basilcare.services;

import java.util.List;

/**
 * Outcome of one ingested message: stored, duplicate (ignored, contract section 7),
 * outdated (delivered after a newer message of the same kind, ignored) or invalid.
 */
public record IngestResult(Outcome outcome, List<String> errors) {

    public enum Outcome { STORED, DUPLICATE, OUTDATED, INVALID }

    public static IngestResult stored() {
        return new IngestResult(Outcome.STORED, List.of());
    }

    public static IngestResult duplicate() {
        return new IngestResult(Outcome.DUPLICATE, List.of());
    }

    public static IngestResult outdated() {
        return new IngestResult(Outcome.OUTDATED, List.of());
    }

    public static IngestResult invalid(List<String> errors) {
        return new IngestResult(Outcome.INVALID, List.copyOf(errors));
    }
}
