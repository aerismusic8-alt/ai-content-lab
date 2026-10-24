"""Build a machine-readable channel for episodes, so an AI agent can pull
finished work and post it elsewhere without a human copying anything.

Reads every `episodes/*/` directory and writes, into `site/`:

    api/index.json                  catalogue of all episodes
    api/episodes/<slug>.json        everything about one episode, incl. ready
                                    to use posting text per platform
    feed.xml                        Atom feed with media enclosures
    sitemap.xml                     for crawlers
    llms.txt                        plain-text orientation for AI agents

Nothing here is hand-maintained: the API is generated from the same
`scenes.json`, `timing.json` and `audio_info.json` the video is built from, so
it cannot drift away from what was actually published.

Usage:
    python3 scripts/build_api.py [--site site] [--episodes episodes] [--base-url URL]
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import html
import json
import os
import re

REPO = "kongkeat938/ai-content-lab"
DEFAULT_BASE = "https://work-1-zcfjbytjdlcldhbg.prod-runtime.all-hands.dev"
GITHUB = f"https://github.com/{REPO}"
RAW = f"https://raw.githubusercontent.com/{REPO}/main"

# Files that are committed to git are served from raw.githubusercontent, which is
# permanent. Large media is not committed (see docs/GOAL.md), so it comes from the
# release for that episode.
COMMITTED_PREFIX = "site/"


def hms(seconds: float) -> str:
    seconds = int(round(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def load(path: str, default=None):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def scene_starts(scenes: list, timings: dict, total: float) -> list:
    """Same rule as make_video.py: a card starts on the line that opens it."""
    lines = timings.get("lines", [])
    starts = []
    for sc in scenes:
        t = None
        for idx in sc.get("lines", []):
            if 0 <= idx < len(lines) and lines[idx].get("start") is not None:
                t = lines[idx]["start"]
                break
        starts.append(0.0 if t is None else float(t))
    if not starts:
        return []
    starts[0] = 0.0
    for i in range(1, len(starts)):
        if starts[i] <= starts[i - 1]:
            starts[i] = starts[i - 1] + 0.5
    return [min(s, max(0.0, total - 1.0)) for s in starts]


def asset_url(rel_path: str, base_url: str, release_tag: str, ext: str) -> str:
    """Committed files -> raw GitHub (permanent). Media blobs -> release."""
    if ext in ("mp4", "mp3"):
        return f"{GITHUB}/releases/download/{release_tag}/{release_tag}.{ext}"
    return f"{RAW}/{rel_path}"


def build_posting(meta: dict, title: str, title_en: str, duration: str,
                  chapters: list, source: dict, credits: list,
                  base_url: str, slug: str, release_tag: str) -> dict:
    """Text an agent can post as-is. Every field is already formatted."""
    ch_lines = "\n".join(f"{hms(c['start'])}  {c['title']}" for c in chapters)
    tags = meta.get("tags", [])
    hashtags = " ".join("#" + t.replace(" ", "") for t in tags[:8])
    credit_lines = "\n".join(
        f"{c.get('title') or c.get('creator') or 'ไม่ทราบชื่อ'} — {c.get('licence')}"
        f"{(' — ' + c['source']) if c.get('source') else ''}"
        for c in credits
    )
    attribution = meta.get("attribution", "")

    description = f"""{title}
{title_en}

{meta.get('description', '')}

⏱ ลำดับเรื่อง
{ch_lines}

📖 ที่มา: {source.get('work', '')} โดย {source.get('author', '')} — สาธารณสมบัติ
🎧 เสียงบรรยาย: {meta.get('voice_note', 'edge-tts (ฟรี)')}
🖼 ภาพ: Openverse (CC BY / PDM)
📜 บทเต็ม: {asset_url(f'episodes/{slug}/narration_th.txt', base_url, release_tag, 'txt')}

{attribution}

