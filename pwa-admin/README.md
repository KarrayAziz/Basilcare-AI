# pwa-admin

Served by WildFly at <http://localhost:8080/admin/>. Start the Compose stack as documented
in [deploy/](../deploy/README.md); no separate frontend server is required.

The app uses `/api` and `/iam` on the current origin, returns to `/admin/` after login,
and keeps its token, PKCE verifier, installed-app scope and offline cache separate from
the Farmer app. Backend endpoints still enforce the actual role permissions.
