"""Static file server with HTTP Range support, plus a small write channel.

`python3 -m http.server` ignores Range headers, so the <video> element cannot
seek and some browsers refuse to start playback at all. This serves the same
files with proper 206 Partial Content responses.

It also exposes one write endpoint so a posting agent can report back:

    POST /api/receipts   {"episode": "ep01", "platform": "youtube", "url": "..."}
    GET  /api/receipts   the receipts recorded so far

The static side is read-only; only /api/receipts accepts a write, the body is
size-capped, and the store is an append-only JSONL file.

Usage:
    python serve.py [port] [directory]
"""
import json
import os
import re
import socket
import sys
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)")
MAX_BODY = 64 * 1024
# Kept outside site/ on purpose: site/ is served to the public, and receipts
# carry the caller's address. Never commit it either (see .gitignore).
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECEIPTS_PATH = os.path.join(REPO_ROOT, "receipts", "receipts.jsonl")


def read_receipts(mask: bool = True) -> list:
    if not os.path.exists(RECEIPTS_PATH):
        return []
    out = []
    with open(RECEIPTS_PATH, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if mask and rec.get("remote"):
                parts = str(rec["remote"]).split(".")
                if len(parts) == 4:
                    rec["remote"] = f"{parts[0]}.{parts[1]}.x.x"
                else:
                    rec["remote"] = "masked"
            out.append(rec)
    return out


class RangeHandler(SimpleHTTPRequestHandler):
    server_version = "content-lab/1.0"

    # ---- write channel -------------------------------------------------

    def do_POST(self):
        if self.path.rstrip("/") != "/api/receipts":
            self.send_error(404, "Only POST /api/receipts is accepted")
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            self.send_error(400, "Bad Content-Length")
            return
        if length <= 0 or length > MAX_BODY:
            self.send_error(413, f"Body must be 1..{MAX_BODY} bytes")
            return
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            self.send_error(400, f"Invalid JSON: {exc}")
            return
        if not isinstance(payload, dict):
            self.send_error(400, "Body must be a JSON object")
            return

        record = {
            "received_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "remote": self.client_address[0],
            **payload,
        }
        os.makedirs(os.path.dirname(RECEIPTS_PATH), exist_ok=True)
        with open(RECEIPTS_PATH, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

        body = json.dumps({"ok": True, "recorded": {**record, "remote": "stored"}},
                          ensure_ascii=False).encode("utf-8")
        self.send_response(201)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.split("?")[0].rstrip("/") == "/api/receipts":
            records = read_receipts(mask=True)
            body = json.dumps({"count": len(records), "receipts": records},
                              ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Allow", "GET, HEAD, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def list_directory(self, path):
        # Directory listing is disabled: site/ holds only known files, and a
        # listing would expose the receipts file to casual browsing.
        self.send_error(404, "No directory listing")
        return None

    # ---- read side, with Range ----------------------------------------

    def send_head(self):
        rng = self.headers.get("Range")
        if not rng:
            return super().send_head()

        path = self.translate_path(self.path)
        if os.path.isdir(path):
            return super().send_head()
        try:
            f = open(path, "rb")
        except OSError:
            self.send_error(404, "File not found")
            return None

        size = os.fstat(f.fileno()).st_size
        m = RANGE_RE.match(rng)
        if not m:
            f.close()
            return super().send_head()

        start_s, end_s = m.group(1), m.group(2)
        if start_s == "":                     # suffix range: last N bytes
            length = int(end_s)
            start = max(0, size - length)
            end = size - 1
        else:
            start = int(start_s)
            end = int(end_s) if end_s else size - 1
        end = min(end, size - 1)

        if start > end or start >= size:
            f.close()
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{size}")
            self.end_headers()
            return None

        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Cache-Control", "public, max-age=300")
        self.end_headers()
        f.seek(start)
        return _Slice(f, end - start + 1)


class _Slice:
    """File wrapper that stops after `remaining` bytes (copyfile reads it)."""

    def __init__(self, f, remaining):
        self.f = f
        self.remaining = remaining

    def read(self, n=-1):
        if self.remaining <= 0:
            return b""
        if n < 0 or n > self.remaining:
            n = self.remaining
        data = self.f.read(n)
        self.remaining -= len(data)
        return data

    def close(self):
        self.f.close()


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 12000
    directory = sys.argv[2] if len(sys.argv) > 2 else "."
    os.chdir(directory)
    ThreadingHTTPServer.allow_reuse_address = True
    httpd = ThreadingHTTPServer(("0.0.0.0", port), RangeHandler)
    print(f"serving {directory} on 0.0.0.0:{port} (Range enabled)", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
