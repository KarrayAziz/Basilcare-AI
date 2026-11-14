package tn.supcom.basilcare.services;

import jakarta.json.Json;
import jakarta.json.JsonObject;
import org.junit.jupiter.api.Test;
import tn.supcom.basilcare.entities.PumpCommand;

import java.io.StringReader;
import java.time.Duration;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class PumpServiceTest {

    private static final String DEVICE = "basil-sim-01";
    private static final PumpService.Requester FARMER =
            new PumpService.Requester("farmer1", "Farmer", "basilcare-pwa-farmer");

    /** A registered, online device with a recent, sufficient water level. */
    private static Fakes.World ready() {
        var w = new Fakes.World();
        w.register(DEVICE);
        w.online(DEVICE);
        w.read(DEVICE, "water_level", 80);
        return w;
    }

    @Test
    void acceptedCommandIsAuditedThenPublishedWithTheContractPayload() {
        var w = ready();
        PumpCommand command = w.pump.request(DEVICE, "on", 120, true, FARMER);

        assertEquals(PumpCommand.ACCEPTED, command.getDecision());
        assertTrue(w.store.commands.containsKey(command.getCommandId()));
        assertEquals(1, w.publisher.sent.size());
        assertEquals("basilcare/v1/" + DEVICE + "/pump/cmd", w.publisher.sent.get(0)[0]);
        JsonObject payload = Json.createReader(new StringReader(w.publisher.sent.get(0)[1])).readObject();
        assertEquals(DEVICE, payload.getString("device_id"));
        assertEquals(command.getCommandId(), payload.getString("command_id"));
        assertEquals(120, payload.getInt("duration_s"));
        assertEquals("farmer1", payload.getString("requested_by"));
        assertEquals("2026-11-04T14:06:00+01:00", payload.getString("expires_at"), "requested + 60 s");
        assertEquals("basilcare-pwa-farmer", command.getClientId());
    }

    @Test
    void unconfirmedOrMalformedRequestsAreRefusedBeforeAnyRecord() {
        var w = ready();
        assertThrows(PumpService.ConfirmationRequired.class, () -> w.pump.request(DEVICE, "on", 60, false, FARMER));
        assertThrows(IllegalArgumentException.class, () -> w.pump.request(DEVICE, "on", null, true, FARMER));
        assertThrows(IllegalArgumentException.class, () -> w.pump.request(DEVICE, "spin", 60, true, FARMER));
        assertTrue(w.store.commands.isEmpty());
        assertTrue(w.publisher.sent.isEmpty());
    }

    @Test
    void lowWaterIsRejectedRecordedAndNeverSent() {
        var w = ready();
        w.clock.advance(Duration.ofSeconds(5));
        w.read(DEVICE, "water_level", 12);
        PumpCommand command = w.pump.request(DEVICE, "on", 60, true, FARMER);

        assertEquals(PumpCommand.REJECTED, command.getDecision());
        assertEquals("low_water_level", command.getDecisionReason());
        assertTrue(w.store.commands.containsKey(command.getCommandId()), "rejections are audited too");
        assertTrue(w.publisher.sent.isEmpty());
    }

    @Test
    void staleWaterLevelCountsAsUnknown() {
        var w = ready();
        w.clock.advance(Duration.ofSeconds(16));   // 3 x 5 s interval exceeded
        assertEquals("water_level_unknown", w.pump.request(DEVICE, "on", 60, true, FARMER).getDecisionReason());
    }

    @Test
    void policyOrder() {
        var w = new Fakes.World();
        assertEquals("device_not_registered", w.pump.request(DEVICE, "on", 60, true, FARMER).getDecisionReason());
        w.register(DEVICE);
        assertEquals("device_offline", w.pump.request(DEVICE, "on", 60, true, FARMER).getDecisionReason());
        w.online(DEVICE);
        w.read(DEVICE, "water_level", 80);
        assertEquals("duration_too_long", w.pump.request(DEVICE, "on", 901, true, FARMER).getDecisionReason());
        w.store.devices.get(DEVICE).setEnabled(false);
        assertEquals("device_disabled", w.pump.request(DEVICE, "on", 60, true, FARMER).getDecisionReason());
    }

    @Test
    void stopIsAlwaysAllowedForARegisteredDeviceEvenOffline() {
        var w = new Fakes.World();
        w.register(DEVICE);
        PumpCommand command = w.pump.request(DEVICE, "off", null, true, FARMER);
        assertEquals(PumpCommand.ACCEPTED, command.getDecision());
        assertFalse(w.publisher.sent.get(0)[1].contains("duration_s"));
    }

    @Test
    void brokerFailureIsRecordedAsRejected() {
        var w = ready();
        w.publisher.fail = true;
        PumpCommand command = w.pump.request(DEVICE, "on", 60, true, FARMER);
        assertEquals("broker_unavailable", command.getDecisionReason());
        assertFalse(w.store.commands.get(command.getCommandId()).isPublished());
    }

    @Test
    void deviceAnswerCompletesTheAuditRecord() {
        var w = ready();
        PumpCommand command = w.pump.request(DEVICE, "on", 60, true, FARMER);
        w.pump.ingestPumpState(Json.createObjectBuilder()
                .add("device_id", DEVICE).add("state", "off").addNull("until")
                .add("command_id", command.getCommandId()).add("result", "rejected").add("reason", "expired")
                .add("reported_at", w.now()).build());

        PumpCommand audited = w.store.commands.get(command.getCommandId());
        assertEquals("rejected", audited.getDeviceResult());
        assertEquals("expired", audited.getDeviceReason());
    }
}
