# Frontoffice — Farmer PWA

Served by WildFly at <https://basilcare.test/farmer/>. Start the Compose stack as documented
in [deploy/](../../deploy/README.md); no separate frontend server is required.

The app uses `/api` and `/iam` on the current origin, returns to `/farmer/` after login,
and keeps its token, PKCE verifier, installed-app scope and offline cache separate from
the Admin app. Backend endpoints still enforce the actual role permissions.
