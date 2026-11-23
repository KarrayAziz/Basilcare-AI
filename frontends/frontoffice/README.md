# Frontoffice — Farmer PWA

Served by WildFly at <https://www.basilcare.test/>. Start the Compose stack as documented
in [deploy/](../../deploy/README.md); no separate frontend server is required.

API requests go to `https://api.basilcare.test/api`, and sign-in/signup use
`https://iam.basilcare.test/iam`. Login returns to this app's root. Custom base domains
and HTTPS ports are derived from the frontend URL.

Login storage and offline caches stay on this app's origin. Backend endpoints enforce
roles and explicitly allow the two frontend origins through CORS.
