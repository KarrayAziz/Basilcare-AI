package tn.supcom.basilcare.services;

import java.time.Clock;
import java.time.Instant;
import java.time.OffsetDateTime;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;
import java.time.temporal.ChronoUnit;
import java.util.Optional;
import java.util.regex.Pattern;

/**
 * Timestamp rules of the MQTT contract (section 1): ISO 8601 with an explicit UTC offset.
 * A time without offset is rejected, because nobody could tell when it really happened.
 */
public final class Timestamps {

    private static final Pattern WITH_OFFSET =
            Pattern.compile("^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(\\.\\d+)?([+-]\\d{2}:\\d{2}|Z)$");
    private static final DateTimeFormatter FORMAT = DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ssXXX");

    private Timestamps() {
    }

    /** Parses a contract timestamp; empty when missing, malformed or without offset. */
    public static Optional<OffsetDateTime> parse(String text) {
        if (text == null || !WITH_OFFSET.matcher(text).matches()) {
            return Optional.empty();
        }
        try {
            return Optional.of(OffsetDateTime.parse(text));
        } catch (DateTimeParseException e) {
            return Optional.empty();
        }
    }

    /** Contract format, second precision: 2026-11-04T14:05:00+01:00. */
    public static String format(OffsetDateTime moment) {
        return FORMAT.format(moment.truncatedTo(ChronoUnit.SECONDS));
    }

    /**
     * Formats an instant in the clock's time zone (the server's zone in production: Africa/Tunis
     * in the compose file). Using the clock's zone, not the JVM default, keeps the output
     * deterministic in tests and on CI runners that run in UTC.
     */
    public static String format(Instant instant, Clock clock) {
        return format(instant.atZone(clock.getZone()).toOffsetDateTime());
    }

    /** Now, in the clock's time zone. */
    public static String now(Clock clock) {
        return format(clock.instant(), clock);
    }
}
