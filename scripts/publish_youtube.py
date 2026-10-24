#!/usr/bin/env python3
"""Publish an episode to YouTube, using the text from the channel.

Everything posted comes from the episode's `posting.youtube` object, so what is
published is exactly what the channel advertises. Nothing is retyped.

    python3 scripts/publish_youtube.py ep01 --dry-run      # show what it would do
    python3 scripts/publish_youtube.py ep01                # upload, private
    python3 scripts/publish_youtube.py ep01 --privacy unlisted
    python3 scripts/publish_youtube.py ep01 --report       # tell the channel

Needs a token from `scripts/yt_auth.py`. The video is taken from the channel's
permanent URL unless --file points at a local copy.

Quota: the YouTube Data API allows 100 videos.insert calls and 100
thumbnails.set calls per day, separate from the 10,000 units other endpoints
share, so publishing an episode is never the thing that runs out.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request

DEFAULT_BASE = os.environ.get(
    "CHANNEL_BASE",
    "https://work-1-zcfjbytjdlcldhbg.prod-runtime.all-hands.dev")
SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube.readonly"]
CATEGORY_IDS = {"film": "1", "music": "10", "entertainment": "24",
                "education": "27", "people": "22"}
REGISTRY = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "channels.json")


def load_registry() -> dict:
    if not os.path.exists(REGISTRY):
        return {"channels": []}
    with open(REGISTRY, encoding="utf-8") as fh:
        return json.load(fh)


def find_channel(slug: str) -> dict:
    for ch in load_registry().get("channels", []):
        if ch.get("slug") == slug:
            return ch
    return {}


def token_path_for(slug: str) -> str:
    """One token file per channel, so two channels never share credentials.

    Overriding YT_TOKEN_PATH forces a single token, which is how you would
    deliberately point every channel at one account.
    """
    if os.environ.get("YT_TOKEN_PATH"):
        return os.environ["YT_TOKEN_PATH"]
    ch = find_channel(slug)
    if ch.get("token_path"):
        return os.path.expanduser(ch["token_path"])
    return os.path.expanduser(f"~/.config/content-lab/yt_token_{slug}.json")


def assert_channel(yt, expected: str | None, slug: str) -> dict:
    """Refuse to upload when the token belongs to the wrong channel.

    A browser can silently reuse whichever Google account is already signed in,
    so authorising can hand back a token for a channel you did not mean. Without
    this check the video would land on the wrong channel with no warning.
    """
    res = yt.channels().list(part="snippet,contentDetails", mine=True).execute()
    items = res.get("items", [])
    if not items:
        sys.exit(f"The token for '{slug}' has no YouTube channel. "
                 f"Re-run scripts/yt_auth.py with the right account.")
    ch = items[0]
    if expected and ch["id"] != expected:
        sys.exit(
            f"WRONG CHANNEL for '{slug}':\n"
            f"  expected {expected}\n"
            f"  token is {ch['id']} ({ch['snippet']['title']})\n"
            f"The browser probably reused a different signed-in Google account.\n"
            f"Revoke this app in that account and authorise again, or fix the\n"
            f"channel_id for '{slug}' in channels.json.")
    return ch


def fetch(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "content-lab-publish/1.0"})
    with urllib.request.urlopen(req, timeout=60) as fh:
        return json.loads(fh.read().decode("utf-8"))


def post(url: str, payload: dict) -> dict:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Content-Type": "application/json; charset=utf-8",
                 "User-Agent": "content-lab-publish/1.0"})
    with urllib.request.urlopen(req, timeout=60) as fh:
        return json.loads(fh.read().decode("utf-8"))


def resolve(base: str, key: str) -> dict:
    cat = fetch(f"{base}/api/index.json")
    for ep in cat.get("episodes", []):
        if key in (ep.get("id"), ep.get("slug")):
            return fetch(ep["url"])
    sys.exit(f"no episode matches {key!r}; try scripts/post.py --list")


def build_body(ep: dict, privacy: str) -> dict:
    p = ep["posting"]["youtube"]
    return {
        "snippet": {
            "title": p["title"][:100],
            "description": p["description"][:5000],
            "tags": p.get("tags", [])[:500],
            "categoryId": CATEGORY_IDS.get(p.get("category_id"), p.get("category_id", "24")),
            "defaultLanguage": p.get("language", "th"),
            "defaultAudioLanguage": p.get("language", "th"),
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": bool(p.get("made_for_kids", False)),
            "license": "youtube",
            "embeddable": True,
        },
    }


def download(url: str, dest: str) -> str:
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        print(f"  using existing {dest}")
        return dest
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    print(f"  downloading {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "content-lab-publish/1.0"})
    with urllib.request.urlopen(req, timeout=600) as src, open(dest, "wb") as out:
        while True:
            chunk = src.read(1 << 18)
            if not chunk:
                break
            out.write(chunk)
    return dest


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("episode")
    ap.add_argument("--base", default=DEFAULT_BASE)
    ap.add_argument("--file", help="local video file instead of the channel URL")
    ap.add_argument("--poster", help="local thumbnail instead of the channel URL")
    ap.add_argument("--privacy", default="private",
                    choices=["private", "unlisted", "public"])
    ap.add_argument("--dry-run", action="store_true",
                    help="print the request that would be sent, then stop")
    ap.add_argument("--report", action="store_true",
                    help="after uploading, record the URL with the channel")
    ap.add_argument("--cache", default=os.path.expanduser("~/.cache/content-lab"),
                    help="where to keep the downloaded video")
    ap.add_argument("--channel", help="channel slug from channels.json "
                                      "(picks the token and the expected channel)")
    args = ap.parse_args()

    ep = resolve(args.base, args.episode)
    slug = args.channel or ep.get("channel") or "default"
    ch_cfg = find_channel(slug)
    expected = ch_cfg.get("channel_id")
    if args.channel and not ch_cfg:
        sys.exit(f"'{args.channel}' is not in channels.json. Add it first.")
    os.environ["YT_TOKEN_PATH"] = token_path_for(slug)
    body = build_body(ep, args.privacy)

    print(f"episode : {ep['id']} — {ep['title']} ({ep['duration_hms']})")
    print(f"channel : {slug}" + (f"  ({ch_cfg.get('name')})" if ch_cfg else "")
          + (f"  expect {expected}" if expected else ""))
    print(f"token   : {os.environ['YT_TOKEN_PATH']}")
    print(f"privacy : {args.privacy}")
    print(f"title   : {body['snippet']['title']}")
    print(f"tags    : {', '.join(body['snippet']['tags'][:8])}")
    print(f"category: {body['snippet']['categoryId']}  "
          f"language: {body['snippet']['defaultLanguage']}  "
          f"kids: {body['status']['selfDeclaredMadeForKids']}")
    print(f"video   : {args.file or ep['media']['video']['url']}")
    print(f"poster  : {args.poster or ep['media']['poster']['url']}")

    if args.dry_run:
        print("\n--- description that would be posted ---\n")
        print(body["snippet"]["description"])
        print("\n--- snippet/status ---")
        print(json.dumps(body, ensure_ascii=False, indent=2))
        print("\ndry run: nothing uploaded")
        return 0

    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from googleapiclient.errors import HttpError
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from yt_auth import load_credentials

    creds = load_credentials()
    yt = build("youtube", "v3", credentials=creds, cache_discovery=False)

    # Refuse before uploading a single byte if the token is for another channel.
    ch = assert_channel(yt, expected, slug)
    print(f"  authorised as: {ch['snippet']['title']} ({ch['id']})")

    video_path = args.file or download(
        ep["media"]["video"]["url"], os.path.join(args.cache, f"{ep['id']}.mp4"))

    print("\nuploading video ...")
    try:
        request = yt.videos().insert(
            part="snippet,status", body=body,
            media_body=MediaFileUpload(video_path, chunksize=8 * 1024 * 1024,
                                       resumable=True))
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"  {int(status.progress() * 100)}%", flush=True)
    except HttpError as exc:
        print(f"upload failed: {exc}", file=sys.stderr)
        return 1

    vid = response["id"]
    url = f"https://youtu.be/{vid}"
    print(f"  uploaded: {url}  status={response['status']['privacyStatus']}")

    thumb_path = args.poster
    if thumb_path or ep["media"].get("poster"):
        try:
            if not thumb_path:
                thumb_path = download(ep["media"]["poster"]["url"],
                                      os.path.join(args.cache, f"{ep['id']}_poster.jpg"))
            yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(thumb_path)).execute()
            print("  thumbnail set")
        except HttpError as exc:
            print(f"  thumbnail rejected ({exc.status_code}); the video is still up",
                  file=sys.stderr)

    print(f"\npublished: {url}")
    print("It is private until you change it in YouTube Studio.")

    if args.report:
        res = post(f"{args.base}/api/receipts", {
            "episode": ep["id"], "slug": ep["slug"], "platform": "youtube",
            "url": url, "title": ep["title"], "duration": ep["duration_hms"],
            "privacy": args.privacy, "video_id": vid,
        })
        print(f"reported to the channel at {res['recorded']['received_at']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