{hashtags}
""".strip()

    return {
        "youtube": {
            "title": f"{title} | {title_en}",
            "description": description,
            "tags": tags,
            "category_id": meta.get("youtube_category_id", "24"),
            "language": "th",
            "made_for_kids": False,
        },
        "facebook": {
            "caption": f"{title}\n\n{meta.get('hook', meta.get('description', ''))}\n\n"
                       f"ฟังเต็ม {duration} นาที\n{hashtags}",
        },
        "tiktok": {
            "caption": f"{meta.get('hook', title)} {hashtags}",
        },
        "blog": {
            "title": title,
            "excerpt": meta.get("description", ""),
            "body_markdown": f"# {title}\n\n{meta.get('description', '')}\n\n"
                             f"## ลำดับเรื่อง\n\n"
                             + "\n".join(f"- `{hms(c['start'])}` {c['title']}" for c in chapters),
        },
        "hashtags": tags,
    }


def build_episode(ep_dir: str, base_url: str) -> dict:
    slug = os.path.basename(ep_dir.rstrip("/"))
    scenes_doc = load(os.path.join(ep_dir, "scenes.json"), {})
    timings = load(os.path.join(ep_dir, "timing.json"), {})
    info = load(os.path.join(ep_dir, "audio_info.json"), {})
    meta = load(os.path.join(ep_dir, "meta.json"), {})
    credits = load("assets/images/credits.json", [])
    if isinstance(credits, dict):
        credits = credits.get("images", credits.get("credits", []))

    scenes = scenes_doc.get("scenes", [])
    total = float(info.get("duration_sec") or timings.get("duration_sec") or 0)
    starts = scene_starts(scenes, timings, total)
    release_tag = meta.get("release_tag") or slug.split("_")[0]

    chapters = []
    for i, sc in enumerate(scenes):
        chapters.append({
            "start": round(starts[i], 2) if i < len(starts) else 0.0,
            "time": hms(starts[i]) if i < len(starts) else "0:00",
            "title": sc.get("title", ""),
            "subtitle": sc.get("subtitle", ""),
            "chapter": sc.get("chapter", ""),
            "card_image": sc.get("image", ""),
        })

    title = meta.get("title") or scenes_doc.get("title", slug)
    title_en = meta.get("title_en") or scenes_doc.get("title_en", "")
    script_path = os.path.join(ep_dir, "narration_th.txt")
    script = open(script_path, encoding="utf-8").read() if os.path.exists(script_path) else ""

    source = meta.get("source", {})
    duration = hms(total)

    def size(name: str) -> int | None:
        p = os.path.join(ep_dir, name)
        return os.path.getsize(p) if os.path.exists(p) else None

    media = {
        "video": {
            "url": asset_url("", base_url, release_tag, "mp4"),
            "local_url": f"{base_url}/media/{release_tag}.mp4",
            "bytes": size("video.mp4"),
            "mime": "video/mp4",
            "width": meta.get("width", 1920),
            "height": meta.get("height", 1080),
            "codec": "h264",
            "audio_codec": "aac",
        },
        "audio": {
            "url": asset_url("", base_url, release_tag, "mp3"),
            "local_url": f"{base_url}/media/{release_tag}.mp3",
            "bytes": size("audio_th.mp3"),
            "mime": "audio/mpeg",
            "lufs": info.get("lufs"),
            "true_peak_dbfs": info.get("true_peak_dbfs"),
            "voice": info.get("voice"),
            "rate": info.get("rate"),
            "pitch": info.get("pitch"),
        },
        "poster": {
            "url": f"{RAW}/site/media/{release_tag}_poster.jpg",
            "local_url": f"{base_url}/media/{release_tag}_poster.jpg",
            "mime": "image/jpeg",
        },
    }

    return {
        "id": release_tag,
        "slug": slug,
        "series": meta.get("series", "เรื่องเล่า"),
        "title": title,
        "title_en": title_en,
        "language": "th",
        "duration_sec": round(total, 2),
        "duration_hms": duration,
        "published": meta.get("published", dt.date.today().isoformat()),
        "source": source,
        "licence": meta.get("licence", "story: public domain; images: see credits"),
        "characters": info.get("chars"),
        "lines": info.get("lines"),
        "media": media,
        "chapters": chapters,
        "script": script,
        "script_url": f"{RAW}/episodes/{slug}/narration_th.txt",
        "credits": credits,
        "posting": build_posting(meta, title, title_en, duration, chapters,
                                 source, credits, base_url, slug, release_tag),
        "self": f"{base_url}/api/episodes/{slug}.json",
        "webpage": f"{base_url}/",
    }


def atom_feed(episodes: list, base_url: str, site_title: str) -> str:
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    entries = []
    for ep in episodes:
        vid = ep["media"]["video"]
        entries.append(f"""  <entry>
    <title>{html.escape(ep['title'])}</title>
    <id>{html.escape(ep['self'])}</id>
    <link href="{html.escape(ep['self'])}"/>
    <updated>{ep['published']}T00:00:00Z</updated>
    <summary>{html.escape(ep['posting']['youtube']['description'][:400])}</summary>
    <content type="html">{html.escape(ep['script'][:2000])}</content>
    <link rel="enclosure" href="{html.escape(vid['url'])}"
          type="video/mp4" title="{html.escape(ep['title'])}"/>
    <link rel="enclosure" href="{html.escape(ep['media']['audio']['url'])}"
          type="audio/mpeg" title="{html.escape(ep['title'])}"/>
  </entry>""")
    return f"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>{html.escape(site_title)}</title>
  <id>{base_url}/feed.xml</id>
  <link href="{base_url}/feed.xml" rel="self"/>
  <link href="{base_url}/api/index.json" rel="alternate" type="application/json"/>
  <updated>{now}</updated>
{chr(10).join(entries)}
</feed>
"""


