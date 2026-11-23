import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import vm from "node:vm";

const folders = { farmer: "frontoffice", admin: "backoffice" };
const origin = "https://basilcare.example";

test("both apps keep their own redirect paths, PKCE secrets and login sessions", async () => {
    const saved = new Map();
    let destination;
    let replaced;
    globalThis.window = {
        location: { origin, search: "", assign: (url) => { destination = url; } },
        history: { replaceState: (_state, _title, url) => { replaced = url; } },
    };
    globalThis.sessionStorage = {
        getItem: (key) => saved.get(key) ?? null,
        setItem: (key, value) => saved.set(key, value),
        removeItem: (key) => saved.delete(key),
    };
    const originalFetch = globalThis.fetch;
    const modules = {};
    try {
        for (const app of ["farmer", "admin"]) {
            const root = `https://${app === "farmer" ? "www" : "admin"}.basilcare.example/`;
            const source = await fs.readFile(new URL(`../../${folders[app]}/scripts/auth.js`, import.meta.url), "utf8");
            const code = source.replaceAll("import.meta.url", JSON.stringify(root + "scripts/auth.js"));
            const auth = await import("data:text/javascript;base64," + Buffer.from(code).toString("base64"));
            modules[app] = auth;
            assert.equal(auth.API, "https://api.basilcare.example/api");
            await auth.signIn();
            const login = new URL(destination);
            assert.equal(login.origin + login.pathname, "https://iam.basilcare.example/iam/authorize");
            assert.equal(login.searchParams.get("redirect_uri"), root);
            const pending = JSON.parse(saved.get(`basilcare-pwa-${app}.pkce`));
            window.location.search = "?" + new URLSearchParams({ code: "test-code", state: pending.state });
            const token = Buffer.from(JSON.stringify({ exp: 4102444800 })).toString("base64url");
            const pass = `header.${token}.${app}`;
            globalThis.fetch = async (address, request) => {
                assert.equal(address, "https://iam.basilcare.example/iam/oauth/token");
                assert.equal(request.body.get("redirect_uri"), root);
                assert.equal(request.body.get("code_verifier"), pending.verifier);
                return { ok: true, json: async () => ({ access_token: pass }) };
            };
            await auth.handleRedirect();
            assert.equal(replaced, root);
            assert.equal(auth.token(), pass);
            assert.equal(saved.has(`basilcare-pwa-${app}.pkce`), false);
        }
        assert.notEqual(modules.farmer.token(), modules.admin.token());
        modules.farmer.signOut();
        assert.equal(destination, "https://www.basilcare.example/");
        assert.equal(modules.farmer.token(), null);
        assert.notEqual(modules.admin.token(), null, "Farmer logout must preserve the Admin session");
        modules.admin.signOut();
        assert.equal(destination, "https://admin.basilcare.example/");
    } finally {
        globalThis.fetch = originalFetch;
        delete globalThis.window;
        delete globalThis.sessionStorage;
    }
});

for (const app of ["farmer", "admin"]) {
    test(`${app} offline cache stays inside its path and preserves the other app's cache`, async () => {
        const scope = `https://${app === "farmer" ? "www" : "admin"}.basilcare.example/`;
        const other = app === "farmer" ? "admin" : "farmer";
        const handlers = {};
        let cached;
        const deleted = [];
        const sandbox = {
            URL,
            self: { registration: { scope }, addEventListener: (event, handler) => { handlers[event] = handler; } },
            caches: {
                open: async () => ({ addAll: async (urls) => { cached = urls; } }),
                keys: async () => [`basilcare-${app}-v0`, `basilcare-${other}-v4`, "another-app"],
                delete: async (name) => { deleted.push(name); },
                match: async () => "offline content",
            },
            fetch: async () => { throw new Error("offline"); },
        };
        vm.runInNewContext(await fs.readFile(new URL(`../../${folders[app]}/sw.js`, import.meta.url), "utf8"), sandbox);
        let pending;
        handlers.install({ waitUntil: (promise) => { pending = promise; } });
        await pending;
        assert.ok(cached.length > 10);
        assert.ok(cached.every((url) => url.startsWith(scope)));
        for (const url of cached) {
            await fs.access(new URL(`../../${folders[app]}/${url.slice(scope.length) || "index.html"}`, import.meta.url));
        }
        handlers.activate({ waitUntil: (promise) => { pending = promise; } });
        await pending;
        assert.deepEqual(deleted, [`basilcare-${app}-v0`]);
        for (const url of ["https://api.basilcare.example/api/me", "https://iam.basilcare.example/iam/oauth/token",
                           `https://${other === "farmer" ? "www" : "admin"}.basilcare.example/index.html`]) {
            handlers.fetch({ request: { method: "GET", url },
                respondWith: () => assert.fail("worker intercepted another app or a backend request") });
        }
        handlers.fetch({ request: { method: "GET", url: scope + "pages/welcome.html" },
            respondWith: (promise) => { pending = promise; } });
        assert.equal(await pending, "offline content");
        const manifest = JSON.parse(await fs.readFile(new URL(`../../${folders[app]}/manifest.webmanifest`, import.meta.url)));
        assert.equal(new URL(manifest.start_url, scope).href, scope);
        assert.equal(new URL(manifest.scope, scope).href, scope);
    });
}


test("sibling service names preserve a custom domain and HTTPS port", async () => {
    const source = await fs.readFile(new URL("../scripts/auth.js", import.meta.url), "utf8");
    for (const [root, expected] of [
        ["https://www.farm.example:9443/", "https://api.farm.example:9443/api"],
        ["https://admin.farm.example:9443/", "https://api.farm.example:9443/api"],
        ["http://localhost:8080/farmer/", "http://localhost:8080/api"],
    ]) {
        const code = source.replaceAll("import.meta.url", JSON.stringify(root + "scripts/auth.js"));
        const auth = await import("data:text/javascript;base64," + Buffer.from(code).toString("base64"));
        assert.equal(auth.API, expected);
    }
});
