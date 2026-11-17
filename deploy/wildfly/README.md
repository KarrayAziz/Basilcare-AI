# Serve the PWAs from WildFly

WildFly's Undertow subsystem serves the actual frontend files:

| URL | Content |
|---|---|
| `/` | application chooser (`welcome/index.html`) |
| `/farmer/` | `pwa-farmer/` |
| `/admin/` | `pwa-admin/` |
| `/api/` | existing API WAR |
| `/iam/` | existing IAM WAR |

This follows the professor's requirement to serve frontends through WildFly. The CLI uses
the same file-handler and location operations as the supplied `default-host.cli` and
`add-host.cli`, adapted to a single origin with separate paths. `add-api.cli` is unnecessary
here: both WARs retain their existing names and context paths on the default host.

## Configuration and deployment

Compose mounts the frontend folders and this configuration directory read-only. `start.sh`
first runs `configure.cli` using WildFly's embedded administrative server, then starts the
normal server. Existing handlers/locations are updated rather than added again, so restarting
the container is safe. Configuration also survives container replacement because it is
reapplied from Git. No public management port is needed.

`HOSTING_ENV=dev` selects `pwas-dev.properties`; `HOSTING_ENV=prod` selects
`pwas-prod.properties`. Their paths are identical inside Docker because Compose mounts the
same container directories in both environments. A bare-metal installation can supply
its own properties file via `BASILCARE_HOSTING_PROPERTIES` when invoking `start.sh`.

For development, run the normal Compose command and open:

- <http://localhost:8080/farmer/>
- <http://localhost:8080/admin/>

For production, set `PUBLIC_ORIGIN=https://your-domain.example` without a trailing slash in
`deploy/.env`, together with `HOSTING_ENV=prod`, then recreate the WildFly service. Compose
derives the exact registered IAM return addresses (`PUBLIC_ORIGIN/farmer/` and
`PUBLIC_ORIGIN/admin/`) and allowed browser origin. `StartupData` updates existing tenant
records from this configuration at startup.

These scripts do not create DNS records or HTTPS certificates. A production TLS proxy may
terminate HTTPS, but it must forward the frontend files to WildFly too, and preserve
`/farmer/`, `/admin/`, `/api/` and `/iam/`. It must preserve the public Host and scheme;
configure WildFly's listener proxy forwarding only behind a trusted proxy if necessary.
Do not expose HTTP-only PWAs on a public IP: service workers and browser cryptography need
HTTPS outside localhost. The previous Live Server ports 5500/5501 are no longer configured.

## Login, installation and offline behavior

- Each auth module derives its app root from its own script URL. It uses that same root for
  the OAuth callback, removal of the authorization code, and logout.
- Session storage keys include the OAuth client ID. Signing out of one app does not delete
  the other app's login state in the same browser tab.
- Manifests use relative start URLs and scopes. Workers resolve cached assets under their
  own registration scope and only remove their own cache names.
- Workers do not intercept API, IAM or the other PWA's requests. Old API answers are never
  served from cache.
- Routes use URL hashes, so no catch-all 404 rewrite is needed. Missing scripts must remain
  404 responses rather than receiving an HTML fallback.

The two apps share an origin, so this is logical UI/storage separation, not an additional
security boundary. The API and IAM continue to enforce roles and signatures.

## Verification

```bash
# Unit checks for paths, callbacks, session separation and cache isolation
node pwa-farmer/test/hosting.test.mjs

# Real server assets plus login/token exchange for both clients (WildFly + MongoDB running)
python3 deploy/hosting_smoke_test.py

# Asset-only post-deployment check, without administrator credentials
python3 deploy/hosting_smoke_test.py --static-only
```

The hosting CI starts isolated Compose services and runs the server check before and after
a restart. Browser checks should additionally verify both app installations, sign-in/out,
hash routes and offline navigation. Previously installed root-scoped development apps may
need to be uninstalled/reinstalled at their new URLs.

## Provenance

The file-handler/location configuration is adapted from the three `.cli` examples supplied
by Mohamed-Bécha Kaâniche in his email requiring WildFly frontend hosting. OpenAI Codex
assisted Aziz Karray with the adaptation, frontend path changes, tests and documentation.
The team's root attribution declaration should include this source and assistance when
the draft is finalized.
