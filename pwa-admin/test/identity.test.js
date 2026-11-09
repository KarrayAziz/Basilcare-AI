const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..", "..");
const read = (...parts) => fs.readFileSync(path.join(root, ...parts), "utf8");
const manifest = (app) => JSON.parse(read(app, "manifest.webmanifest"));

test("the Farmer PWA has the Farmer identity and OAuth client", () => {
    assert.equal(manifest("pwa-farmer").name, "BasilCare Farmer");
    assert.equal(manifest("pwa-farmer").short_name, "BasilCare Farmer");
    assert.match(read("pwa-farmer", "index.html"), /<title>BasilCare Farmer<\/title>/);
    assert.match(read("pwa-farmer", "sw.js"), /basilcare-farmer-v\d+/);
    assert.match(read("pwa-farmer", "scripts", "auth.js"), /clientId: "basilcare-pwa-farmer"/);
});

test("the Admin PWA has the Admin identity and OAuth client", () => {
    assert.equal(manifest("pwa-admin").name, "BasilCare Admin");
    assert.equal(manifest("pwa-admin").short_name, "BasilCare Admin");
    assert.match(read("pwa-admin", "index.html"), /<title>BasilCare Admin<\/title>/);
    assert.match(read("pwa-admin", "sw.js"), /basilcare-admin-v\d+/);
    assert.match(read("pwa-admin", "scripts", "auth.js"), /clientId: "basilcare-pwa-admin"/);
});

test("the Admin PWA does not expose public Farmer registration", () => {
    assert.doesNotMatch(read("pwa-admin", "index.html"), /id="signup"|>Sign up</);
    assert.doesNotMatch(read("pwa-admin", "scripts", "app.js"), /signUp|signup/);
    assert.doesNotMatch(read("pwa-admin", "scripts", "auth.js"), /register\?|function signUp/);
});

test("the two dashboards contain role-specific content", () => {
    const farmer = read("pwa-farmer", "pages", "dashboard.html");
    const admin = read("pwa-admin", "pages", "dashboard.html");

    assert.match(farmer, /pH/);
    assert.match(farmer, /Water level/);
    assert.match(farmer, /Active alerts/);
    assert.match(admin, /Connected devices/);
    assert.match(admin, /Active users/);
    assert.match(admin, /Open incidents/);
    assert.doesNotMatch(admin, /<h3>pH<\/h3>/);
});
