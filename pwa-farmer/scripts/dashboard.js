// Farmer dashboard: live values, history, incidents, pump control and leaf screening (FR-02..FR-05).
import { api, el } from "./api.js";
import { age, chart, formatValue, newIncidents, pumpReason, rangeStatus, rangeText, sortIncidents } from "./view.js";

const POLL_MS = 5000;
let timer = null;
let deviceId = localStorage.getItem("basilcare.device") || null;
let chartSensor = "ph";
let knownIncidents = null;   // ids seen at the previous poll (null = first poll: no notification)

export async function startDashboard() {
    stopDashboard();
    document.getElementById("notify").addEventListener("click", askNotifications);
    document.getElementById("pump-start").addEventListener("click", () => pump("on"));
    document.getElementById("pump-stop").addEventListener("click", () => pump("off"));
    document.getElementById("device").addEventListener("change", (event) => {
        deviceId = event.target.value;
        localStorage.setItem("basilcare.device", deviceId);
        knownIncidents = null;
        refresh();
    });
    await loadDevices();
    await refresh();
    timer = setInterval(refresh, POLL_MS);
}

export function stopDashboard() {
    if (timer) clearInterval(timer);
    timer = null;
}

async function loadDevices() {
    const select = document.getElementById("device");
    const devices = await api("/devices");
    select.replaceChildren(...devices.filter((d) => d.enabled).map((d) =>
        el("option", { value: d.deviceId }, `${d.name} (${d.deviceId})`)));
    if (!devices.some((d) => d.deviceId === deviceId)) deviceId = devices[0]?.deviceId || null;
    if (deviceId) select.value = deviceId;
    document.getElementById("no-device").hidden = Boolean(deviceId);
}

async function refresh() {
    if (!deviceId || !document.getElementById("device")) {
        if (!document.getElementById("device")) stopDashboard();   // the user left the page
        return;
    }
    try {
        const [state, live, thresholds, incidents, pumpState, screenings] = await Promise.all([
            api(`/device-states/${deviceId}`).catch(() => null),
            api(`/telemetry/latest?deviceId=${deviceId}`),
            api("/thresholds"),
            api(`/incidents?deviceId=${deviceId}`),
            api(`/pump/${deviceId}`),
            api(`/screenings?deviceId=${deviceId}&limit=5`),
        ]);
        showState(state);
        showLive(live, thresholds);
        showIncidents(incidents);
        showPump(pumpState);
        showScreenings(screenings);
        await showHistory();
        setError("");
    } catch (error) {
        setError(`Cannot reach the API: ${error.message}`);
    }
}

function setError(text) {
    const box = document.getElementById("error");
    box.textContent = text;
    box.hidden = !text;
}

function showState(state) {
    const box = document.getElementById("state");
    if (!state) {
        box.className = "banner muted";
        box.textContent = "No status received from this device yet.";
        return;
    }
    box.className = `banner ${state.online ? "ok" : "bad"}`;
    box.textContent = state.online
        ? `Online · ${state.software} · readings every ${state.telemetryIntervalS} s`
        : `Offline since ${new Date(state.receivedAt).toLocaleString()} · pump safety stays active on the device`;
}

function showLive(live, thresholds) {
    const byName = Object.fromEntries(thresholds.map((t) => [t.sensor, t]));
    const cards = live.map((r) => {
        const status = rangeStatus(r.value, byName[r.sensor]);
        return el("button", { class: `card value ${status}${r.stale ? " stale" : ""}${chartSensor === r.sensor ? " selected" : ""}`,
            title: "Show the history", onclick: () => { chartSensor = r.sensor; refresh(); } },
        el("h3", {}, r.label),
        el("p", { class: "big" }, formatValue(r.value, r.unit)),
        el("small", {}, rangeText(byName[r.sensor])),
        el("small", {}, r.stale ? `⚠ not reporting (${age(r.ageSeconds)})` : age(r.ageSeconds)),
        r.calibrated ? null : el("small", { class: "warn" }, "probe not calibrated"));
    });
    for (const sensor of ["ph", "ec", "water_level"]) {
        const reading = live.find((r) => r.sensor === sensor);
        document.getElementById(`sum-${sensor}`).textContent = reading ? formatValue(reading.value, reading.unit) : "—";
    }
    document.getElementById("live").replaceChildren(...(cards.length ? cards
        : [el("p", { class: "muted" }, "No reading yet. Is the device or the simulator running?")]));
}

async function showHistory() {
    const data = await api(`/telemetry/history?deviceId=${deviceId}&sensor=${chartSensor}&limit=2000`);
    const width = 600;
    const height = 160;
    const { line, dots, min, max } = chart(data.points, width, height);
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", `${data.label}, last 24 hours`);
    const path = document.createElementNS(svg.namespaceURI, "polyline");
    path.setAttribute("points", line);
    path.setAttribute("class", "line");
    svg.append(path);
    for (const d of dots.filter((p) => p.buffered)) {   // history sent late after an outage
        const c = document.createElementNS(svg.namespaceURI, "circle");
        c.setAttribute("cx", d.x);
        c.setAttribute("cy", d.y);
        c.setAttribute("r", 3);
        c.setAttribute("class", "buffered");
        svg.append(c);
    }
    document.getElementById("history-title").textContent =
        `${data.label} — last 24 h (${data.points.length} points${min === null ? "" : `, ${min.toFixed(2)} to ${max.toFixed(2)} ${data.unit}`})`;
    document.getElementById("history").replaceChildren(svg);
}

