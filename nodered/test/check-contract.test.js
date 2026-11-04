// Unit tests of the "Check against MQTT contract" function node.
// The code is read from flows.json, so the tests always cover the deployed version.
// Run from the repository root (Node.js 22+, nothing to install):  node --test "nodered/test/*.test.js"
const { test } = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const flows = require(path.join(__dirname, "..", "flows.json"));
const node = flows.find((n) => n.type === "function" && n.name === "Check against MQTT contract");
const checkNode = new Function("msg", "node", node.func);

/** Runs the node like Node-RED does; returns { valid, invalid } (one is null) or null. */
function check(topic, payload) {
    const text = typeof payload === "string" ? payload : JSON.stringify(payload);
    const result = checkNode({ topic, payload: text }, {});
    return result && { valid: result[0], invalid: result[1] };
}

const T = "basilcare/v1/basil-sim-01";
const reading = (fields = {}) => ({
    device_id: "basil-sim-01", sensor: "ph", value: 6.04, unit: "pH",
    measured_at: "2026-11-04T14:05:00+01:00", calibrated: true, seq: 1, buffered: false, ...fields,
});
const status = (fields = {}) => ({
    device_id: "basil-sim-01", online: true, started_at: "2026-11-04T08:00:00+01:00",
    telemetry_interval_s: 5, software: "simulator 0.1.0", reported_at: "2026-11-04T08:00:01+01:00", ...fields,
});
const pumpState = (fields = {}) => ({
    device_id: "basil-sim-01", state: "on", until: "2026-11-04T14:08:00+01:00", command_id: "c-1",
    result: "executed", reason: null, reported_at: "2026-11-04T14:06:00+01:00", ...fields,
});
const pumpCmd = (fields = {}) => ({
    command_id: "c-1", device_id: "basil-sim-01", action: "on", duration_s: 120, requested_by: "farmer1",
    requested_at: "2026-11-04T14:06:00+01:00", expires_at: "2026-11-04T14:07:00+01:00", ...fields,
});
const screening = (fields = {}) => ({
    device_id: "basil-sim-01", image_id: "img-1", captured_at: "2026-11-04T14:05:00+01:00",
    model_version: "simulated", label: "healthy", confidence: 0.62, quality_ok: true,
    quality_issues: [], review_required: true, ...fields,
});

function assertValid(topic, payload, kind) {
    const out = check(topic, payload);
    assert.equal(out.invalid, null, out.invalid && out.invalid.errors.join("; "));
    assert.equal(out.valid.kind, kind);
    assert.equal(out.valid.device_id, "basil-sim-01");
    const text = typeof payload === "string" ? payload : JSON.stringify(payload);
    assert.deepEqual(out.valid.payload, JSON.parse(text));
    assert.match(out.valid.received_at, /Z$/);
}

function assertInvalid(topic, payload, problem) {
    const out = check(topic, payload);
    assert.equal(out.valid, null, "expected invalid");
    assert.ok(out.invalid.errors.some((e) => e.includes(problem)),
              `expected "${problem}" in: ${out.invalid.errors.join("; ")}`);
    assert.equal(out.invalid.payload, typeof payload === "string" ? payload : JSON.stringify(payload));
}

test("the contract examples are valid and get the right kind", () => {
    assertValid(`${T}/telemetry/ph`, reading(), "telemetry");
    assertValid(`${T}/status`, status(), "status");
    assertValid(`${T}/pump/state`, pumpState(), "pump_state");
    assertValid(`${T}/pump/cmd`, pumpCmd(), "pump_cmd");
    assertValid(`${T}/screening`, screening(), "screening");
});

test("every sensor of the contract is accepted with its unit", () => {
    const units = { air_temperature: "degC", air_humidity: "%RH", ph: "pH", ec: "mS/cm",
                    water_temperature: "degC", water_level: "%" };
    for (const [sensor, unit] of Object.entries(units)) {
        assertValid(`${T}/telemetry/${sensor}`, reading({ sensor, unit, value: 10 }), "telemetry");
    }
});

