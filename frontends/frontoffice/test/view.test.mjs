// Unit tests of the farmer PWA's presentation logic. Run: node --test frontends/frontoffice/test/
import { test } from "node:test";
import assert from "node:assert/strict";
import { age, chart, formatValue, newIncidents, pumpReason, rangeStatus, rangeText, sortIncidents }
    from "../scripts/view.js";

test("age and value formatting", () => {
    assert.equal(age(12), "12 s ago");
    assert.equal(age(180), "3 min ago");
    assert.equal(age(7200), "2 h ago");
    assert.equal(formatValue(6.049, "pH"), "pH 6.05");
    assert.equal(formatValue(1.4, "mS/cm"), "1.40 mS/cm");
    assert.equal(formatValue(24.06, "degC"), "24.1 °C");
    assert.equal(formatValue(80, "%"), "80.0 %");
});

test("a value is compared with the enabled alert range only", () => {
    const ph = { enabled: true, min: 5.5, max: 6.5, verified: false };
    assert.equal(rangeStatus(6.0, ph), "ok");
    assert.equal(rangeStatus(7.1, ph), "high");
    assert.equal(rangeStatus(5.0, ph), "low");
    assert.equal(rangeStatus(9, { ...ph, enabled: false }), "unknown");
    assert.equal(rangeStatus(10, { enabled: true, min: 25, max: null }), "low");
    assert.equal(rangeText(ph), "range 5.5 to 6.5 (not verified)");
});

test("pump refusals are explained, unknown reasons shown as they are", () => {
    assert.match(pumpReason("low_water_level"), /Refill/);
    assert.equal(pumpReason("new_reason"), "new_reason");
    assert.equal(pumpReason(null), "");
});

test("chart scales points by time and value and keeps the buffered flag", () => {
    const points = [
        { measured_at: "2026-11-04T14:00:00+01:00", value: 6.0, buffered: false },
        { measured_at: "2026-11-04T14:00:10+01:00", value: 7.0, buffered: true },
    ];
    const result = chart(points, 100, 50, 0);
    assert.deepEqual(result.dots.map((d) => [d.x, d.y, d.buffered]), [[0, 50, false], [100, 0, true]]);
    assert.equal(result.line, "0.0,50.0 100.0,0.0");
    assert.deepEqual(chart([], 100, 50), { line: "", dots: [], min: null, max: null });
});

test("only new, active incidents trigger a notification; critical ones first", () => {
    const a = { id: "a", active: true, severity: "warning", openedAtEpoch: 2 };
    const b = { id: "b", active: true, severity: "critical", openedAtEpoch: 1 };
    const c = { id: "c", active: false, severity: "critical", openedAtEpoch: 3 };
    assert.deepEqual(newIncidents(new Set(["a"]), [a, b, c]).map((i) => i.id), ["b"]);
    assert.deepEqual(sortIncidents([a, c, b]).map((i) => i.id), ["b", "c", "a"]);
});

test("live camera: boxes, colours, names, summary and staleness", async () => {
    const { boxPixels, detectionColor, detectionSummary, diseaseName, liveStatus } = await import("../scripts/view.js");
    assert.deepEqual(boxPixels([0.1, 0.25, 0.5, 1.2], 640, 480), { x: 64, y: 120, w: 256, h: 360 });
    assert.equal(diseaseName("downy_mildew"), "Downy mildew");
    assert.equal(detectionColor("healthy"), "#2e9e44");
    assert.equal(detectionColor("something_new"), "#555");
    assert.deepEqual(detectionSummary([
        { label: "healthy", confidence: 0.6 }, { label: "downy_mildew", confidence: 0.7 },
        { label: "downy_mildew", confidence: 0.4 }]),
        [{ label: "downy_mildew", confidence: 0.7, count: 2 }, { label: "healthy", confidence: 0.6, count: 1 }]);
    const live = liveStatus({ age_s: 0.4, model_version: "basil-detect-0.1", fps: 2.04, inference_ms: 181.6 });
    assert.equal(live.stale, false);
    assert.match(live.text, /2\.0 frames\/s · 182 ms/);
    const stale = liveStatus({ age_s: 95, model_version: "m", fps: 2, inference_ms: 100 });
    assert.equal(stale.stale, true);
    assert.match(stale.text, /2 min/);
});
