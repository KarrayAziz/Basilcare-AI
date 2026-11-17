const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..", "..");
const read = (...parts) => fs.readFileSync(path.join(root, ...parts), "utf8");
const manifest = (app) => JSON.parse(read(app, "manifest.webmanifest"));

test("the Farmer PWA has the Farmer identity and OAuth client", () => {
    assert.equal(manifest("frontoffice").name, "BasilCare Farmer");
    assert.equal(manifest("frontoffice").short_name, "BasilCare Farmer");
    assert.match(read("frontoffice", "index.html"), /<title>BasilCare Farmer<\/title>/);
    assert.match(read("frontoffice", "sw.js"), /basilcare-farmer-v\d+/);
    assert.match(read("frontoffice", "scripts", "auth.js"), /clientId: "basilcare-pwa-farmer"/);
});

test("the Admin PWA has the Admin identity and OAuth client", () => {
    assert.equal(manifest("backoffice").name, "BasilCare Admin");
    assert.equal(manifest("backoffice").short_name, "BasilCare Admin");
    assert.match(read("backoffice", "index.html"), /<title>BasilCare Admin<\/title>/);
    assert.match(read("backoffice", "sw.js"), /basilcare-admin-v\d+/);
    assert.match(read("backoffice", "scripts", "auth.js"), /clientId: "basilcare-pwa-admin"/);
});

test("the Admin PWA does not expose public Farmer registration", () => {
    assert.doesNotMatch(read("backoffice", "index.html"), /id="signup"|>Sign up</);
    assert.doesNotMatch(read("backoffice", "scripts", "app.js"), /signUp|signup/);
    assert.doesNotMatch(read("backoffice", "scripts", "auth.js"), /register\?|function signUp/);
});

test("the two dashboards contain role-specific content", () => {
    const farmer = read("frontoffice", "pages", "dashboard.html");
    const admin = read("backoffice", "pages", "dashboard.html");

    assert.match(farmer, /pH/);
    assert.match(farmer, /Water level/);
    assert.match(farmer, /Active alerts/);
    assert.match(admin, /Connected devices/);
    assert.match(admin, /Active users/);
    assert.match(admin, /Open incidents/);
    assert.doesNotMatch(admin, /<h3>pH<\/h3>/);
});