test("Last Will (offline, reported_at null) and a buffered reading are valid", () => {
    assertValid(`${T}/status`, status({ online: false, reported_at: null }), "status");
    assertValid(`${T}/telemetry/ph`, reading({ buffered: true, seq: 42 }), "telemetry");
    assertValid(`${T}/telemetry/ph`, reading({ measured_at: "2026-11-04T13:05:00Z" }), "telemetry");
});

test("an empty message (retained topic being cleared) is dropped silently", () => {
    assert.equal(check(`${T}/status`, ""), null);
});

test("broken topics and payloads are invalid", () => {
    assertInvalid(`${T}/unknown`, status(), "unknown topic");
    assertInvalid("basilcare/v1/basil-sim-01", status(), "unknown topic");
    assertInvalid("basilcare/v1/Bad_Id/status", status({ device_id: "Bad_Id" }), "invalid device_id");
    assertInvalid(`${T}/status`, "not json", "not a JSON object");
    assertInvalid(`${T}/status`, "[1,2]", "not a JSON object");
    assertInvalid(`${T}/status`, status({ device_id: "basil-sim-02" }), "differs from the topic");
});

test("readings: unknown sensor, wrong unit, out of range, wrong types", () => {
    assertInvalid(`${T}/telemetry/co2`, reading({ sensor: "co2" }), "unknown sensor co2");
    assertInvalid(`${T}/telemetry/ec`, reading(), "sensor differs from the topic");
    assertInvalid(`${T}/telemetry/ph`, reading({ unit: "mS/cm" }), "unit must be pH");
    assertInvalid(`${T}/telemetry/ph`, reading({ value: 14.5 }), "plausible range");
    assertInvalid(`${T}/telemetry/ph`, reading({ value: -0.1 }), "plausible range");
    assertInvalid(`${T}/telemetry/ph`, reading({ value: "6.0" }), "plausible range");
    assertInvalid(`${T}/telemetry/ph`, reading({ seq: 0 }), "seq");
    assertInvalid(`${T}/telemetry/ph`, reading({ calibrated: "yes" }), "calibrated");
    assertInvalid(`${T}/telemetry/ph`, reading({ buffered: undefined }), "buffered");
});

test("timestamps must carry an offset", () => {
    assertInvalid(`${T}/telemetry/ph`, reading({ measured_at: "2026-11-04T14:05:00" }), "measured_at");
    assertInvalid(`${T}/telemetry/ph`, reading({ measured_at: 1762261500 }), "measured_at");
    assertInvalid(`${T}/telemetry/ph`, reading({ measured_at: "2026-13-45T99:00:00+01:00" }), "measured_at");
});

test("status: reported_at may be null only when offline", () => {
    assertInvalid(`${T}/status`, status({ reported_at: null }), "reported_at");
    assertInvalid(`${T}/status`, status({ telemetry_interval_s: 0 }), "telemetry_interval_s");
});

test("pump state, pump command and screening field checks", () => {
    assertInvalid(`${T}/pump/state`, pumpState({ state: "running" }), "state must be");
    assertInvalid(`${T}/pump/state`, pumpState({ result: "ok" }), "result must be");
    assertInvalid(`${T}/pump/cmd`, pumpCmd({ action: "start" }), "action must be");
    assertInvalid(`${T}/pump/cmd`, pumpCmd({ duration_s: 1.5 }), "duration_s");
    assertInvalid(`${T}/pump/cmd`, pumpCmd({ command_id: "" }), "command_id");
    assertInvalid(`${T}/pump/cmd`, pumpCmd({ device_id: undefined }), "device_id differs from the topic");
    assertValid(`${T}/pump/cmd`, pumpCmd({ action: "off", duration_s: undefined }), "pump_cmd");
    assertInvalid(`${T}/screening`, screening({ confidence: 1.2 }), "confidence");
    assertInvalid(`${T}/screening`, screening({ quality_issues: "too_dark" }), "quality_issues");
});
