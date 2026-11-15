# BasilCare IAM

Account registration, email activation, OAuth authorization-code login with PKCE,
and Ed25519 access tokens. The deployment is `iam.war` on WildFly.

## Administrator account management

| Method | Path | Body | Success |
|---|---|---|---|
| `DELETE` | `/iam/accounts/{username}` | None | `204` |
| `PATCH` | `/iam/accounts/{username}` | `role` and/or `active` | `204` |

Both endpoints require `Authorization: Bearer <token>` obtained through the Admin
PWA (`basilcare-pwa-admin`). Tokens are checked for signature, issuer, expiry,
audience and Admin role. The caller must also still exist as an active Admin in
MongoDB; a token issued before a demotion, disabling or deletion does not preserve
account-management privileges.

Examples (development URLs):

```bash
# Promote an already activated user. Roles are case-sensitive: Admin or Farmer.
curl -i -X PATCH http://localhost:8080/iam/accounts/farmer1 \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"role":"Admin"}'

# Disable an account. Omitted properties are preserved.
curl -i -X PATCH http://localhost:8080/iam/accounts/farmer1 \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"active":false}'

# Delete an account, including your own if another active Admin remains.
curl -i -X DELETE http://localhost:8080/iam/accounts/admin \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

### Last active administrator invariant

An operation that would delete, disable or demote the last **active** Admin returns
`409` with no account mutation:

```json
{
  "error": "last_active_admin",
  "message": "Cannot delete, disable or demote the last active administrator."
}
```

Inactive Admins do not count as replacements. The rule applies regardless of who
the target is. A lone Admin may promote an activated Farmer first, then remove
their own administrator access. Email activation cannot be bypassed using PATCH.

Other errors: `400` for an invalid update, `401` for a missing/invalid Admin-client
token, `403` if the caller is no longer an active Admin, and `404` for an unknown
target. Errors use JSON fields `error` and `message`. Password hashes and activation
codes are never returned by these endpoints. There is no account-management UI yet.

### Concurrency and deployment scope

`AccountManagementService` is an EJB singleton with a WRITE lock. WildFly serializes
the caller check, last-admin check and database write across these management
requests **within one IAM instance**, matching the current Compose deployment.
Two administrators cannot concurrently remove one another through these endpoints
on that instance. This is not a distributed database transaction: multiple IAM
replicas require database-level coordination before deployment. Direct database
edits bypass the rule.

Existing API access tokens remain usable until expiry under the API's existing
stateless verification. The live-account check applies to the new IAM management
endpoints; this change does not add global token revocation. The initial Admin
still comes from `ADMIN_PASSWORD` during startup.

## Verification

With JDK 25 and Maven:

```bash
mvn --file iam/pom.xml clean verify
```

Unit tests exercise account mutations with an in-memory repository substitute and
cryptographic token validation. They do not start WildFly or MongoDB. IAM CI runs
the same build for changes in this module.

## Assistance provenance for this change

The account-management endpoints, last-active-admin rule, tests, CI workflow and
this documentation were generated with OpenAI Codex under Aziz Karray's direction.
This records the scope of assistance without certifying team-wide authorship
percentages; the mandatory root `ATTRIBUTION.md` still needs the team's input.
