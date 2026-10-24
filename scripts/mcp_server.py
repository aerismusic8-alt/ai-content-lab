#!/usr/bin/env python3
"""MCP server: exposes the episode channel as tools an AI can call directly.

An agent that supports MCP does not need to know any URLs or JSON shapes. It
connects to this server and gets four tools:

    list_episodes()                        what exists
    get_episode(episode)                   one episode, with posting text
    get_posting(episode, platform)         the text for one platform
    report_posted(episode, platform, url)  record what was published

Run it over stdio:

    python3 scripts/mcp_server.py

Register with an MCP client (Claude Desktop, OpenHands, any MCP host):

    {
      "mcpServers": {
        "thai-story-channel": {
          "command": "python3",
          "args": ["/abs/path/content-lab/scripts/mcp_server.py"]
        }
      }
    }

It talks to the same HTTP API the site serves, so there is exactly one source of
truth. Point it elsewhere with CHANNEL_BASE.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

try:
    from mcp.server.mcpserver import MCPServer
except ImportError:  # mcp < 2 kept FastMCP under a different name
    try:
        from mcp.server.fastmcp import FastMCP as MCPServer  # type: ignore
    except ImportError:
        print("The 'mcp' package is required: pip install mcp", file=sys.stderr)
        raise

DEFAULT_BASE = os.environ.get(
    "CHANNEL_BASE",
    "https://work-1-zcfjbytjdlcldhbg.prod-runtime.all-hands.dev")
PLATFORMS = ("youtube", "facebook", "tiktok", "blog")

mcp = MCPServer(
    "thai-story-channel",
    instructions=(
        "A channel of Thai narrated story episodes. Each episode has a video, an "
        "audio track, poster art, a full Thai script and posting text that is "
        "already formatted for YouTube, Facebook, TikTok and a blog. Stories are "
        "Thai public-domain literature, so they are free to republish with "
        "attribution; the attribution text is included in every episode. "
        "Use list_episodes first, then get_posting for the text, then "
        "report_posted with the URL you published so the channel records it."
    ),
)


def _fetch(path: str, base: str = None) -> dict:
    base = (base or DEFAULT_BASE).rstrip("/")
    req = urllib.request.Request(f"{base}{path}",
                                headers={"User-Agent": "content-lab-mcp/1.0"})
    with urllib.request.urlopen(req, timeout=60) as fh:
        return json.loads(fh.read().decode("utf-8"))


def _post(path: str, payload: dict, base: str = None) -> dict:
    base = (base or DEFAULT_BASE).rstrip("/")
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{base}{path}", data=data, method="POST",
        headers={"Content-Type": "application/json; charset=utf-8",
                 "User-Agent": "content-lab-mcp/1.0"})
    with urllib.request.urlopen(req, timeout=60) as fh:
        return json.loads(fh.read().decode("utf-8"))


def _resolve_slug(key: str, base: str = None) -> str:
    cat = _fetch("/api/index.json", base)
    for ep in cat.get("episodes", []):
        if key in (ep.get("id"), ep.get("slug")):
            return ep["slug"]
    raise ValueError(f"no episode matches {key!r}; try list_episodes()")


@mcp.tool()
def list_episodes() -> dict:
    """List every episode on the channel.

    Returns each episode's id, title, length, series and the URL of its full
    JSON record. Start here.
    """
    cat = _fetch("/api/index.json")
    return {
        "count": cat.get("count", 0),
        "title": cat.get("title"),
        "episodes": [
            {
                "id": ep["id"],
                "slug": ep["slug"],
                "title": ep["title"],
                "title_en": ep.get("title_en"),
                "series": ep.get("series"),
                "duration": ep["duration_hms"],
                "published": ep.get("published"),
                "video_url": ep.get("video_url"),
                "audio_url": ep.get("audio_url"),
                "poster_url": ep.get("poster_url"),
                "chapters": ep.get("chapters"),
                "record": ep.get("url"),
            }
            for ep in cat.get("episodes", [])
        ],
    }


@mcp.tool()
def get_episode(episode: str) -> dict:
    """Get one episode in full.

    `episode` is an id or slug, e.g. "ep01" or "ep01_gift_of_the_magi".

    Returns the title, length, source work and its licence, media download
    links, a chapter list with timestamps, the full Thai script, image credits
    for attribution, and a `posting` object with text already shaped for each
    platform.
    """
    ep = _fetch(f"/api/episodes/{_resolve_slug(episode)}.json")
    return {
        "id": ep["id"],
        "slug": ep["slug"],
        "title": ep["title"],
        "title_en": ep.get("title_en"),
        "series": ep.get("series"),
        "duration": ep["duration_hms"],
        "language": ep.get("language"),
        "source": ep.get("source"),
        "licence": ep.get("licence"),
        "media": ep.get("media"),
        "chapters": ep.get("chapters"),
        "script": ep.get("script"),
        "credits": ep.get("credits"),
        "posting": ep.get("posting"),
        "webpage": ep.get("webpage"),
    }


@mcp.tool()
def get_posting(episode: str, platform: str = "youtube") -> dict:
    """Get ready-to-publish text for one episode and one platform.

    `platform` is one of: youtube, facebook, tiktok, blog.

    The text needs no rewriting. For YouTube it includes a description with the
    chapter timestamps, the source and the attribution already in place. Also
    returns the media URLs to attach.
    """
    platform = (platform or "youtube").lower()
    if platform not in PLATFORMS:
        return {"error": f"platform must be one of {', '.join(PLATFORMS)}"}
    ep = _fetch(f"/api/episodes/{_resolve_slug(episode)}.json")
    return {
        "episode": ep["id"],
        "title": ep["title"],
        "platform": platform,
        "payload": ep["posting"].get(platform, {}),
        "hashtags": ep["posting"].get("hashtags", []),
        "attach": {
            "video": ep["media"]["video"]["url"],
            "audio": ep["media"]["audio"]["url"],
            "poster": ep["media"]["poster"]["url"],
        },
        "attribution_required": True,
        "note": ("Stories are public domain. Photograph licences differ per "
                 "episode — keep the attribution block in the description."),
    }


@mcp.tool()
def report_posted(episode: str, platform: str, url: str,
                  posted_by: str = "", note: str = "") -> dict:
    """Record that an episode was published, and where.

    Call this after posting. `url` is the public link to the post. The channel
    keeps a log so nobody publishes the same episode twice by accident.
    """
    ep = _fetch(f"/api/episodes/{_resolve_slug(episode)}.json")
    payload = {
        "episode": ep["id"], "slug": ep["slug"], "platform": platform.lower(),
        "url": url, "title": ep["title"], "duration": ep["duration_hms"],
    }
    if posted_by:
        payload["posted_by"] = posted_by
    if note:
        payload["note"] = note
    res = _post("/api/receipts", payload)
    rec = res.get("recorded", {})
    return {"ok": res.get("ok", False), "recorded_at": rec.get("received_at"),
            "episode": rec.get("episode"), "platform": rec.get("platform"),
            "url": rec.get("url")}


@mcp.tool()
def list_posted() -> dict:
    """List what has already been published from this channel.

    Use this before posting, so the same episode is not published twice.
    """
    res = _fetch("/api/receipts")
    return {"count": res.get("count", 0), "receipts": res.get("receipts", [])}


@mcp.tool()
def youtube_status() -> dict:
    """Check whether this machine is allowed to upload to YouTube.

    Returns whether an authorisation token exists and, if so, which channel it
    belongs to. Call this before publish_to_youtube. When `ready` is false, tell
    the user to run `python3 scripts/yt_auth.py` once — that needs a human with
    a browser, and cannot be done by an agent.
    """
    import subprocess
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "yt_auth.py")
    token = os.environ.get("YT_TOKEN_PATH",
                           os.path.expanduser("~/.config/content-lab/yt_token.json"))
    if not os.path.exists(token):
        return {"ready": False, "token_path": token,
                "reason": "no authorisation token yet",
                "fix": "python3 scripts/yt_auth.py   (needs a browser, once)"}
    proc = subprocess.run([sys.executable, script, "--check"],
                          capture_output=True, text=True, timeout=120)
    return {"ready": proc.returncode == 0, "token_path": token,
            "output": (proc.stdout + proc.stderr).strip()}


@mcp.tool()
def publish_to_youtube(episode: str, privacy: str = "private",
                       dry_run: bool = True) -> dict:
    """Upload an episode to YouTube and record it on the channel.

    `privacy` is private, unlisted or public. `dry_run` defaults to True: it
    prints the exact title, description, tags and thumbnail that would be used
    and uploads nothing. Only pass dry_run=False when the user has clearly asked
    for the episode to be published.

    The title, description, chapters, source and attribution all come from the
    channel, so nothing is retyped. Requires `youtube_status().ready` to be true.
    """
    import subprocess
    if privacy not in ("private", "unlisted", "public"):
        return {"error": "privacy must be private, unlisted or public"}
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "publish_youtube.py")
    cmd = [sys.executable, script, episode, "--base", DEFAULT_BASE,
           "--privacy", privacy]
    if dry_run:
        cmd.append("--dry-run")
    else:
        cmd.append("--report")
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3600,
                          env={**os.environ, "CHANNEL_BASE": DEFAULT_BASE})
    out = (proc.stdout + proc.stderr).strip()
    result = {"ok": proc.returncode == 0, "dry_run": dry_run,
              "privacy": privacy, "output": out[-4000:]}
    for line in out.splitlines():
        if line.startswith("published: "):
            result["url"] = line.split("published: ", 1)[1].strip()
    return result


if __name__ == "__main__":
    mcp.run()
