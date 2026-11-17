// Administration dashboard: device registry, incidents, alert ranges, pump audit (FR-08, scope §2.1).
import { API, api, el } from "./api.js";
import { pumpReason, sortIncidents } from "./view.js";

const POLL_MS = 10000;
let timer = null;

export async function startDashboard() {
    stopDashboard();
    document.getElementById("device-form").addEventListener("submit", registerDevice);
    await Promise.all([refresh(), loadThresholds()]);
    timer = setInterval(refresh, POLL_MS);
}

export function stopDashboard() {
    if (timer) clearInterval(timer);
    timer = null;
}

async function refresh() {
    if (!document.getElementById("devices")) return stopDashboard();
    try {
        const [devices, states, incidents, audit, health] = await Promise.all([
            api("/devices"), api("/device-states"), api("/incidents?status=unresolved&limit=200"),
            api("/pump/commands?limit=30"), fetch(`${API}/health`).then((r) => r.json()).catch(() => null),
        ]);
        showSummary(devices, states, incidents, health);
        showDevices(devices, states);
        showIncidents(incidents);
        showAudit(audit);
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

function showSummary(devices, states, incidents, health) {
    const online = states.filter((s) => s.online).length;
    document.getElementById("sum-devices").textContent = `${online} / ${devices.length}`;
    document.getElementById("sum-devices-detail").textContent = "online / registered";
    const critical = incidents.filter((i) => i.severity === "critical" && i.active).length;
    document.getElementById("sum-incidents").textContent = String(incidents.length);
    document.getElementById("sum-incidents-detail").textContent = `${critical} critical and active`;
    document.getElementById("sum-health").textContent = health && health.status === "UP" ? "UP" : "DOWN";
    const unregistered = states.filter((s) => !devices.some((d) => d.deviceId === s.deviceId)).length;
    document.getElementById("sum-health-detail").textContent =
        unregistered ? `${unregistered} device(s) sending data without being registered` : "API reachable";
}

function showDevices(devices, states) {
    const byId = Object.fromEntries(states.map((s) => [s.deviceId, s]));
    const ids = [...new Set([...devices.map((d) => d.deviceId), ...states.map((s) => s.deviceId)])].sort();
    document.getElementById("devices").replaceChildren(...ids.map((id) => {
        const device = devices.find((d) => d.deviceId === id);
        const state = byId[id];
        const connection = !state ? "never connected"
            : state.online ? `online · ${state.software}` : `offline since ${new Date(state.receivedAt).toLocaleString()}`;
        return el("tr", {},
            el("td", {}, id),
            el("td", {}, device ? device.name : el("em", {}, "not registered")),
            el("td", {}, device?.location || ""),
            el("td", { class: state?.online ? "ok" : "muted" }, connection),
            el("td", {}, device
                ? el("input", { type: "checkbox", checked: device.enabled, onchange: (e) => setEnabled(device, e.target.checked) })
                : el("button", { onclick: () => prefill(id) }, "Register…")));
    }));
}

function prefill(id) {
    const form = document.getElementById("device-form");
    form.deviceId.value = id;
    form.name.focus();
}

async function registerDevice(event) {
    event.preventDefault();
    const form = event.target;
    try {
        await api("/devices", { method: "POST", body: {
            deviceId: form.deviceId.value.trim(), name: form.name.value, location: form.location.value || null } });
        form.reset();
        refresh();
    } catch (error) {
        alert(error.message);
    }
}

async function setEnabled(device, enabled) {
    try {
        await api(`/devices/${device.deviceId}`, { method: "PUT", body: { name: device.name, location: device.location, enabled } });
    } catch (error) {
        alert(error.message);
    }
    refresh();
}

function showIncidents(incidents) {
    const items = sortIncidents(incidents).map((i) => el("li", { class: `incident ${i.severity}${i.active ? "" : " cleared"}` },
        el("strong", {}, `${i.deviceId}: ${i.title}`),
        el("span", { class: "tag" }, i.status),
        i.active ? null : el("span", { class: "tag" }, "condition cleared"),
        el("p", {}, i.detail),
        el("small", {}, `opened ${new Date(i.openedAt).toLocaleString()}${i.occurrences > 1 ? ` · ${i.occurrences} times` : ""}`),
        el("div", { class: "actions" },
            i.status === "open" ? el("button", { onclick: () => act(i.id, "acknowledge") }, "Acknowledge") : null,
            el("button", { onclick: () => act(i.id, "resolve") }, "Resolve…"))));
    document.getElementById("incidents").replaceChildren(...(items.length ? items
        : [el("li", { class: "muted" }, "No unresolved incident.")]));
}

async function act(id, action) {
    let body;
    if (action === "resolve") {
        const note = prompt("What was done? (recorded with your name)");
        if (note === null) return;
        body = { note };
    }
    try {
        await api(`/incidents/${id}/${action}`, { method: "POST", body });
    } catch (error) {
        alert(error.message);
    }
    refresh();
}

async function loadThresholds() {
    const thresholds = await api("/thresholds");
    document.getElementById("thresholds").replaceChildren(...thresholds.map((t) => {
        const min = el("input", { type: "number", step: "any", value: t.min ?? "" });
        const max = el("input", { type: "number", step: "any", value: t.max ?? "" });
        const severity = el("select", {}, ["warning", "critical"].map((s) => el("option", { value: s, selected: s === t.severity }, s)));
        const enabled = el("input", { type: "checkbox", checked: t.enabled });
        const verified = el("input", { type: "checkbox", checked: t.verified });
        const source = el("input", { value: t.source || "", size: 28 });
        const save = async () => {
            try {
                await api(`/thresholds/${t.sensor}`, { method: "PUT", body: {
                    min: min.value === "" ? null : Number(min.value), max: max.value === "" ? null : Number(max.value),
                    severity: severity.value, enabled: enabled.checked, verified: verified.checked, source: source.value } });
                loadThresholds();
            } catch (error) {
                alert(error.message);
            }
        };
        return el("tr", {}, el("td", {}, t.sensor), el("td", {}, min), el("td", {}, max), el("td", {}, severity),
            el("td", {}, enabled), el("td", {}, verified), el("td", {}, source),
            el("td", {}, el("button", { onclick: save }, "Save")));
    }));
}

function showAudit(commands) {
    document.getElementById("audit").replaceChildren(...commands.map((c) => el("tr", {},
        el("td", {}, new Date(c.requestedAt).toLocaleString()),
        el("td", {}, c.deviceId),
        el("td", {}, c.action === "on" ? `on ${c.durationS} s` : "off"),
        el("td", {}, `${c.requestedBy} (${c.requesterRole}${c.clientId ? `, ${c.clientId}` : ""})`),
        el("td", { class: c.decision === "accepted" ? "ok" : "warn", title: pumpReason(c.decisionReason) },
            c.decision + (c.decisionReason ? `: ${c.decisionReason}` : "")),
        el("td", { title: pumpReason(c.deviceReason) },
            c.deviceResult ? c.deviceResult + (c.deviceReason ? `: ${c.deviceReason}` : "") : (c.published ? "waiting…" : "—")))));
}
