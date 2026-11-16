# postman

The Postman collection of the deployed REST API (scope §6.1), with one test script per request.

| File | Content |
|---|---|
| [`BasilCare.postman_collection.json`](BasilCare.postman_collection.json) | 28 requests in 6 folders: public, me and devices, ingest (Node-RED service key), telemetry and screening, incidents and alert ranges, pump control |
| [`BasilCare-local.postman_environment.json`](BasilCare-local.postman_environment.json) | `baseUrl` (http://localhost:8080), `deviceId` (basil-sim-01), `ingestKey` (development value) |

## Why it is organised this way

- **Sign-in is real.** The collection's authorization is OAuth 2.0 *authorization code with PKCE* against the IAM, the same flow as the PWAs, so no token is ever pasted into a file.
- **Every request asserts its status.** The expected refusals have their own requests: 401 without a token, 422 for an invalid reading, 428 for an unconfirmed pump command, 409 for an unsafe one. They document the API's behaviour.
- **The ingest folder uses the service key** (`X-Ingest-Key`), exactly like Node-RED, so the device data path can be tested without the simulator.

## How to use it

1. Postman → *Import* both files, then select the **BasilCare local** environment.
2. Collection → *Authorization* → **Get New Access Token**. Sign in as `admin` (password `change-me-now` in development, `ADMIN_PASSWORD` from `deploy/.env` on the server), then click *Use Token*.
3. Start the simulator (`python simulator/simulator.py --fault ph-drift`) so there are readings and incidents.
4. Run the folders in order, or use the *Collection Runner*.

On the server, duplicate the environment and set `baseUrl` to the public HTTPS address and `ingestKey` to the value in `deploy/.env`.

The collection is generated from the endpoint list. It was not yet run end to end in Postman: the same endpoints are exercised by [`deploy/smoke_test.py`](../deploy/smoke_test.py), which passes.
