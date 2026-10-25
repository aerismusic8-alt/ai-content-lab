#!/usr/bin/env python3
"""One-time YouTube authorisation, so later uploads need no browser.

Run this once. It prints a URL; open it in a browser, approve, and the refresh
token is saved. After that `publish_youtube.py` uploads unattended.

    python3 scripts/yt_auth.py --loopback          # preferred: grant on your PC
    python3 scripts/yt_auth.py --loopback --slug dharma
    python3 scripts/yt_auth.py --url-only          # just print the URL
    python3 scripts/yt_auth.py                     # wait on the sandbox callback
    python3 scripts/yt_auth.py --check             # verify the saved token

The token is written to `~/.config/content-lab/yt_token.json` (mode 600), never
into the repository. Override the location with YT_TOKEN_PATH, or name a channel
with `--slug` to write `yt_token_<slug>.json`.

NO BROWSER NEEDED WHEN A TOKEN IS ALREADY IN THE ENVIRONMENT: an agent session
that has `YT_<SLUG>_REFRESH_TOKEN` (or `YT_REFRESH_TOKEN` / `YOUTUBE_REFRESH_TOKEN`)
plus `YT_CLIENT_ID` / `YT_CLIENT_SECRET` can upload with no human at all. The
first `--check` or upload materialises that refresh token into the token file, so
the rest of the pipeline works unchanged. This is why "the AI cannot post" is
usually a missing token file, not a missing grant.

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
# A loopback redirect is registered once and never changes, unlike a sandbox
# hostname. That is why it is the preferred method: the pod can be recycled
# without the owner touching the Google console again.
LOOPBACK_PORT = 8080
LOOPBACK_REDIRECT = f"http://127.0.0.1:{LOOPBACK_PORT}/oauth2callback"
# The PKCE verifier must survive between `--url-only` and the later run that
# finishes the flow, or the exchange fails with "invalid_grant". It is a
# short-lived secret, so it is written 0600 beside the token and removed on use.
PENDING_PATH = os.path.expanduser("~/.config/content-lab/yt_pending.json")
# The pod's public hostname changes every time the sandbox is recreated, and the
# OAuth client must have the matching redirect URI registered. Reading the host
# from the environment is what stops redirect_uri_mismatch after a recycle; the
# literal list is only a fallback for when the variables are absent.
FALLBACK_HOSTS = [
    "work-1-zcfjbytjdlcldhbg.prod-runtime.all-hands.dev",
    "work-2-zcfjbytjdlcldhbg.prod-runtime.all-hands.dev",
]


def sandbox_hosts() -> list[tuple[str, str]]:
    """Return (host, where it came from), environment first."""
    found: list[tuple[str, str]] = []
    runtime = os.environ.get("RUNTIME_URL", "").strip()
    if runtime:
        found.append((runtime.replace("https://", "").replace("http://", "")
                      .strip("/"), "$RUNTIME_URL"))
    for name in ("WORK_HOST_1", "WORK_HOST_2"):
        value = os.environ.get(name, "").strip()
        if value:
            found.append((value.replace("https://", "").replace("http://", "")
                          .strip("/"), f"${name}"))
    found.extend((h, "fallback list") for h in FALLBACK_HOSTS)
    seen, unique = set(), []
    for host, source in found:
        if host and host not in seen:
            seen.add(host)
            unique.append((host, source))
    return unique


SANDBOX_HOSTS = [h for h, _ in sandbox_hosts()]


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


def save_token(creds, channel: dict | None = None) -> str:
    os.makedirs(os.path.dirname(TOKEN_PATH), exist_ok=True)
    doc = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes or SCOPES),
    }
    if channel:
        # Recorded so a later upload can prove it is targeting the intended
        # channel. Without this, a browser that silently reuses a logged-in
        # account can hand back a token for a different channel.
        doc["channel_id"] = channel.get("id")
        doc["channel_title"] = channel.get("snippet", {}).get("title")
    fd = os.open(TOKEN_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2)
    return TOKEN_PATH


def channel_of(creds) -> dict | None:
    """The channel this token can upload to, or None."""
    from googleapiclient.discovery import build
    yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
    res = yt.channels().list(part="snippet,contentDetails", mine=True).execute()
    items = res.get("items", [])
    return items[0] if items else None


def slug_from_env() -> str | None:
    """Which channel slug this session is meant to post as, if any."""
    for name in ("YT_SLUG", "YT_CHANNEL", "CHANNEL_SLUG"):
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return None


def env_refresh_token(slug: str | None) -> tuple[str, str] | None:
    """Find a refresh token in the environment. Returns (refresh_token, source).

    Checked in order: the slug-specific variable, the numbered `YT_CH<N>_`
    variables, a multi-channel JSON blob, then the generic single-channel
    variables. Returns None when nothing is set, so a session with no credentials
    behaves exactly as before.
    """
    candidates = env_token_candidates(slug)
    return candidates[0] if candidates else None


def env_token_candidates(slug: str | None = None) -> list[tuple[str, str]]:
    """Every refresh token the environment offers, most specific first."""
    out: list[tuple[str, str]] = []
    seen: set[str] = set()

    def add(value: str | None, source: str) -> None:
        value = (value or "").strip()
        if value and value not in seen:
            seen.add(value)
            out.append((value, source))

    if slug:
        upper = slug.upper().replace("-", "_")
        add(os.environ.get(f"YT_{upper}_REFRESH_TOKEN"), f"$YT_{upper}_REFRESH_TOKEN")
        add(os.environ.get(f"YT_CH_{upper}_REFRESH_TOKEN"), f"$YT_CH_{upper}_REFRESH_TOKEN")
    for n in range(1, 9):
        add(os.environ.get(f"YT_CH{n}_REFRESH_TOKEN"), f"$YT_CH{n}_REFRESH_TOKEN")
    blob = os.environ.get("YT_CHANNEL_TOKENS", "").strip()
    if blob:
        try:
            tokens = json.loads(blob)
        except json.JSONDecodeError:
            tokens = {}
        if isinstance(tokens, dict):
            for key, value in tokens.items():
                add(value, f"$YT_CHANNEL_TOKENS[{key}]")
    for name in ("YT_REFRESH_TOKEN", "YOUTUBE_REFRESH_TOKEN"):
        add(os.environ.get(name), f"${name}")
    return out


def _channel_id_for_refresh(refresh_token: str, client: tuple[str, str]) -> str | None:
    """The channel a refresh token belongs to, or None if it cannot be read."""
    import urllib.request
    cid, secret = client
    data = urllib.parse.urlencode({
        "client_id": cid, "client_secret": secret,
        "refresh_token": refresh_token, "grant_type": "refresh_token",
    }).encode()
    try:
        with urllib.request.urlopen("https://oauth2.googleapis.com/token", data=data,
                                    timeout=30) as fh:
            token = json.loads(fh.read().decode()).get("access_token")
        if not token:
            return None
        req = urllib.request.Request(
            "https://www.googleapis.com/youtube/v3/channels?part=id&mine=true",
            headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req, timeout=30) as fh:
            items = json.loads(fh.read().decode()).get("items", [])
        return items[0]["id"] if items else None
    except Exception:
        return None


def client_from_env() -> tuple[str, str] | None:
    """(client_id, client_secret) from the environment, or None."""
    cid = (os.environ.get("YT_CLIENT_ID") or os.environ.get("YOUTUBE_CLIENT_ID") or "").strip()
    secret = (os.environ.get("YT_CLIENT_SECRET") or os.environ.get("YOUTUBE_CLIENT_SECRET") or "").strip()
    return (cid, secret) if cid and secret else None


def materialise_env_token(slug: str | None, expected_channel: str | None = None) -> str | None:
    """Write the environment's refresh token to the token file, if there is one.

    When `expected_channel` is given and the environment holds several tokens, the
    matching one is found by asking Google which channel each belongs to. That
    makes a four-channel secret self-selecting: no channel-to-variable mapping has
    to be configured by hand, and a token for the wrong channel is never used.

    Returns the path it wrote, or None when the environment holds no token.
    """
    candidates = env_token_candidates(slug)
    if not candidates:
        return None
    client = client_from_env()
    if not client:
        sys.exit(f"Found a refresh token in {candidates[0][1]} but no client "
                 f"id/secret. Set YT_CLIENT_ID and YT_CLIENT_SECRET too.")

    chosen = candidates[0]
    if expected_channel:
        for refresh_token, source in candidates:
            if _channel_id_for_refresh(refresh_token, client) == expected_channel:
                chosen = (refresh_token, source)
                break
        else:
            sys.exit(f"No refresh token in the environment belongs to channel "
                     f"{expected_channel}. Authorise that channel first with "
                     f"scripts/yt_auth.py --loopback --slug <slug>.")

    refresh_token, source = chosen
    cid, secret = client
    os.makedirs(os.path.dirname(TOKEN_PATH), exist_ok=True)
    doc = {
        "token": None,
        "refresh_token": refresh_token,
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": cid,
        "client_secret": secret,
        # Deliberately no "scopes": a refresh that names scopes the grant does not
        # hold fails with invalid_scope. The environment's tokens carry the full
        # youtube scope, which is wider than the two this script asks for, so let
        # the grant speak for itself.
        "scopes": None,
    }
    fd = os.open(TOKEN_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2)
    print(f"using refresh token from {source} -> {TOKEN_PATH}")
    return TOKEN_PATH


def _require_google():
    """Import the Google libraries, or exit with the command that installs them."""
    try:
        from google.auth.transport.requests import Request  # noqa: F401
        from google.oauth2.credentials import Credentials  # noqa: F401
        import google_auth_oauthlib.flow  # noqa: F401
        import googleapiclient.discovery  # noqa: F401
    except ModuleNotFoundError as exc:
        sys.exit(f"Missing {exc.name}. Install the Google libraries first:\n"
                 "  pip install -r requirements.txt\n"
                 "  (google-api-python-client, google-auth-oauthlib)")


def load_credentials(expected_channel: str | None = None):
    _require_google()
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    if not os.path.exists(TOKEN_PATH):
        # No file, but the session may already hold a grant. Use it instead of
        # stopping to ask a human for a browser they do not need.
        materialise_env_token(slug_from_env(), expected_channel)
    if not os.path.exists(TOKEN_PATH):
        sys.exit(f"No saved token at {TOKEN_PATH}. Run scripts/yt_auth.py first, "
                 f"or set YT_REFRESH_TOKEN + YT_CLIENT_ID + YT_CLIENT_SECRET.")
    creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if not creds.valid:
        if creds.refresh_token:
            # Refresh must not re-declare scopes: the grant may be wider than
            # SCOPES (the account-wide tokens carry the full `youtube` scope), and
            # asking for a scope the grant lacks returns invalid_scope.
            creds = Credentials(
                token=None, refresh_token=creds.refresh_token,
                token_uri=creds.token_uri or "https://oauth2.googleapis.com/token",
                client_id=creds.client_id, client_secret=creds.client_secret,
                scopes=None)
            creds.refresh(Request())
            save_token(creds)
        else:
            sys.exit("Saved token is not usable and has no refresh token. "
                     "Delete it and authorise again.")
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
    ap.add_argument("--loopback", action="store_true",
                    help="use http://127.0.0.1:<port>/oauth2callback (must be registered; "
                         "this is the URI that never changes)")
    ap.add_argument("--slug", help="channel slug; writes yt_token_<slug>.json "
                                   "and picks YT_<SLUG>_REFRESH_TOKEN from the env")
    ap.add_argument("--url-only", action="store_true",
                    help="print the URL and exit, without waiting")
    ap.add_argument("--manual-code", action="store_true",
                    help="read the code from stdin instead of waiting for a callback")
    ap.add_argument("--check", action="store_true",
                    help="verify the saved token against the API and exit")
    ap.add_argument("--print-redirects", action="store_true",
                    help="print the redirect URIs to register, then exit")
    ap.add_argument("--expected-channel", metavar="CHANNEL_ID",
                    help="fail if the token belongs to a different channel")
    args = ap.parse_args()

    if args.slug:
        # One token file per channel, so two channels never share credentials.
        globals()["TOKEN_PATH"] = os.path.expanduser(
            f"~/.config/content-lab/yt_token_{args.slug}.json")

    if args.print_redirects:
        print("Add these under APIs & Services > Credentials > your OAuth client")
        print("> Authorised redirect URIs, then save:\n")
        print(f"  {LOOPBACK_REDIRECT}   (loopback — register once, never changes)")
        for host, source in sandbox_hosts():
            print(f"  https://{host}/oauth2callback   ({source})")
        if args.loopback:
            print(f"\nPreferred: use --loopback and register ONLY the loopback URI.")
        print("\nThe sandbox hostnames change when the pod is recreated, so those")
        print("URIs need re-registering whenever the pod changes. The loopback URI")
        print("does not.")
        runtime = os.environ.get("RUNTIME_URL", "").strip()
        if runtime:
            bare = runtime.replace("https://", "").replace("http://", "").strip("/")
            printed = {h for h, _ in sandbox_hosts()}
            if bare not in printed:
                sys.exit(f"\nBUG: $RUNTIME_URL ({bare}) is set but missing from the "
                         f"printed list. sandbox_hosts() is not reading the environment.")
            print(f"\n($RUNTIME_URL -> {bare} is in the list above.)")
        return 0

    if args.check:
        creds = load_credentials(args.expected_channel)
        ch = channel_of(creds)
        if not ch:
            print("Token works, but this account has no YouTube channel.")
            return 1
        print("token OK")
        print("  channel:", ch["snippet"]["title"])
        print("  id:     ", ch["id"])
        print("  uploads:", ch["contentDetails"]["relatedPlaylists"]["uploads"])
        if args.expected_channel:
            if ch["id"] != args.expected_channel:
                print(f"\nWRONG CHANNEL: expected {args.expected_channel}, "
                      f"token belongs to {ch['id']}")
                print("The browser may have reused a different logged-in account. "
                      "Re-authorise with the intended account selected.")
                return 2
            print("  matches --expected-channel")
        return 0

    client = load_client_secrets(args.client_secrets)
    from google_auth_oauthlib.flow import Flow

    registered = client.get("redirect_uris", [])
    if args.loopback:
        # The owner runs this on their own machine: the browser lands on their
        # loopback, the code is copied back, and the pod never needs a public
        # hostname. Default to the canonical 8080 that matches the one redirect
        # URI worth registering forever.
        if args.port == 12001:
            args.port = LOOPBACK_PORT
        args.redirect_uri = (args.redirect_uri
                             or f"http://127.0.0.1:{args.port}/oauth2callback")
    if not args.redirect_uri:
        if not registered:
            sys.exit("This OAuth client has no registered redirect URI. Add one:\n"
                     "  python3 scripts/yt_auth.py --print-redirects")
        # Google only accepts a registered URI, so defaulting to one is the only
        # choice that can work without the caller knowing the client's config.
        args.redirect_uri = registered[0]
        print(f"Using the client's registered redirect URI:\n  {args.redirect_uri}")
        print("(pass --redirect-uri or --loopback to choose another)\n")
    if args.redirect_uri not in registered:
        print("WARNING: this redirect URI is not in the client's registered list:")
        print(f"  {args.redirect_uri}")
        print(f"Registered: {registered or 'none'}")
        print("Google will refuse with redirect_uri_mismatch. Register it first:")
        print("  python3 scripts/yt_auth.py --print-redirects\n")
        if not args.loopback:
            print("Tip: omit --redirect-uri to fall back to the registered one.\n")

    flow = Flow.from_client_config({"web": client}, scopes=SCOPES,
                                   redirect_uri=args.redirect_uri)

    # PKCE: the verifier that hashes into this URL's code_challenge must be the
    # same one sent when the code is exchanged. authorization_url() would mint a
    # fresh random verifier, so a verifier saved by an earlier run is loaded here,
    # BEFORE the URL is built — loading it afterwards does not help, because the
    # challenge in the URL would already belong to a different verifier.
    reused = None
    if os.path.exists(PENDING_PATH):
        try:
            with open(PENDING_PATH, encoding="utf-8") as fh:
                pending = json.load(fh)
            if pending.get("redirect_uri") == args.redirect_uri \
                    and pending.get("code_verifier"):
                flow.code_verifier = pending["code_verifier"]
                reused = pending["code_verifier"]
        except Exception as exc:  # noqa: BLE001 — a bad cache just means a new one
            print(f"(ignoring unreadable pending flow: {exc})", file=sys.stderr)

    state = secrets.token_urlsafe(16)
    url, _ = flow.authorization_url(access_type="offline", prompt="consent",
                                    state=state)

    # Save the verifier that is actually in the URL, so a later run reuses it.
    try:
        os.makedirs(os.path.dirname(PENDING_PATH), exist_ok=True)
        fd = os.open(PENDING_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump({"state": state, "redirect_uri": args.redirect_uri,
                       "code_verifier": flow.code_verifier}, fh)
    except Exception as exc:  # noqa: BLE001 — a missing cache is not fatal
        print(f"(could not save the pending flow: {exc})", file=sys.stderr)
    if reused:
        print("Reusing the PKCE verifier from the previous run "
              "(its code_challenge is in this URL).")

    if args.loopback:
        print("Open this URL in a browser ON YOUR OWN MACHINE and approve:\n")
        print(url)
        print(f"\nThe callback lands on {args.redirect_uri} — make sure that exact")
        print("URI is registered on the OAuth client. It never needs changing again,")
        print("even when the sandbox is recreated.\n")
    else:
        print("Open this URL in a browser and approve access:\n")
        print(url)
        print()

    if args.url_only:
        print("Then re-run without --url-only to finish. The PKCE verifier was")
        print(f"saved to {PENDING_PATH} (mode 600) so that second run can complete.")
        return 0

    if args.manual_code:
        print("After approving, the browser lands on a page that may fail to load.")
        print("That is expected: copy the whole address and take the value of the")
        print("?code= parameter from it (it is the long string before any '&').\n")
        code = input("Paste the value of the ?code= parameter: ").strip()
        flow.fetch_token(code=urllib.parse.unquote(code))
    else:
        host = urllib.parse.urlparse(args.redirect_uri).hostname or ""
        here = {h for h, _ in sandbox_hosts()}
        if host and host not in here and host not in ("127.0.0.1", "localhost"):
            sys.exit(f"The callback for {args.redirect_uri}\n"
                     f"cannot land in this pod (this pod is {sorted(here)}).\n"
                     "Re-run with --manual-code and paste the code from the browser, "
                     "or pass --loopback after registering that URI.")
        port = args.port
        host = "127.0.0.1" if args.loopback else "0.0.0.0"
        probe = socket.socket()
        if probe.connect_ex(("127.0.0.1", port)) == 0:
            probe.close()
            sys.exit(f"Port {port} is already in use; the callback cannot land. "
                     f"Pick another with --port and register a matching URI.")
        probe.close()

        httpd = http.server.ThreadingHTTPServer((host, port), _Catcher)
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        print(f"Waiting for the callback on {host}:{port} ...")
        if not args.loopback:
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

    try:
        os.remove(PENDING_PATH)
    except OSError:
        pass
    creds = flow.credentials
    if not creds.refresh_token:
        sys.exit("Google returned no refresh token. Re-run with prompt=consent "
                 "(the default) and revoke the app's access first if needed.")

    ch = None
    try:
        ch = channel_of(creds)
    except Exception as exc:
        print(f"(could not read the channel now: {exc})", file=sys.stderr)
    path = save_token(creds, ch)

    print(f"\nSaved to {path} (mode 600). Uploads can now run unattended.")
    if ch:
        print(f"Authorised for channel: {ch['snippet']['title']} ({ch['id']})")
        print("If that is not the channel you meant, revoke the app's access in "
              "the Google account and authorise again with the right account.")
    print("Verify with: python3 scripts/yt_auth.py --check")
    return 0


if __name__ == "__main__":
    sys.exit(main())
