// Unit tests of the "To API request" and "Check API answer" function nodes.
// Like check-contract.test.js, the code is read from flows.json.
// Run from the repository root:  node --test "nodered/test/*.test.js"
const { test } = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const flows = require(path.join(__dirname, "..", "flows.json"));
const code = (name) => flows.find((n) => n.type === "function" && n.name === name).func;
const toApi = new Function("msg", "node", "env", code("To API request"));
const checkAnswer = new Function("msg", "node", "context", code("Check API answer"));

const quietNode = () => ({ warned: [], status() {}, warn(text) { this.warned.push(text); } });
const environment = (values) => ({ get: (name) => values[name] });
const ENV = environment({ API_URL: "http://wildfly:8080/api/", INGEST_KEY: "k3y" });
const T = "basilcare/v1/basil-sim-01";

test("valid messages go to the matching ingest endpoint, payload unchanged", () => {
    const paths = { telemetry: "telemetry", status: "status", pump_state: "pump-state", screening: "screening" };
    for (const [kind, endpoint] of Object.entries(paths)) {
        const payload = { device_id: "basil-sim-01" };
        const out = toApi({ topic: `${T}/x`, kind, payload }, quietNode(), ENV);
        assert.equal(out.url, `http://wildfly:8080/api/ingest/${endpoint}`);
        assert.equal(out.method, "POST");
        assert.equal(out.headers["X-Ingest-Key"], "k3y");
        assert.deepEqual(out.payload, payload);
    }
});

test("pump commands are not sent back to the API", () => {
    assert.equal(toApi({ topic: `${T}/pump/cmd`, kind: "pump_cmd", payload: {} }, quietNode(), ENV), null);
});

test("invalid messages become {topic, errors} for the device incident", () => {
    const out = toApi({ topic: `${T}/telemetry/ph`, errors: ["unit must be pH"], payload: "raw" }, quietNode(), ENV);
    assert.equal(out.url, "http://wildfly:8080/api/ingest/invalid");
    assert.deepEqual(out.payload, { topic: `${T}/telemetry/ph`, errors: ["unit must be pH"] });
});

test("without INGEST_KEY nothing is sent and a warning is logged", () => {
    const node = quietNode();
    assert.equal(toApi({ topic: `${T}/status`, kind: "status", payload: {} }, node, environment({})), null);
    assert.equal(node.warned.length, 1);
});

const freshContext = () => {
    const store = {};
    return { store, get: (k) => store[k], set: (k, v) => { store[k] = v; } };
};
const ingest = (attempts = 0) => ({ path: "telemetry", topic: `${T}/telemetry/ph`, body: { value: 6 }, attempts });

test("the request keeps the body so a retry can resend it", () => {
    const out = toApi({ topic: `${T}/status`, kind: "status", payload: { online: true } }, quietNode(), ENV);
    assert.deepEqual(out.ingest.body, { online: true });
    assert.equal(out.ingest.attempts, 0);
});

test("2xx answers are only counted", () => {
    const context = freshContext();
    for (const status of [200, 201, 202]) {
        assert.equal(checkAnswer({ statusCode: status, ingest: ingest() }, quietNode(), context), null);
    }
    assert.equal(context.store.ok, 3);
});

test("API unreachable or 5xx: retried with the original body", () => {
    const context = freshContext();
    for (const status of ["ECONNREFUSED", 503, 500]) {
        const [retry, failed] = checkAnswer({ statusCode: status, payload: "error text", ingest: ingest() },
                                            quietNode(), context);
        assert.equal(failed, null);
        assert.deepEqual(retry.payload, { value: 6 }, "error text replaced by the original body");
        assert.equal(retry.ingest.attempts, 1);
    }
});

test("refused for good, or still failing after the last attempt: logged, not retried", () => {
    const context = freshContext();
    const [noRetry, refused] = checkAnswer({ statusCode: 422, ingest: ingest() }, quietNode(), context);
    assert.equal(noRetry, null);
    assert.equal(refused.api_error.status, 422);
    const [, wrongKey] = checkAnswer({ statusCode: 401, ingest: ingest() }, quietNode(), context);
    assert.equal(wrongKey.api_error.status, 401);
    const [, gaveUp] = checkAnswer({ statusCode: "ECONNREFUSED", ingest: ingest(23) }, quietNode(), context);
    assert.equal(gaveUp.api_error.attempts, 24);
    assert.equal(context.store.failed, 3);
});
