import { api, el } from "./api.js";

const sourceURLs = new Set([
    "https://plants.ces.ncsu.edu/plants/ocimum-basilicum/",
    "https://extension.usu.edu/yardandgarden/research/basil-in-the-garden",
]);
let cancel = () => {};
export function stopAssistant() { cancel(); cancel = () => {}; }

export function startAssistant() {
    const form = document.getElementById("assistant-form");
    const question = document.getElementById("assistant-question");
    const send = document.getElementById("assistant-send");
    const status = document.getElementById("assistant-status");
    const messages = document.getElementById("assistant-messages");
    const controller = new AbortController();
    cancel = () => controller.abort();
    let busy = false;
    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const text = question.value.trim();
        if (busy || controller.signal.aborted) return;
        if (!text || text.length > 2000) {
            status.textContent = "Enter a question between 1 and 2000 characters.";
            return;
        }
        busy = true;
        send.disabled = true;
        status.textContent = "Finding an answer…";
        try {
            const result = await api("/assistant/ask", { method: "POST", body: { question: text }, signal: controller.signal });
            if (controller.signal.aborted) return;
            const sources = (result.citations || []).filter(c => sourceURLs.has(c.url));
            const entry = el("article", { class: "card assistant-message" },
                el("h2", {}, "You asked"), el("p", {}, text),
                el("h2", {}, "Assistant"), el("p", { class: "assistant-answer" }, result.answer));
            if (sources.length) entry.append(el("h3", {}, "Sources"), el("ul", {}, sources.map(c =>
                el("li", {}, el("a", { href: c.url, target: "_blank", rel: "noopener noreferrer" }, c.title)))));
            messages.append(entry);
            // Keep only this page's most recent ten exchanges; never persist chat history.
            while (messages.children.length > 10) messages.firstElementChild.remove();
            question.value = "";
            status.textContent = "Answer ready. Check the sources before applying advice.";
        } catch (error) {
            if (controller.signal.aborted) return;
            if (error.status === 401) document.getElementById("signin").hidden = false;
            status.textContent = error.status === 401 ? "Your session expired. Please sign in again."
                : error.status === 429 ? "Too many questions. Wait a minute and try again."
                : error.status === 403 ? "This account cannot use the assistant."
                : error.status === 503 ? "The assistant is unavailable or busy. Try again later."
                : "Could not get an answer. Check your connection and try again.";
        } finally {
            busy = false;
            send.disabled = false;
        }
    });
}
