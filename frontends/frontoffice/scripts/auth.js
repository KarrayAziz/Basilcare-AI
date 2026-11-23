// OAuth 2.0 authorization code + PKCE against the BasilCare IAM.
// The two frontends use sibling API/IAM names. Preserve a custom HTTPS port.
const appRoot = new URL("../", import.meta.url);
const service = (name, path) => {
    const url = new URL(path, appRoot);
    if (/^(www|admin)\./.test(appRoot.hostname)) {
        url.hostname = appRoot.hostname.replace(/^(www|admin)\./, `${name}.`);
    }
    return url.href;
};
export const API = service("api", "/api");
const config = {
    clientId: "basilcare-pwa-farmer",
    iam: service("iam", "/iam"),
    redirectUri: appRoot.href,   // must equal tenant.farmer.redirect
};

const base64url = (bytes) =>
    btoa(String.fromCharCode(...new Uint8Array(bytes)))
        .replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");

const randomString = () => base64url(crypto.getRandomValues(new Uint8Array(32)));

export async function signIn() {
    const verifier = randomString();
    const state = randomString();
    sessionStorage.setItem(`${config.clientId}.pkce`, JSON.stringify({ verifier, state }));
    const challenge = base64url(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier)));
    const query = new URLSearchParams({
        response_type: "code",
        client_id: config.clientId,
        redirect_uri: config.redirectUri,
        scope: "resource.read resource.write",
        state,
        code_challenge: challenge,
        code_challenge_method: "S256",
    });
    window.location.assign(`${config.iam}/authorize?${query}`);
}

export function signUp() {
    window.location.assign(`${config.iam}/register?client_id=${config.clientId}`);
}

export function signOut() {
    sessionStorage.removeItem(`${config.clientId}.token`);
    window.location.assign(config.redirectUri);
}

// Called on every page load: if the IAM sent us back with ?code=..., exchange it for a token.
export async function handleRedirect() {
    const query = new URLSearchParams(window.location.search);
    if (!query.has("code")) return;
    const saved = JSON.parse(sessionStorage.getItem(`${config.clientId}.pkce`) || "{}");
    sessionStorage.removeItem(`${config.clientId}.pkce`);
    window.history.replaceState({}, "", config.redirectUri);  // keep /farmer/, remove ?code
    if (query.get("state") !== saved.state) throw new Error("Sign-in answer does not match the request.");

    const response = await fetch(`${config.iam}/oauth/token`, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({
            grant_type: "authorization_code",
            code: query.get("code"),
            client_id: config.clientId,
            redirect_uri: config.redirectUri,
            code_verifier: saved.verifier,
        }),
    });
    if (!response.ok) throw new Error("Sign-in failed.");
    sessionStorage.setItem(`${config.clientId}.token`, (await response.json()).access_token);
}

// The token if present and not expired, otherwise null.
export function token() {
    const value = sessionStorage.getItem(`${config.clientId}.token`);
    if (!value) return null;
    const payload = JSON.parse(atob(value.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
    if (payload.exp * 1000 < Date.now()) {
        sessionStorage.removeItem(`${config.clientId}.token`);
        return null;
    }
    return value;
}
