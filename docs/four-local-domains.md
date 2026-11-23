# Four local application names

The professor requested separate local names for the two frontends and two middleware
applications. All four names can point to the same computer and the same WildFly instance.
No cloud account, paid domain or public DNS registration is needed for this local setup.

| Application | URL |
|---|---|
| Farmer PWA | `https://www.basilcare.test/` |
| Administrator PWA | `https://admin.basilcare.test/` |
| REST API | `https://api.basilcare.test/api/` |
| Authentication | `https://iam.basilcare.test/iam/` |

## Name resolution and certificate

Add this line to `/etc/hosts` on Linux/macOS, or
`C:\Windows\System32\drivers\etc\hosts` on Windows (administrator permission required):

```text
127.0.0.1 basilcare.test www.basilcare.test admin.basilcare.test api.basilcare.test iam.basilcare.test
```

The bare name remains an application chooser and a compatibility/readiness address.
The root `start.sh` offers to add missing names; simply editing repository files does
not change the computer's hosts file. This is local name resolution, not a DNS server.

WildFly's generated self-signed certificate includes all these names. An older generated
certificate is replaced once on upgrade. Copy/trust the new certificate again using
the startup instructions. Operator-supplied keystores are preserved and must cover
all application names too. Trust the certificate before testing login, installation
and offline use; accepting an individual warning is not a substitute for trusting
cross-origin API/IAM connections.

## Routing and browser requests

Undertow serves the two frontend directories at `/` on separate virtual hosts. The
existing backend host accepts the `api` and `iam` aliases and retains the `/api` and
`/iam` WAR contexts. The aliases are not exclusive routing/security boundaries: both
backend contexts remain available on that shared backend host. Internal Node-RED and
JWKS requests continue using `http://wildfly:8080/api` and local `/iam` URLs.

The frontend auth module derives the sibling API/IAM names from its own URL and keeps
any nonstandard port. OAuth return addresses are exactly the Farmer/Admin roots.
Compose supplies them through `TENANT_FARMER_REDIRECT` and `TENANT_ADMIN_REDIRECT`;
the existing IAM startup code updates registered clients on restart.

API and IAM explicitly allow only `FARMER_ORIGIN` and `ADMIN_ORIGIN` in CORS. Browser
preflight requests are answered before authentication; actual protected API requests
still require a valid token and the correct role. Service workers cannot intercept
requests to the other origins.

## Migration

1. Review `deploy/.env`: defaults are `TLS_HOSTNAME=basilcare.test`,
   `FARMER_ORIGIN=https://www.basilcare.test` and
   `ADMIN_ORIGIN=https://admin.basilcare.test` (no trailing slash).
   `start.sh` adds missing frontend origin settings without replacing secrets.
2. Add/approve the hosts entries and recreate WildFly with the new image. Before a
   released image includes this PR, use `bash start.sh --build` when choosing to test it.
3. Trust the regenerated certificate and open the new frontend URLs. Previously
   installed PWAs use the old origin: uninstall/reinstall them at the new addresses.
   Existing sessions are not copied across origins; sign in again.

For another base domain, change `TLS_HOSTNAME`, `PUBLIC_ORIGIN` (chooser address) and
both frontend origins together. For `HTTPS_PORT=8443`, include `:8443` in every public
origin. This does not require moving application folders, resetting MongoDB or changing
MQTT topics. Legacy `/farmer/` and `/admin/` paths remain available for static readiness
checks, but use the new names for login: their old callback URLs are no longer registered.

## Verification and provenance

`node --test frontends/frontoffice/test/*.mjs frontends/backoffice/test/*.js` checks
frontend identity, callbacks and offline caching. The hosting CI checks all names over
verified HTTPS, both PKCE flows, allowed/disallowed CORS origins and protected API access
before and after a restart. `python3 deploy/hosting_smoke_test.py` runs these server checks
against an already running stack; it does not create accounts or devices.

This extends the professor's supplied WildFly CLI examples and the team's previous
hosting work. OpenAI Codex assisted Aziz Karray with routing, frontend configuration,
CORS handling, certificate migration, tests and documentation. The prompt journal is
left for the team to complete separately.
