import { signIn, signUp, signOut, handleRedirect, token } from "./auth.js";
import { startAssistant, stopAssistant } from "./assistant.js";
import { API } from "./api.js";
import { startDashboard, stopDashboard } from "./dashboard.js";

const routes = {
    "/": "pages/welcome.html",
    "/dashboard": "pages/dashboard.html",
    "/about": "pages/about.html",
    "/assistant": "pages/assistant.html",
};
const needsSignIn = new Set(["/dashboard", "/assistant"]);

async function render() {
    const path = window.location.hash.slice(1) || "/";
    if (needsSignIn.has(path) && !token()) {
        window.location.hash = "#/";
        return;
    }
    const file = routes[path] ?? routes["/"];
    stopDashboard();
    stopAssistant();
    document.getElementById("main").innerHTML = await (await fetch(file)).text();

    const signedIn = token() !== null;
    document.getElementById("signin").hidden = signedIn;
    document.getElementById("signup").hidden = signedIn;
    document.getElementById("signout").hidden = !signedIn;

    if (path === "/assistant") startAssistant();
    if (path === "/dashboard") {
        await showMe();
        await startDashboard();
    }
}

// Calls the protected API endpoint to prove the token works end to end.
async function showMe() {
    const response = await fetch(`${API}/me`, {
        headers: { Authorization: `Bearer ${token()}` },
    });
    const me = response.ok ? await response.json() : { username: `error ${response.status}` };
    document.getElementById("who").textContent = me.username;
}

document.getElementById("signin").addEventListener("click", signIn);
document.getElementById("signup").addEventListener("click", signUp);
document.getElementById("signout").addEventListener("click", signOut);
window.addEventListener("hashchange", render);

if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js");

try {
    await handleRedirect();
} catch (e) {
    alert(e.message);
}
render();