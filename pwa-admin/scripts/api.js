// Calls to the BasilCare REST API with the signed-in user's token.
import { token } from "./auth.js";

// Same machine in development. On the server, the reverse proxy serves the API on the PWA's origin.
export const API = window.location.hostname === "localhost" ? "http://localhost:8080/api" : "/api";

export class ApiError extends Error {
    constructor(status, body) {
        super((body && body.message) || `HTTP ${status}`);
        this.status = status;
        this.body = body;
    }
}

export async function api(path, { method = "GET", body } = {}) {
    const response = await fetch(API + path, {
        method,
        headers: {
            Authorization: `Bearer ${token()}`,
            ...(body === undefined ? {} : { "Content-Type": "application/json" }),
        },
        body: body === undefined ? undefined : JSON.stringify(body),
    });
    const text = await response.text();
    let data = null;
    try {
        data = text ? JSON.parse(text) : null;
    } catch {
        data = { message: text };
    }
    // the pump endpoint answers 409 with the audit record of a rejected request: not an exception
    if (!response.ok && !(response.status === 409 && data && data.commandId)) {
        throw new ApiError(response.status, data);
    }
    return data;
}

/** Builds a DOM element. Text is always inserted as text, never as HTML (device data is untrusted). */
export function el(tag, attributes = {}, ...children) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(attributes)) {
        if (value === undefined || value === null || value === false) continue;
        if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
        else if (key === "class") node.className = value;
        else node.setAttribute(key, value === true ? "" : value);
    }
    for (const child of children.flat()) {
        if (child === null || child === undefined || child === false) continue;
        node.append(child instanceof Node ? child : document.createTextNode(String(child)));
    }
    return node;
}
