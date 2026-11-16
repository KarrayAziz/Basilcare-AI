// Pure presentation logic (no DOM, no network), unit-tested in test/view.test.mjs.

/** "12 s ago", "3 min ago", "2 h ago". */
export function age(seconds) {
    if (seconds < 60) return `${Math.max(0, Math.round(seconds))} s ago`;
    if (seconds < 3600) return `${Math.round(seconds / 60)} min ago`;
    return `${Math.round(seconds / 3600)} h ago`;
}

/** "pH 6.05", "1.40 mS/cm", "24.1 °C", "60.5 %RH". */
export function formatValue(value, unit) {
    if (unit === "pH") return `pH ${value.toFixed(2)}`;
    if (unit === "mS/cm") return `${value.toFixed(2)} mS/cm`;
    if (unit === "degC") return `${value.toFixed(1)} °C`;
    return `${value.toFixed(1)} ${unit}`;
}

/**
 * Position of a live value against the administrator's alert range:
 * "ok", "low", "high", or "unknown" (no enabled range for this sensor).
 */
export function rangeStatus(value, threshold) {
    if (!threshold || !threshold.enabled) return "unknown";
    if (threshold.min !== null && threshold.min !== undefined && value < threshold.min) return "low";
    if (threshold.max !== null && threshold.max !== undefined && value > threshold.max) return "high";
    return "ok";
}

export function rangeText(threshold) {
    if (!threshold || !threshold.enabled) return "no alert range";
    const min = threshold.min ?? "–";
    const max = threshold.max ?? "–";
    return `range ${min} to ${max}${threshold.verified ? "" : " (not verified)"}`;
}

/** Why the API or the device refused a pump command, in words a farmer understands. */
export const PUMP_REASONS = {
    device_not_registered: "This device is not registered. Ask an administrator.",
    device_disabled: "This device is disabled in the registry.",
    device_offline: "The device is offline, so starting the pump cannot be confirmed.",
    pump_fault: "The pump is in fault. Maintenance is needed on the device.",
    duration_too_long: "The duration is above the allowed maximum.",
    water_level_unknown: "No recent water-level reading: the pump could run dry.",
    low_water_level: "The water level is too low. Refill the reservoir first.",
    broker_unavailable: "The command could not be sent (message broker unavailable). Try again.",
    expired: "The command reached the device too late and was refused.",
    invalid_command: "The device refused the command as invalid.",
    duration_elapsed: "Stopped automatically: the requested duration is over.",
};

export function pumpReason(reason) {
    return PUMP_REASONS[reason] || reason || "";
}

/**
 * SVG polyline points for a history chart. Points: [{measured_at, value, buffered}].
 * Returns {line, dots: [{x, y, buffered}], min, max} scaled into width x height with a margin.
 */
export function chart(points, width, height, margin = 6) {
    if (!points.length) return { line: "", dots: [], min: null, max: null };
    const times = points.map((p) => Date.parse(p.measured_at));
    const values = points.map((p) => p.value);
    const t0 = Math.min(...times);
    const t1 = Math.max(...times);
    let min = Math.min(...values);
    let max = Math.max(...values);
    if (min === max) {
        min -= 1;
        max += 1;
    }
    const x = (t) => margin + (t1 === t0 ? (width - 2 * margin) / 2 : ((t - t0) / (t1 - t0)) * (width - 2 * margin));
    const y = (v) => height - margin - ((v - min) / (max - min)) * (height - 2 * margin);
    const dots = points.map((p, i) => ({ x: x(times[i]), y: y(p.value), buffered: p.buffered }));
    return { line: dots.map((d) => `${d.x.toFixed(1)},${d.y.toFixed(1)}`).join(" "), dots, min, max };
}

/** New unresolved incidents since the previous poll, for browser notifications. */
export function newIncidents(previousIds, incidents) {
    return incidents.filter((i) => !previousIds.has(i.id) && i.active);
}

export const SEVERITY_ORDER = { critical: 0, warning: 1 };

export function sortIncidents(incidents) {
    return [...incidents].sort((a, b) =>
        (SEVERITY_ORDER[a.severity] ?? 9) - (SEVERITY_ORDER[b.severity] ?? 9)
        || Number(b.active) - Number(a.active)
        || b.openedAtEpoch - a.openedAtEpoch);
}
