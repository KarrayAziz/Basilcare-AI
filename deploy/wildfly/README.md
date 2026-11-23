# Serve the PWAs from WildFly

WildFly's Undertow subsystem serves the actual frontend files:

| URL | Content |
|---|---|
| `https://www.basilcare.test/` | `frontends/frontoffice/` |
| `https://admin.basilcare.test/` | `frontends/backoffice/` |
| `https://api.basilcare.test/api/` | API WAR |
| `https://iam.basilcare.test/iam/` | IAM WAR |
| `https://basilcare.test/` | application chooser |

The CLI adapts the professor's `default-host.cli` and `add-host.cli` examples into
frontend virtual hosts and API/IAM aliases on the existing backend host. The WAR names
and contexts stay unchanged for internal services. See [four-domain setup and migration](../../docs/four-local-domains.md)
for hosts entries, CORS, callback URLs and compatibility details.

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

Open <https://www.basilcare.test/> and <https://admin.basilcare.test/>.
For another domain or port, set `TLS_HOSTNAME`, `PUBLIC_ORIGIN`, `FARMER_ORIGIN` and
`ADMIN_ORIGIN` together in `deploy/.env`, then recreate WildFly. IAM startup updates
its two registered return addresses from Compose configuration.

## HTTPS

`start.sh` creates a self-signed certificate on first start (`keytool`, RSA 2048, 397 days,
SAN base domain, `www`, `admin`, `api`, `iam`, `localhost`, `127.0.0.1`) in `/opt/jboss/wildfly/certs`, a named volume, so it
survives restarts and container replacement and only has to be trusted once. It is replaced
when its hostname set or `TLS_KEYSTORE_PASSWORD` changes. The first upgrade to four
names also regenerates an older generated certificate; trust the replacement again. A keystore placed there by an
operator (a CA-issued certificate) is never overwritten. `configure.cli` adds the Elytron
`basilcareKS` key store, `basilcareKM` key manager and `basilcareSSC` SSL context (TLS 1.3/1.2)
and attaches it to Undertow's `https` listener (8443, published as host port 443). The keystore
password stays an expression (`${env.TLS_KEYSTORE_PASSWORD}`) resolved from the container
environment, so it is never written into `standalone.xml`.

The browser must resolve the name: add all five names listed in the four-domain guide to `/etc/hosts` (macOS/Linux)
or `C:\Windows\System32\drivers\etc\hosts` (Windows, as administrator); the root `start.sh` offers to.
Trusting `deploy/certs/basilcare.crt` (macOS keychain / Windows user root store; `start.sh` offers
to) removes the browser warning. Trust is needed for cross-origin API/IAM requests as well as PWA installation and offline use.

These scripts do not create DNS records or CA-issued certificates. A production TLS proxy may
terminate HTTPS instead, but it must forward the frontend files to WildFly too, and preserve
the application Host headers and the `/api/` and `/iam/` contexts. It must preserve the public Host and scheme;
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

The two apps use separate browser origins. Backend aliases share their host; hostnames
do not replace authorization. The API and IAM continue to enforce roles and signatures.

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
