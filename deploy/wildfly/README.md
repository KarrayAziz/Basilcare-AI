# Serve the PWAs from WildFly

WildFly's Undertow subsystem serves the actual frontend files:

| URL | Content |
|---|---|
| `/` | application chooser (`welcome/index.html`) |
| `/farmer/` | `frontends/frontoffice/` |
| `/admin/` | `frontends/backoffice/` |
| `/api/` | existing API WAR |
| `/iam/` | existing IAM WAR |

This follows the professor's requirement to serve frontends through WildFly. The CLI uses
the same file-handler and location operations as the supplied `default-host.cli` and
`add-host.cli`, adapted to a single origin with separate paths. `add-api.cli` is unnecessary
here: both WARs retain their existing names and context paths on the default host.

## Configuration and deployment

The [`Dockerfile`](Dockerfile) builds `iam.war` and `api.war` and copies them, both frontend
folders and this directory into `quay.io/wildfly/wildfly:42.0.0.Final-jdk25`. CI publishes it
for amd64 and arm64 as `ghcr.io/karrayaziz/basilcare-wildfly`. The development override
(`deploy/compose.dev.yaml`) mounts local WARs, frontends and this directory over the copies.
`start.sh` first runs `configure.cli` using WildFly's embedded administrative server, then starts the
normal server. Existing handlers/locations are updated rather than added again, so restarting
the container is safe. Configuration also survives container replacement because it is
reapplied from Git. No public management port is needed.

`HOSTING_ENV=dev` selects `pwas-dev.properties`; `HOSTING_ENV=prod` selects
`pwas-prod.properties`. Their paths are identical inside Docker because Compose mounts the
same container directories in both environments. A bare-metal installation can supply
its own properties file via `BASILCARE_HOSTING_PROPERTIES` when invoking `start.sh`.

Open:

- <https://basilcare.test/farmer/>
- <https://basilcare.test/admin/>

On another domain, set `PUBLIC_ORIGIN=https://your-domain.example` without a trailing slash
and `TLS_HOSTNAME=your-domain.example` in `deploy/.env`, then recreate the WildFly service. Compose
derives the exact registered IAM return addresses (`PUBLIC_ORIGIN/farmer/` and
`PUBLIC_ORIGIN/admin/`) and allowed browser origin. `StartupData` updates existing tenant
records from this configuration at startup.

## HTTPS

`start.sh` creates a self-signed certificate on first start (`keytool`, RSA 2048, 397 days,
SAN `TLS_HOSTNAME`, `localhost`, `127.0.0.1`) in `/opt/jboss/wildfly/certs`, a named volume, so it
survives restarts and container replacement and only has to be trusted once. It is replaced
only when `TLS_HOSTNAME` or `TLS_KEYSTORE_PASSWORD` changes. A keystore placed there by an
operator (a CA-issued certificate) is never overwritten. `configure.cli` adds the Elytron
`basilcareKS` key store, `basilcareKM` key manager and `basilcareSSC` SSL context (TLS 1.3/1.2)
and attaches it to Undertow's `https` listener (8443, published as host port 443). The keystore
password stays an expression (`${env.TLS_KEYSTORE_PASSWORD}`) resolved from the container
environment, so it is never written into `standalone.xml`.

The browser must resolve the name: add `127.0.0.1  basilcare.test` to `/etc/hosts` (macOS/Linux)
or `C:\Windows\System32\drivers\etc\hosts` (Windows, as administrator); the root `start.sh` offers to.
Trusting `deploy/certs/basilcare.crt` (macOS keychain / Windows user root store; `start.sh` offers
to) removes the browser warning. Without it, sign-in works after accepting the warning, but
service workers, and therefore installation and offline use, do not.

These scripts do not create DNS records or CA-issued certificates. A production TLS proxy may
terminate HTTPS instead, but it must forward the frontend files to WildFly too, and preserve
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
node frontends/frontoffice/test/hosting.test.mjs

# Real server assets plus login/token exchange for both clients (WildFly + MongoDB running)
python3 deploy/hosting_smoke_test.py

# Asset-only post-deployment check, without administrator credentials
python3 deploy/hosting_smoke_test.py --static-only
```

The hosting CI builds the image, starts isolated Compose services, resolves `basilcare.test`
through `/etc/hosts`, and runs the server check over verified HTTPS before and after a restart
(the second run also proves the certificate was kept). Browser checks should additionally verify both app installations, sign-in/out,
hash routes and offline navigation. Previously installed root-scoped development apps may
need to be uninstalled/reinstalled at their new URLs.

## Provenance

The file-handler/location configuration is adapted from the three `.cli` examples supplied
by Mohamed-Bécha Kaâniche in his email requiring WildFly frontend hosting. OpenAI Codex
assisted Aziz Karray with the adaptation, frontend path changes, tests and documentation.
The team's root attribution declaration should include this source and assistance when
the draft is finalized.
