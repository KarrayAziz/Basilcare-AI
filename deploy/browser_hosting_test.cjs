// Real browser origin/CORS check against the isolated CI stack; no account/device creation.
// TLS certificate/hostname validation is covered separately by hosting_smoke_test.py.
const assert = require("node:assert/strict");
const { chromium } = require("playwright");

(async () => {
    const browser = await chromium.launch({ headless: true });
    const context = await browser.newContext({ ignoreHTTPSErrors: true });
    try {
        for (const [app, host] of [["farmer", "www"], ["admin", "admin"]]) {
            const page = await context.newPage();
            await page.goto(`https://${host}.basilcare.test/`);
            if (app === "farmer") {
                const anonymous = await page.evaluate(async () => (await fetch("https://api.basilcare.test/api/assistant/ask", {
                    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({question:"basil light"})
                })).status);
                assert.equal(anonymous, 401);
            }
            await page.getByRole("button", { name: "Sign in", exact: true }).click();
            await page.waitForURL("https://iam.basilcare.test/iam/authorize?**");
            await page.locator('[name="username"]').fill("admin");
            await page.locator('[name="password"]').fill("change-me-now");
            await page.getByRole("button", { name: "Sign in", exact: true }).click();
            await page.waitForURL(`https://${host}.basilcare.test/`);
            await page.getByRole("button", { name: "Sign out", exact: true }).waitFor({ state: "visible" });
            const me = await page.evaluate(async (app) => {
                const token = sessionStorage.getItem(`basilcare-pwa-${app}.token`);
                const response = await fetch("https://api.basilcare.test/api/me", {
                    headers: { Authorization: `Bearer ${token}` },
                });
                if (!response.ok) throw new Error(`API returned ${response.status}`);
                return response.json();
            }, app);
            assert.equal(me.username, "admin");
            assert.equal(me.admin, true);
            if (app === "farmer") {
                await page.getByRole("link", {name:"Assistant",exact:true}).click();
                await page.locator("#assistant-question").fill("How should I prune basil?");
                await page.locator("#assistant-send").click();
                await page.getByRole("status").filter({hasText:"unavailable or busy"}).waitFor();
                // Test UI rendering with a scripted answer; CI never calls Gemini.
                await page.route("https://api.basilcare.test/api/assistant/ask", route => route.fulfill({
                    status:200, contentType:"application/json", headers:{"Access-Control-Allow-Origin":"https://www.basilcare.test"},
                    body:JSON.stringify({status:"answered",answer:"<img src=x onerror=alert(1)> Pinch tips.",
                        citations:[{title:"NC State",url:"https://plants.ces.ncsu.edu/plants/ocimum-basilicum/",text:"Pinch tips."},
                            {title:"Bad link",url:"javascript:alert(1)",text:"ignored"}]})
                }));
                await page.locator("#assistant-send").click();
                await page.getByRole("status").filter({hasText:"Answer ready"}).waitFor();
                assert.match(await page.locator(".assistant-answer").textContent(), /<img/);
                assert.equal(await page.locator("#assistant-messages img").count(),0);
                assert.equal(await page.locator("#assistant-messages a").count(),1);
                await page.unroute("https://api.basilcare.test/api/assistant/ask");
            }
            await page.getByRole("button", { name: "Sign out", exact: true }).click();
            await page.getByRole("button", { name: "Sign in", exact: true }).waitFor({ state: "visible" });
            assert.equal(new URL(page.url()).origin, `https://${host}.basilcare.test`);
            await page.close();
            console.log(`[ok] ${app}: browser login, cross-origin token/API requests and logout`);
        }
    } finally {
        await context.close();
        await browser.close();
    }
})().catch((error) => { console.error(error); process.exitCode = 1; });
