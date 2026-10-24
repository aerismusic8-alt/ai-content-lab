#!/usr/bin/env python3
"""One-time YouTube authorisation, so later uploads need no browser.

Run this once. It prints a URL; open it in a browser, approve, and the refresh
token is saved. After that `publish_youtube.py` uploads unattended.

    python3 scripts/yt_auth.py --url-only          # just print the URL
    python3 scripts/yt_auth.py                     # wait for the callback
    python3 scripts/yt_auth.py --check             # verify the saved token

The token is written to `~/.config/content-lab/yt_token.json` (mode 600), never
into the repository. Override the location with YT_TOKEN_PATH.

WHY A CALLBACK SERVER: the sandbox has no browser, so `run_local_server()`
cannot work. Google's OAuth needs a redirect URI registered on the client, and
`urn:ietf:wg:oauth:2.0:oob` was retired in 2022. The client's registered
redirect is a public sandbox URL that forwards to a port inside this container,
so this script listens on that port and lets the browser callback land here.
`--print-redirects` shows exactly which URIs must be registered in the Google
Cloud console for the current sandbox.
"""
from __future__ import annotations

import argparse
import http.server
import json
import os
import secrets
import socket
import sys
import threading
import urllib.parse
import webbrowser

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]
TOKEN_PATH = os.environ.get(
    "YT_TOKEN_PATH", os.path.expanduser("~/.config/content-lab/yt_token.json"))
SANDBOX_HOSTS = [
    "work-1-zcfjbytjdlcldhbg.prod-runtime.all-hands.dev",
    "work-2-zcfjbytjdlcldhbg.prod-runtime.all-hands.dev",
]


def load_client_secrets(path: str | None) -> dict:
    """Accept a file path or the CLIENT_SECRET environment variable."""
    raw = None
    if path:
        with open(path, encoding="utf-8") as fh:
            raw = fh.read()
    elif os.environ.get("CLIENT_SECRET"):
        raw = os.environ["CLIENT_SECRET"]
    if not raw:
        sys.exit("No OAuth client. Set CLIENT_SECRET, or pass --client-secrets FILE.")
    doc = json.loads(raw)
    for key in ("web", "installed"):
        if key in doc:
            return doc[key]
    sys.exit("Client secrets JSON has neither a 'web' nor an 'installed' section.")


def save_token(creds) -> str:
    os.makedirs(os.path.dirname(TOKEN_PATH), exist_ok=True)
    doc = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes or SCOPES),
    }
    fd = os.open(TOKEN_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2)
    return TOKEN_PATH


def load_credentials():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    if not os.path.exists(TOKEN_PATH):
        sys.exit(f"No saved token at {TOKEN_PATH}. Run scripts/yt_auth.py first.")
    creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            save_token(creds)
        else:
            sys.exit("Saved token is not usable. Delete it and authorise again.")
    return creds


class _Catcher(http.server.BaseHTTPRequestHandler):
    """Receives the browser redirect and stashes the authorisation code."""

    result: dict = {}

    def do_GET(self):  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path.rstrip("/") != "/oauth2callback":
            self.send_error(404)
            return
        qs = urllib.parse.parse_qs(parsed.query)
        _Catcher.result = {k: v[0] for k, v in qs.items()}
        ok = "code" in qs
        body = (b"<h2>Authorised. You can close this tab.</h2>" if ok
                else f"<h2>Failed: {qs.get('error', ['unknown'])[0]}</h2>".encode())
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--client-secrets", help="path to the client secrets JSON")
    ap.add_argument("--redirect-uri", default=os.environ.get("YT_REDIRECT_URI"),
                    help="must match a URI registered on the OAuth client")
    ap.add_argument("--port", type=int, default=12001,
                    help="local port the callback lands on (default 12001)")
    ap.add_argument("--url-only", action="store_true",
                    help="print the URL and exit, without waiting")
    ap.add_argument("--manual-code", action="store_true",
                    help="read the code from stdin instead of waiting for a callback")
    ap.add_argument("--check", action="store_true",
                    help="verify the saved token against the API and exit")
    ap.add_argument("--print-redirects", action="store_true",
                    help="print the redirect URIs to register, then exit")
    args = ap.parse_args()

    if args.print_redirects:
        print("Add these under APIs & Services > Credentials > your OAuth client")
        print("> Authorised redirect URIs, then save:\n")
        for host in SANDBOX_HOSTS:
            print(f"  https://{host}/oauth2callback")
        print("\nThese hostnames change when the sandbox is recreated, so the")
        print("redirect URI has to be re-registered whenever the pod changes.")
        return 0

    if args.check:
        from googleapiclient.discovery import build
        creds = load_credentials()
        yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
        res = yt.channels().list(part="snippet,contentDetails", mine=True).execute()
        items = res.get("items", [])
        if not items:
            print("Token works, but this account has no YouTube channel.")
            return 1
        ch = items[0]
        print("token OK")
        print("  channel:", ch["snippet"]["title"])
        print("  id:     ", ch["id"])
        print("  uploads:", ch["contentDetails"]["relatedPlaylists"]["uploads"])
        return 0

    client = load_client_secrets(args.client_secrets)
    from google_auth_oauthlib.flow import Flow

    if not args.redirect_uri:
        sys.exit("Pass --redirect-uri (see --print-redirects), or set YT_REDIRECT_URI.")
    if args.redirect_uri not in client.get("redirect_uris", []):
        print("WARNING: this redirect URI is not in the client's registered list:")
        print(f"  {args.redirect_uri}")
        print("Google will refuse with redirect_uri_mismatch. Register it first:")
        print("  python3 scripts/yt_auth.py --print-redirects\n")

    flow = Flow.from_client_config({"web": client}, scopes=SCOPES,
                                   redirect_uri=args.redirect_uri)
    url, _ = flow.authorization_url(access_type="offline", prompt="consent",
                                    state=secrets.token_urlsafe(16))

    print("Open this URL in a browser and approve access:\n")
    print(url)
    print()

    if args.url_only:
        print("Then re-run without --url-only to finish.")
        return 0

    if args.manual_code:
        code = input("Paste the value of the ?code= parameter: ").strip()
        flow.fetch_token(code=urllib.parse.unquote(code))
    else:
        port = args.port
        probe = socket.socket()
        if probe.connect_ex(("127.0.0.1", port)) == 0:
            probe.close()
            sys.exit(f"Port {port} is already in use; the callback cannot land. "
                     f"Pick another with --port and register a matching URI.")
        probe.close()

        httpd = http.server.ThreadingHTTPServer(("0.0.0.0", port), _Catcher)
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        print(f"Waiting for the callback on port {port} ...")
        try:
            webbrowser.open(url)
        except Exception:
            pass
        while not _Catcher.result:
            t.join(1)
        httpd.shutdown()

        if "code" not in _Catcher.result:
            sys.exit(f"Authorisation failed: {_Catcher.result}")
        flow.fetch_token(code=_Catcher.result["code"])

    creds = flow.credentials
    if not creds.refresh_token:
        sys.exit("Google returned no refresh token. Re-run with prompt=consent "
                 "(the default) and revoke the app's access first if needed.")
    path = save_token(creds)
    print(f"\nSaved to {path} (mode 600). Uploads can now run unattended.")
    print("Verify with: python3 scripts/yt_auth.py --check")
    return 0


if __name__ == "__main__":
    sys.exit(main())
