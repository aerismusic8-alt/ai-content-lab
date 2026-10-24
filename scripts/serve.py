"""Static file server with HTTP Range support.

`python3 -m http.server` ignores Range headers, so the <video> element cannot
seek and some browsers refuse to start playback at all. This serves the same
files with proper 206 Partial Content responses.

Usage:
    python serve.py [port] [directory]
"""
import os
import re
import socket
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)")


class RangeHandler(SimpleHTTPRequestHandler):
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
