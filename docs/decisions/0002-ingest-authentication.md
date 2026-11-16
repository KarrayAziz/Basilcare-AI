# ADR 0002: Node-RED authenticates to the API with a service key

**Status:** proposed · **Date:** 2026-11-15

## Context

Node-RED forwards device messages to the API (`POST /api/ingest/*`). Nobody is signed in: there is no user and no browser. The IAM issues tokens through the authorization-code flow, which needs a person to type a password.

## Decision

- The `/api/ingest/*` endpoints are bound to `IngestKeyFilter` (`@IngestKeyRequired`), not to the user `SecurityFilter`.
- Node-RED sends `X-Ingest-Key: <key>`. The API compares it in constant time with `INGEST_KEY` from its environment.
- **Fail closed**: without a configured key, ingestion answers 503.
- The key is never in the repository. Development uses a default from `deploy/compose.yaml`; production sets it in `deploy/.env`.
- The ingest endpoints only accept device data. They cannot read anything, change the registry, or control the pump.

## Alternatives considered

- **OAuth 2.0 client-credentials grant in the IAM.** It is the standard answer and the better long-term option, but it is not implemented in the IAM yet. Moving to it later only changes `IngestKeyFilter` and the Node-RED request node.
- **The API subscribes to MQTT itself (no Node-RED in the path).** This contradicts the architecture of the scope (§4.1: Node-RED normalises and routes) and duplicates the contract checks.

## Consequences

- One shared secret per environment. Rotating it means changing `.env` and restarting WildFly and Node-RED.
- A leaked key would let an attacker inject fake readings, but not read data or move the pump. The device ACL on the broker (contract §9) protects the earlier hop.
