#!/usr/bin/env python3
"""One-time OAuth2 setup for the Upwork API. Run this locally after your app
is approved at upwork.com/developer/keys/apply, to turn your Upwork login
into a refresh token the pipeline can use unattended.

Usage:
    python3 scripts/upwork_authorize.py <client_id> <client_secret> <redirect_uri>

<redirect_uri> must exactly match one registered on the app. If you didn't
set up a real callback server, register something like
http://localhost:8765/callback — you'll just be copying the `code` query
param out of the browser's address bar by hand after it redirects there
(the page itself doesn't need to load).

Prints a refresh token at the end — save it to pods.secrets.yaml (local
runs) or the UPWORK_REFRESH_TOKEN GitHub Actions secret (CI). It doesn't
expire under normal use; re-run this script only if it's ever revoked.
"""
import sys
from urllib.parse import urlencode

import requests

AUTHORIZE_URL = "https://www.upwork.com/ab/account-security/oauth2/authorize"
TOKEN_URL = "https://www.upwork.com/api/v3/oauth2/token"
SCOPES = "pub-time-sheet:read:all pub-commons:read:all"


def main():
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(1)

    client_id, client_secret, redirect_uri = sys.argv[1:4]

    auth_url = f"{AUTHORIZE_URL}?" + urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": SCOPES,
        }
    )
    print("1. Open this URL, log in, and approve access:\n")
    print(f"   {auth_url}\n")
    print("2. You'll be redirected to your redirect_uri with a ?code=... param.")
    print("   Paste just that code value below (the page itself doesn't need to load).\n")

    code = input("Authorization code: ").strip()

    resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
        },
    )
    if not resp.ok:
        print(f"\nToken exchange failed ({resp.status_code}): {resp.text}", file=sys.stderr)
        sys.exit(1)

    tokens = resp.json()
    print("\nSuccess. Save this refresh token:\n")
    print(f"   {tokens['refresh_token']}\n")
    print("Add it to pods.secrets.yaml as upwork_refresh_token, or the")
    print("UPWORK_REFRESH_TOKEN GitHub Actions secret.")


if __name__ == "__main__":
    main()
