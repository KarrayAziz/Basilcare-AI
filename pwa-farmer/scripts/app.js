import { signIn, signUp, signOut, handleRedirect, token } from "./auth.js";

const routes = {
    "/": "pages/welcome.html",
    "/dashboard": "pages/dashboard.html",
    "/about": "pages/about.html",
};
const needsSignIn = new Set(["/dashboard"]);

async function render() {
    const path = window.location.hash.slice(1) || "/";
    if (needsSignIn.has(path) && !token()) {
        window.location.hash = "#/";
        return;
    }
    const file = routes[path] ?? routes["/"];
    document.getElementById("main").innerHTML = await (await fetch(file)).text();

    const signedIn = token() !== null;
    document.getElementById("signin").hidden = signedIn;
    document.getElementById("signup").hidden = signedIn;
    document.getElementById("signout").hidden = !signedIn;

    if (path === "/dashboard") await showMe();
}

// Calls the protected API endpoint to prove the token works end to end.
async function showMe() {
    const response = await fetch("http://localhost:8080/api/me", {
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