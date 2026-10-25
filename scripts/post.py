#!/usr/bin/env python3
"""Pull an episode from the channel and print the posting payload.

This is the client side of the channel: an AI agent runs this, gets text that is
already shaped for the platform, and posts it. No human copying.

    python3 scripts/post.py --list
    python3 scripts/post.py ep01 --platform youtube
    python3 scripts/post.py ep01 --platform facebook --json
    python3 scripts/post.py ep01 --download ./out      # fetch video + audio

Then report back, so the channel records what was published:

    python3 scripts/post.py ep01 --platform youtube --report https://youtu.be/XXXX
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

# Follow the environment rather than a frozen hostname; see build_api.py.
DEFAULT_BASE = (os.environ.get("CHANNEL_BASE", "").rstrip("/")
                or os.environ.get("RUNTIME_URL", "").rstrip("/")
                or "https://work-1-zcfjbytjdlcldhbg.prod-runtime.all-hands.dev")


def fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "content-lab-post/1.0"})
    with urllib.request.urlopen(req, timeout=60) as fh:
        return json.loads(fh.read().decode("utf-8"))


def post_json(url: str, payload: dict) -> dict:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Content-Type": "application/json; charset=utf-8",
                 "User-Agent": "content-lab-post/1.0"})
    with urllib.request.urlopen(req, timeout=60) as fh:
        return json.loads(fh.read().decode("utf-8"))


def download(url: str, dest: str) -> int:
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "content-lab-post/1.0"})
    total = 0
    with urllib.request.urlopen(req, timeout=300) as src, open(dest, "wb") as out:
        while True:
            chunk = src.read(1 << 16)
            if not chunk:
                break
            out.write(chunk)
            total += len(chunk)
    return total


def resolve(base: str, key: str) -> str:
    """Accept either the short id (ep01) or the full slug and return the slug.

    The API files are named after the slug, but people and agents naturally use
    the short id from the catalogue, so both have to work.
    """
    cat = fetch_json(f"{base}/api/index.json")
    for ep in cat.get("episodes", []):
        if key in (ep.get("id"), ep.get("slug")):
            return ep["slug"]
    raise KeyError(key)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("episode", nargs="?", help="episode id or slug, e.g. ep01")
    ap.add_argument("--base", default=DEFAULT_BASE, help="channel base URL")
    ap.add_argument("--list", action="store_true", help="list episodes and exit")
    ap.add_argument("--platform", default="youtube",
                    choices=["youtube", "facebook", "tiktok", "blog"])
    ap.add_argument("--json", action="store_true", help="print raw JSON")
    ap.add_argument("--download", metavar="DIR", help="download video and audio here")
    ap.add_argument("--report", metavar="URL", help="report a posted URL back")
    args = ap.parse_args()

    try:
        if args.list or not args.episode:
            cat = fetch_json(f"{args.base}/api/index.json")
            print(f"{cat['count']} episode(s) — {cat['title']}\n")
            for ep in cat["episodes"]:
                print(f"  {ep['id']:6s} {ep['duration_hms']:>7s}  {ep['title']}")
                print(f"         {ep['url']}")
            return 0

        ep = fetch_json(f"{args.base}/api/episodes/{resolve(args.base, args.episode)}.json")

        if args.download:
            vid = download(ep["media"]["video"]["url"],
                           os.path.join(args.download, f"{ep['id']}.mp4"))
            aud = download(ep["media"]["audio"]["url"],
                           os.path.join(args.download, f"{ep['id']}.mp3"))
            print(f"video {vid / 1e6:.1f} MB, audio {aud / 1e6:.1f} MB -> {args.download}")
            return 0

        if args.report:
            if args.report.lower() in ("none", "skipped", "dry-run"):
                print("nothing reported (dry run)")
                return 0
            res = post_json(f"{args.base}/api/receipts", {
                "episode": ep["id"], "slug": ep["slug"],
                "platform": args.platform, "url": args.report,
                "title": ep["title"], "duration": ep["duration_hms"],
            })
            print(f"recorded: {res['recorded']['received_at']} "
                  f"{res['recorded']['platform']} {res['recorded']['url']}")
            return 0

        payload = ep["posting"][args.platform]
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0

        print(f"=== {args.platform} — {ep['title']} ({ep['duration_hms']}) ===\n")
        for key in ("title", "caption", "description", "tags", "hashtags",
                    "category_id", "language", "made_for_kids", "excerpt",
                    "body_markdown"):
            if key in payload:
                val = payload[key]
                if isinstance(val, list):
                    val = ", ".join(val)
                print(f"--- {key} ---\n{val}\n")
        print(f"--- video ---\n{ep['media']['video']['url']}")
        print(f"--- audio ---\n{ep['media']['audio']['url']}")
        print(f"--- poster ---\n{ep['media']['poster']['url']}")
        return 0

    except urllib.error.HTTPError as exc:
        print(f"HTTP {exc.code} from the channel: {exc.reason}", file=sys.stderr)
        print("If every path 502s, the sandbox was recycled — restart "
              "scripts/watch_site.sh", file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(f"cannot reach the channel at {args.base}: {exc.reason}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
