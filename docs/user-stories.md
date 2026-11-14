# User stories

XP backlog (scope §7.3). One story per GitHub Issue: copy the title, the story and the acceptance criteria. Estimates are in ideal person-days and should be revised in the planning game. **Status** reflects branch `amir/phase1-telemetry-incidents-edge`.

Legend: ✅ done and tested · 🟡 done, needs a manual check or hardware · ⬜ to do

## Monitoring (FR-01, FR-02)

| # | Story | Acceptance criteria | Est. | Status |
|---|---|---|---|---|
| US-01 | As a **farmer**, I want to see the current pH, EC, temperatures, humidity and water level, so that I know whether the solution needs attention. | Values refresh within 10 s; each shows its unit, age, alert range, "not calibrated" and "not reporting" flags; values sent late are never shown as live. | 2 | 🟡 API ✅, PWA needs a browser check |
| US-02 | As an **agronomist**, I want the 24 h history of one sensor, so that I can explain a drift. | Chart ordered by measurement time; late (buffered) points visible as such; `from`/`to` query parameters. | 1.5 | 🟡 |
| US-03 | As a **farmer**, I want readings collected during a network outage to be kept, so that the history has no hole. | Pi queues on disk; broker down 25 s → no `seq` gap, late readings flagged `buffered`. | 2 | ✅ (live test) |
| US-04 | As an **operator**, I want the real probes read and calibrated, so that the values are trustworthy. | pH 2-point, EC reference solution, level empty/full; `calibrated: true` only with calibration values. | 3 | ⬜ needs the sensors (drivers written) |

## Incidents and alerts (FR-03, FR-04)

| # | Story | Acceptance criteria | Est. | Status |
|---|---|---|---|---|
| US-05 | As a **farmer**, I want an alert when a value leaves its range, so that I act before the plants suffer. | One incident per condition (not one per reading); reactivated if it comes back; buffered readings never raise one. | 2 | ✅ |
| US-06 | As a **farmer**, I want to know when a sensor or the device stops reporting, so that I do not trust stale values. | `stale` after 3 × interval while online; `offline` from the Last Will or a clean goodbye; `invalid_message` for broken data. | 1.5 | ✅ |
| US-07 | As a **farmer**, I want to acknowledge an alert and record how I fixed it, so that the team knows what happened. | Acknowledge (who, when); resolve requires a 3 to 500 character note; a resolved incident cannot be acknowledged again. | 1 | ✅ API, 🟡 PWA |
| US-08 | As a **farmer**, I want a notification on my phone for a new alert. | Browser notification while the app is open ✅; Web Push to a closed app ⬜. | 2 | 🟡 |
| US-09 | As an **administrator**, I want to set the alert range of each sensor and record its source, so that alerts are agronomically justified. | Admin-only PUT; min < max inside the plausible range; "verified" requires a source; seeded defaults flagged unverified. | 1 | ✅ API, 🟡 PWA |

## Pump control

| # | Story | Acceptance criteria | Est. | Status |
|---|---|---|---|---|
| US-10 | As a **farmer**, I want to start the pump for a chosen time and stop it, so that I can circulate the solution remotely. | Confirmation required (428 otherwise); 202 when sent; the device's answer is shown. | 2 | ✅ (smoke test) |
| US-11 | As a **farmer**, I want an unsafe start to be refused with the reason, so that the pump never runs dry. | Refused when not registered, disabled, offline, in fault, too long, water level unknown/stale or low; explained in plain words. | 1.5 | ✅ |
| US-12 | As an **administrator**, I want every control request audited, so that each action is attributable (scope §6.2). | Record before sending: user, role, client app, time, expiry, API decision, device result; rejections included. | 1 | ✅ |
| US-13 | As an **operator**, I want the pump to stop by itself even without network. | Device stops after `duration_s` and on low water; relay off at start and at shutdown. | 1 | ✅ (unit tests), 🟡 relay on hardware |

## Edge AI (FR-05)

| # | Story | Acceptance criteria | Est. | Status |
|---|---|---|---|---|
| US-14 | As a **team**, we want a labelled basil-leaf dataset, so that the model can be trained and evaluated. | ≥ 50 good pictures per class, captured with the deployment camera; duplicates removed; 70/15/15 split. | 3 | ⬜ (tools ready) |
| US-15 | As a **farmer**, I want each leaf screening shown with its confidence and "review required" when unsure, so that I am never misled. | Quality checks; confidence < 0.7 or poor picture → review required; model version in every result. | 2 | ✅ (no model yet) |
| US-16 | As a **team**, we want the model evaluated on held-out pictures and benchmarked on the Pi. | Confusion matrix, per-class P/R/F1, coverage above threshold; median and p95 latency on the Pi. | 1 | ⬜ after US-14 (scripts ready) |

## Assistant (FR-06, FR-07)

| # | Story | Acceptance criteria | Est. | Status |
|---|---|---|---|---|
| US-17 | As a **farmer**, I want to ask a cultivation question and get an answer with its sources. | Curated, openly licensed corpus; every claim cites a passage; "I don't know" when unsupported. | 4 | ⬜ |
| US-18 | As a **farmer**, I want the assistant to read my sensor history and alerts. | MCP tools call the API with the user's token (same roles). | 2 | ⬜ |
| US-19 | As an **administrator**, I want the assistant to *request* a pump action only after I confirm, and never bypass the safety policy. | MCP tool → `POST /api/pump/...` with confirm only after a user step; the refusal case is demonstrated. | 2 | ⬜ (API ready) |
| US-20 | As a **team**, we want prompts, model versions, retrieval ids, tool calls and evaluation results traced (LLMOps). | Traces stored with sensitive values minimised; test set for groundedness, citations, authorisation, unsafe-action refusal. | 3 | ⬜ |

## Platform (FR-08, FR-09)

| # | Story | Acceptance criteria | Est. | Status |
|---|---|---|---|---|
| US-21 | As an **administrator**, I want to register, disable and see the connection state of devices. | Register form; enable toggle; devices sending data without registration are listed. | 1 | 🟡 |
| US-22 | As an **administrator**, I want to manage user accounts without locking out the last admin. | (Aziz, branch `aziz/protect-last-admin`) | 2 | 🟡 in review |
| US-23 | As an **agronomist**, I want reports of consumption, water level, uptime and alert frequency. | Per day and per device; MongoDB aggregations. | 2 | ⬜ |
| US-24 | As a **team**, we want a reproducible deployment on a cloud VM. | `setup.sh` + `deploy.sh`; `.env.example`; TLS proxy; broker TLS + ACL; Postman collection passes. | 3 | 🟡 scripts and collection ready, VM not yet |
