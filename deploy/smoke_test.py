"""End-to-end smoke test of the running stack (scope section 8.4, demonstration checklist).

Checks, against a real WildFly + MongoDB + Mosquitto + Node-RED + simulator:
  1. sign-in as admin through the IAM (authorization code + PKCE, like the PWAs)
  2. the simulated device is registered
  3. telemetry flows device -> broker -> Node-RED -> API -> database (live values)
  4. the pH drift raises a threshold incident; acknowledge and resolve it
  5. an authorized pump command is executed by the device and audited
  6. an unsafe pump command (too long) is rejected by the safety policy and audited

Usage (stack running, simulator started with --fault ph-drift on basil-sim-01):
    python deploy/smoke_test.py [--api https://basilcare.test] [--password change-me-now]

The stack's self-signed certificate is trusted through --cafile (default: deploy/certs/basilcare.crt,
which start.sh copies out of the WildFly container).

Standard library only, so it runs anywhere Python 3.10+ is installed.
"""
import argparse
import base64
import hashlib
import json
import os
import secrets
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

DEVICE = "basil-sim-01"
CLIENT = "basilcare-pwa-admin"
DEFAULT_BASE = "https://basilcare.test"
DEFAULT_CAFILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "certs", "basilcare.crt")
SSL_CONTEXT = None


def trust(cafile):
    """Verify HTTPS against this certificate file (the stack's self-signed certificate)."""
    global SSL_CONTEXT
    if cafile and os.path.exists(cafile):
        SSL_CONTEXT = ssl.create_default_context(cafile=cafile)
    elif cafile and cafile != DEFAULT_CAFILE:
        raise SystemExit(f"certificate file not found: {cafile}")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def call(method, url, token=None, body=None, form=None, expect=None):
    headers = {}
    data = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    if form is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        data = urllib.parse.urlencode(form).encode()
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    opener = urllib.request.build_opener(NoRedirect, urllib.request.HTTPSHandler(context=SSL_CONTEXT))
    try:
        with opener.open(request, timeout=15) as response:
            status, text, location = response.status, response.read().decode(), response.headers.get("Location")
    except urllib.error.HTTPError as error:
        status, text, location = error.code, error.read().decode(), error.headers.get("Location")
    if expect and status not in expect:
        raise AssertionError(f"{method} {url} -> {status} (expected {expect}): {text[:300]}")
    try:
        payload = json.loads(text) if text else None
    except ValueError:
        payload = text
    return status, payload, location


def sign_in(api, password, redirect=None):
    redirect = redirect or api.rstrip("/") + "/admin/"
    verifier = secrets.token_urlsafe(32)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    query = urllib.parse.urlencode({
        "client_id": CLIENT, "redirect_uri": redirect, "response_type": "code",
        "code_challenge": challenge, "code_challenge_method": "S256",
        "scope": "resource.read resource.write", "state": "smoke"})
    status, _, location = call("POST", f"{api}/iam/login?{query}",
                               form={"username": "admin", "password": password}, expect={303})
    code = urllib.parse.parse_qs(urllib.parse.urlparse(location).query)["code"][0]
    _, token, _ = call("POST", f"{api}/iam/oauth/token", expect={200}, form={
        "grant_type": "authorization_code", "code": code, "client_id": CLIENT,
        "redirect_uri": redirect, "code_verifier": verifier})
    return token["access_token"]


def wait_for(description, probe, timeout=90):
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = probe()
        if result:
            return result
        time.sleep(2)
    raise AssertionError(f"timed out waiting for {description}")


def step(text):
    print(f"[ok] {text}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--api", default=DEFAULT_BASE)
    parser.add_argument("--cafile", default=DEFAULT_CAFILE, help="certificate to trust for HTTPS")
    parser.add_argument("--password", default="change-me-now", help="ADMIN_PASSWORD of the IAM")
    parser.add_argument("--redirect-uri", help="Registered Admin return URL if different from --api/admin/")
    args = parser.parse_args()
    api = args.api.rstrip("/")
    trust(args.cafile)

    token = sign_in(api, args.password, args.redirect_uri)
    step("signed in as admin (authorization code + PKCE)")

    status, _, _ = call("POST", f"{api}/api/devices", token,
                        {"deviceId": DEVICE, "name": "Simulated gateway", "location": "laptop"}, expect={201, 409})
    step(f"device {DEVICE} registered ({'created' if status == 201 else 'already there'})")

    live = wait_for("live telemetry", lambda: (lambda r: r if len(r) >= 6 else None)(
        call("GET", f"{api}/api/telemetry/latest?deviceId={DEVICE}", token, expect={200})[1]))
    step("live telemetry: " + ", ".join(f"{r['sensor']}={r['value']}" for r in live))

    _, history, _ = call("GET", f"{api}/api/telemetry/history?deviceId={DEVICE}&sensor=ph", token, expect={200})
    times = [p["measured_at"] for p in history["points"]]
    assert times == sorted(times), "history must be ordered by measured_at"
    step(f"pH history: {len(times)} points, ordered by measured_at")

    def threshold_incident():
        _, found, _ = call("GET", f"{api}/api/incidents?deviceId={DEVICE}", token, expect={200})
        return next((i for i in found if i["type"] == "threshold" and i["sensor"] == "ph"), None)

    incident = wait_for("pH threshold incident (simulator --fault ph-drift)", threshold_incident, timeout=120)
    step(f"incident raised: {incident['title']} - {incident['detail']}")
    call("POST", f"{api}/api/incidents/{incident['id']}/acknowledge", token, expect={200})
    _, resolved, _ = call("POST", f"{api}/api/incidents/{incident['id']}/resolve", token,
                          {"note": "Smoke test: pH corrected."}, expect={200})
    assert resolved["status"] == "resolved" and resolved["resolvedBy"] == "admin"
    step("incident acknowledged and resolved with a note")

    status, _, _ = call("POST", f"{api}/api/pump/{DEVICE}/commands", token, {"action": "on", "duration_s": 30},
                        expect={428})
    step("pump command without confirmation refused (428)")

    _, accepted, _ = call("POST", f"{api}/api/pump/{DEVICE}/commands", token,
                          {"action": "on", "duration_s": 30, "confirm": True}, expect={202})
    command_id = accepted["commandId"]

    def device_answer():
        _, audit, _ = call("GET", f"{api}/api/pump/commands?deviceId={DEVICE}", token, expect={200})
        record = next(c for c in audit if c["commandId"] == command_id)
        return record if record.get("deviceResult") else None

    record = wait_for("the device's answer on pump/state", device_answer, timeout=30)
    assert record["deviceResult"] == "executed", record
    _, pump, _ = call("GET", f"{api}/api/pump/{DEVICE}", token, expect={200})
    step(f"pump command executed by the device and audited (state now {pump['state']})")

    _, rejected, _ = call("POST", f"{api}/api/pump/{DEVICE}/commands", token,
                          {"action": "on", "duration_s": 5000, "confirm": True}, expect={409})
    assert rejected["decisionReason"] == "duration_too_long"
    step("unsafe pump command rejected by the safety policy and audited (duration_too_long)")

    call("POST", f"{api}/api/pump/{DEVICE}/commands", token, {"action": "off", "confirm": True}, expect={202})
    step("pump stopped")
    print("\nSMOKE TEST PASSED")


if __name__ == "__main__":
    try:
        main()
    except (AssertionError, KeyError, urllib.error.URLError) as error:
        sys.exit(f"\nSMOKE TEST FAILED: {error}")