def llms_txt(episodes: list, base_url: str, site_title: str) -> str:
    lines = [
        f"# {site_title}",
        "",
        f"> Thai narrated story episodes. Each episode is a video plus an audio",
        f"> track, poster art, a full script and ready-to-post text for YouTube,",
        f"> Facebook, TikTok and a blog. All stories are Thai public-domain",
        f"> literature. Everything here is free to reuse with attribution.",
        "",
        "## How to use this",
        "",
        f"- Catalogue: {base_url}/api/index.json",
        f"- One episode: {base_url}/api/episodes/<slug>.json",
        f"- Feed: {base_url}/feed.xml",
        "",
        "Fetch an episode JSON and read the `posting` object. It already contains",
        "the title, description, tags and hashtags in the right shape for each",
        "platform, so no rewriting is needed. `media.video.url` and",
        "`media.audio.url` are permanent download links. `chapters` gives the",
        "timestamps for a YouTube chapter list.",
        "",
        "Report what you posted with `POST /api/receipts` (see docs/API.md).",
        "",
        "## Episodes",
        "",
    ]
    for ep in episodes:
        lines.append(f"- [{ep['title']}]({ep['self']}): {ep['duration_hms']}, "
                     f"{ep['series']}, {ep['published']}")
    lines += [
        "",
        "## Licence",
        "",
        "Stories are public domain (Thai copyright lasts the author's life plus",
        "50 years). Photographs keep their own licences, listed per episode in",
        "`credits`. Attribution text is supplied in the episode JSON.",
        "",
    ]
    return "\n".join(lines)


def sitemap(episodes: list, base_url: str) -> str:
    urls = [f"{base_url}/", f"{base_url}/api/index.json", f"{base_url}/feed.xml"]
    urls += [ep["self"] for ep in episodes]
    body = "\n".join(f"  <url><loc>{html.escape(u)}</loc></url>" for u in urls)
    return ('<?xml version="1.0" encoding="utf-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f"{body}\n</urlset>\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="site")
    ap.add_argument("--episodes", default="episodes")
    ap.add_argument("--base-url", default=os.environ.get("BASE_URL", DEFAULT_BASE))
    args = ap.parse_args()

    site_title = "เรื่องเล่าไทย — Thai Story Episodes"
    ep_dirs = sorted(d for d in glob.glob(os.path.join(args.episodes, "*"))
                     if os.path.isdir(d) and os.path.exists(os.path.join(d, "scenes.json")))

    api_dir = os.path.join(args.site, "api")
    ep_api_dir = os.path.join(api_dir, "episodes")
    os.makedirs(ep_api_dir, exist_ok=True)

    episodes = []
    for d in ep_dirs:
        ep = build_episode(d, args.base_url)
        episodes.append(ep)
        out = os.path.join(ep_api_dir, f"{ep['slug']}.json")
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(ep, fh, ensure_ascii=False, indent=2)
        print(f"  {out}  ({os.path.getsize(out) // 1024} KB, {len(ep['chapters'])} chapters)")

    catalogue = {
        "generator": "content-lab build_api.py",
        "generated": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "site": args.base_url,
        "title": site_title,
        "count": len(episodes),
        "endpoints": {
            "catalogue": f"{args.base_url}/api/index.json",
            "episode": f"{args.base_url}/api/episodes/<slug>.json",
            "feed": f"{args.base_url}/feed.xml",
            "receipts": f"{args.base_url}/api/receipts",
            "llms": f"{args.base_url}/llms.txt",
        },
        "episodes": [
            {
                "id": ep["id"], "slug": ep["slug"], "title": ep["title"],
                "title_en": ep["title_en"], "series": ep["series"],
                "duration_hms": ep["duration_hms"], "published": ep["published"],
                "url": ep["self"],
                "video_url": ep["media"]["video"]["url"],
                "audio_url": ep["media"]["audio"]["url"],
                "poster_url": ep["media"]["poster"]["url"],
                "tags": ep["posting"]["hashtags"],
                "chapters": len(ep["chapters"]),
            }
            for ep in episodes
        ],
    }
    with open(os.path.join(api_dir, "index.json"), "w", encoding="utf-8") as fh:
        json.dump(catalogue, fh, ensure_ascii=False, indent=2)

    with open(os.path.join(args.site, "feed.xml"), "w", encoding="utf-8") as fh:
        fh.write(atom_feed(episodes, args.base_url, site_title))
    with open(os.path.join(args.site, "sitemap.xml"), "w", encoding="utf-8") as fh:
        fh.write(sitemap(episodes, args.base_url))
    with open(os.path.join(args.site, "llms.txt"), "w", encoding="utf-8") as fh:
        fh.write(llms_txt(episodes, args.base_url, site_title))

    print(f"\n  {len(episodes)} episode(s) -> {api_dir}")
    print(f"  {args.site}/feed.xml, {args.site}/sitemap.xml, {args.site}/llms.txt")


if __name__ == "__main__":
    main()
