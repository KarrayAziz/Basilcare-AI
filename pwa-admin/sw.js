// Cache the app shell so the PWA opens offline. Change the name to force an update.
const CACHE = "basilcare-admin-v2";
const SHELL = [
    "/", "/index.html", "/styles/main.css", "/scripts/app.js", "/scripts/auth.js",
    "/pages/welcome.html", "/pages/dashboard.html", "/pages/about.html", "/images/icon.svg",
];

self.addEventListener("install", (event) => {
    event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(SHELL)));
});

self.addEventListener("activate", (event) => {
    event.waitUntil(caches.keys().then((names) =>
        Promise.all(names.filter((n) => n !== CACHE).map((n) => caches.delete(n)))));
});

// Network first (fresh data when online), cache as fallback (offline)
self.addEventListener("fetch", (event) => {
    if (event.request.method !== "GET") return;
    event.respondWith(fetch(event.request).catch(() => caches.match(event.request)));
});
