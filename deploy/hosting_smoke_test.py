"""Verify real WildFly static hosting and PKCE login without sensors or Node-RED.

Run with WildFly and MongoDB running:
    python3 deploy/hosting_smoke_test.py --base https://basilcare.test --password change-me-now
Standard library only. This reads assets and signs in; it does not change user/device data.
"""
import argparse
import base64
import hashlib
import secrets
import urllib.parse

from smoke_test import DEFAULT_BASE, DEFAULT_CAFILE, application_sites, call, trust


def check(base, password, public_origin=None, static_only=False):
    public_origin = public_origin or base
    sites = application_sites(base)
    public_sites = application_sites(public_origin)
    _, landing, _ = call("GET", base + "/", expect={200})
    assert '/farmer/' in landing and '/admin/' in landing, "landing links missing"
    call("GET", sites["api"] + "/api/health", expect={200})
    call("GET", sites["iam"] + "/iam/jwk", expect={200})
    for app in ("farmer", "admin"):
        root = sites[app] + "/"
        origin = sites[app]
        _, html, _ = call("GET", root, expect={200})
        assert f"BasilCare {app.title()}" in html
        _, manifest, _ = call("GET", root + "manifest.webmanifest", expect={200})
        assert urllib.parse.urljoin(root, manifest["start_url"]) == root
        assert urllib.parse.urljoin(root, manifest["scope"]) == root
        for asset in ("scripts/app.js", "scripts/auth.js", "scripts/api.js", "scripts/view.js",
                      "scripts/dashboard.js", "styles/main.css", "pages/welcome.html",
                      "pages/dashboard.html", "pages/about.html", "images/icon.svg", "sw.js"):
            call("GET", root + asset, expect={200})
        # Missing assets must remain 404s, not be replaced by index.html.
        call("GET", root + "scripts/does-not-exist.js", expect={404})
        if urllib.parse.urlsplit(base).hostname not in {"localhost", "127.0.0.1"}:
            headers = {}
            call("OPTIONS", sites["api"] + "/api/devices", expect={204}, headers={
                "Origin": origin, "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,content-type"}, response_headers=headers)
            assert headers.get("Access-Control-Allow-Origin") == origin, headers
            assert "Authorization" in headers.get("Access-Control-Allow-Headers", "")
            call("OPTIONS", sites["api"] + "/api/devices", expect={403}, headers={
                "Origin": "https://untrusted.invalid", "Access-Control-Request-Method": "POST"})
            call("GET", sites["api"] + "/api/me", expect={401}, headers={"Origin": origin})
        if static_only:
            print(f"[ok] {app}: static assets and scoped manifest")
            continue
        redirect = public_sites[app] + "/"
        verifier = secrets.token_urlsafe(32)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        state = secrets.token_urlsafe(16)
        client = f"basilcare-pwa-{app}"
        query = urllib.parse.urlencode({
            "client_id": client, "redirect_uri": redirect, "response_type": "code",
            "code_challenge": challenge, "code_challenge_method": "S256", "state": state})
        _, _, location = call("POST", sites["iam"] + "/iam/login?" + query,
                               form={"username": "admin", "password": password}, expect={303})
        returned = urllib.parse.urlparse(location)
        assert returned.scheme + "://" + returned.netloc + returned.path == redirect
        parameters = urllib.parse.parse_qs(returned.query)
        assert parameters["state"] == [state]
        headers = {}
        _, result, _ = call("POST", sites["iam"] + "/iam/oauth/token", headers={"Origin": origin}, response_headers=headers, form={
            "grant_type": "authorization_code", "client_id": client, "redirect_uri": redirect,
            "code": parameters["code"][0], "code_verifier": verifier}, expect={200})
        if sites["iam"] != base:
            assert headers.get("Access-Control-Allow-Origin") == origin, headers
        headers = {}
        _, me, _ = call("GET", sites["api"] + "/api/me", token=result["access_token"], expect={200},
                       headers={"Origin": origin}, response_headers=headers)
        if sites["api"] != base:
            assert headers.get("Access-Control-Allow-Origin") == origin, headers
        assert me["username"] == "admin" and me["admin"] is True
        print(f"[ok] {app}: all assets, scoped manifest, PKCE redirect and authenticated API")
    print("HOSTING SMOKE TEST PASSED")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default=DEFAULT_BASE)
    parser.add_argument("--cafile", default=DEFAULT_CAFILE, help="certificate to trust for HTTPS")
    parser.add_argument("--password", default="change-me-now")
    parser.add_argument("--public-origin", help="Registered public origin if it differs from --base")
    parser.add_argument("--static-only", action="store_true", help="Skip login; check only serving/assets")
    args = parser.parse_args()
    trust(args.cafile)
    check(args.base.rstrip("/"), args.password,
          args.public_origin.rstrip("/") if args.public_origin else None, args.static_only)
