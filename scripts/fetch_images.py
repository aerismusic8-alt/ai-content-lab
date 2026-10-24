"""Fetch free-licensed background images from Openverse (no API key needed).

Every image is downloaded together with its licence and creator so the video
can carry proper attribution. Only licences that allow commercial use AND
modification are requested; the licence gate below re-checks each result
because the API filter is not always honoured.

Usage:
    python fetch_images.py <queries.json> <out_dir> [--per-query 2]
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

UA = "ai-content-lab/1.0 (free-content pipeline; contact: kongkeat938)"
API = "https://api.openverse.org/v1/images/"

# Licences safe for a monetisable video: attribution-only, no share-alike
# obligation that would force us to relicense the whole video.
OK_LICENSES = {"cc0", "pdm", "by", "by-sa"}
BAD_TOKENS = ("nc", "nd", "gfdl", "sampling")


def licence_ok(lic: str, version: str = "") -> bool:
    lic = (lic or "").lower()
    if not lic or any(t in lic for t in BAD_TOKENS):
        return False
    return lic in OK_LICENSES


def get(url: str, timeout: int = 40) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def search(query: str, want: int, pages: int = 3) -> list:
    """Return up to `want` acceptable results for one query."""
    got, seen = [], set()
    for page in range(1, pages + 1):
        params = urllib.parse.urlencode({
            "q": query,
            "license_type": "commercial,modification",
            "page_size": 20,
            "page": page,
            "mature": "false",
        })
        try:
            data = json.loads(get(API + "?" + params))
        except Exception as e:  # noqa: BLE001 - keep going on a flaky page
            print(f"  query page failed: {e}", file=sys.stderr)
            time.sleep(2)
            continue
        for r in data.get("results", []):
            if len(got) >= want:
                return got
            if not licence_ok(r.get("license"), r.get("license_version")):
                continue
            url = r.get("url") or ""
            if not url or url in seen:
                continue
            if not re.search(r"\.(jpe?g|png)$", url.split("?")[0], re.I):
                continue
            w = r.get("width") or 0
            h = r.get("height") or 0
            if w and h and (w < 1000 or h < 600):
                continue
            seen.add(url)
            got.append({
                "title": (r.get("title") or "").strip()[:120],
                "url": url,
                "license": f"{r.get('license','').upper()} {r.get('license_version','')}".strip(),
                "creator": (r.get("creator") or "unknown").strip(),
                "source": r.get("foreign_landing_url") or r.get("detail_url") or "",
            })
        time.sleep(0.4)
    return got


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("queries_json", help="JSON list of query strings")
    ap.add_argument("out_dir")
    ap.add_argument("--per-query", type=int, default=2)
    a = ap.parse_args()

    queries = json.load(open(a.queries_json, encoding="utf-8"))
    os.makedirs(a.out_dir, exist_ok=True)
    credits_path = os.path.join(a.out_dir, "credits.json")
    credits = json.load(open(credits_path, encoding="utf-8")) if os.path.exists(credits_path) else []

    for qi, q in enumerate(queries):
        found = search(q, a.per_query)
        print(f"[{qi + 1}/{len(queries)}] {q!r} -> {len(found)}")
        for r in found:
            name = f"img{qi:02d}_{len([c for c in credits if c['query'] == q]):02d}.jpg"
            path = os.path.join(a.out_dir, name)
            try:
                blob = get(r["url"])
            except Exception as e:  # noqa: BLE001
                print(f"    download failed: {e}", file=sys.stderr)
                continue
            if len(blob) < 20000:
                print("    too small, skipped", file=sys.stderr)
                continue
            with open(path, "wb") as f:
                f.write(blob)
            credits.append({"file": name, "query": q, **r})
            print(f"    {name}  {len(blob)//1024}KB  {r['license']}  {r['creator'][:30]}")
            # save incrementally so a killed run keeps its progress
            with open(credits_path, "w", encoding="utf-8") as f:
                json.dump(credits, f, ensure_ascii=False, indent=2)
        time.sleep(1.0)

    print(f"\ntotal images: {len(credits)} -> {credits_path}")


if __name__ == "__main__":
    main()