function showIncidents(incidents) {
    const list = sortIncidents(incidents).map((i) => el("li", { class: `incident ${i.severity}${i.active ? "" : " cleared"}` },
        el("strong", {}, i.title),
        el("span", { class: "tag" }, i.status),
        i.active ? null : el("span", { class: "tag" }, "condition cleared"),
        el("p", {}, i.detail),
        el("small", {}, `opened ${new Date(i.openedAt).toLocaleString()}${i.occurrences > 1 ? ` · ${i.occurrences} times` : ""}`
            + (i.acknowledgedBy ? ` · seen by ${i.acknowledgedBy}` : "")),
        el("div", { class: "actions" },
            i.status === "open" ? el("button", { onclick: () => acknowledge(i.id) }, "Acknowledge") : null,
            el("button", { onclick: () => resolve(i.id) }, "Resolve…"))));
    document.getElementById("incidents").replaceChildren(...(list.length ? list
        : [el("li", { class: "muted" }, "No open incident.")]));
    document.getElementById("incident-count").textContent = String(incidents.length);
    document.getElementById("sum-alerts").textContent = String(incidents.filter((i) => i.active).length);
    notifyNew(incidents);
}

async function acknowledge(id) {
    await api(`/incidents/${id}/acknowledge`, { method: "POST" });
    refresh();
}

async function resolve(id) {
    const note = prompt("What was done to fix it? (recorded with your name)");
    if (note === null) return;
    try {
        await api(`/incidents/${id}/resolve`, { method: "POST", body: { note } });
        refresh();
    } catch (error) {
        alert(error.message);
    }
}

function showPump(state) {
    const text = state.state === null ? "unknown (no report yet)"
        : state.state === "on" ? `ON until ${new Date(state.until).toLocaleTimeString()}`
            : state.state.toUpperCase();
    document.getElementById("pump-state").textContent = text;
    document.getElementById("pump-reason").textContent = pumpReason(state.reason);
    const input = document.getElementById("pump-duration");
    input.max = state.max_duration_s;
    document.getElementById("pump-limits").textContent =
        `Maximum ${state.max_duration_s} s. Refused below ${state.min_water_level} % water. The device checks again by itself.`;
}

async function pump(action) {
    const duration = Number(document.getElementById("pump-duration").value);
    const question = action === "on"
        ? `Start the pump of ${deviceId} for ${duration} seconds?`
        : `Stop the pump of ${deviceId}?`;
    if (!confirm(question)) return;   // scope §5.3: a person confirms every control action
    const result = document.getElementById("pump-result");
    try {
        const command = await api(`/pump/${deviceId}/commands`, {
            method: "POST",
            body: action === "on" ? { action, duration_s: duration, confirm: true } : { action, confirm: true },
        });
        result.className = command.decision === "accepted" ? "ok" : "bad";
        result.textContent = command.decision === "accepted"
            ? "Sent. Waiting for the device to confirm…"
            : `Refused: ${pumpReason(command.decisionReason)}`;
    } catch (error) {
        result.className = "bad";
        result.textContent = error.message;
    }
    setTimeout(refresh, 1500);
}

function showScreenings(screenings) {
    const items = screenings.map((s) => el("li", {},
        el("strong", {}, s.reviewRequired ? "Review required" : s.label),
        el("span", { class: "tag" }, `${Math.round(s.confidence * 100)} %`),
        s.qualityOk ? null : el("span", { class: "tag warn" }, `picture: ${s.qualityIssues.join(", ")}`),
        el("small", {}, ` ${new Date(s.capturedAt).toLocaleString()} · model ${s.modelVersion} · image ${s.imageId}`)));
    document.getElementById("screenings").replaceChildren(...(items.length ? items
        : [el("li", { class: "muted" }, "No screening yet.")]));
}

// ---- browser notifications (FR-04) while the app is open ----------------------------

async function askNotifications() {
    if (!("Notification" in window)) return alert("This browser has no notifications.");
    const permission = await Notification.requestPermission();
    document.getElementById("notify").hidden = permission === "granted";
}

function notifyNew(incidents) {
    const fresh = knownIncidents ? newIncidents(knownIncidents, incidents) : [];
    knownIncidents = new Set(incidents.map((i) => i.id));
    if (!("Notification" in window) || Notification.permission !== "granted") return;
    for (const incident of fresh) {
        new Notification(`BasilCare: ${incident.title}`, { body: incident.detail, tag: incident.id, icon: "images/icon.svg" });
    }
}
