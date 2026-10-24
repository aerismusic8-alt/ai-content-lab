#!/usr/bin/env python3
"""The shared work queue two accounts use so they do not collide.

Two OpenHands accounts cannot see each other's conversations — a conversation
belongs to the account that started it and is not shareable. So the coordination
bus has to be the repository, which both accounts can read and write.

This script is that bus. It keeps one file, `work/CLAIMS.json`, that says who is
doing which episode right now.

    python3 scripts/claims.py list
    python3 scripts/claims.py claim ep02 --as account-1
    python3 scripts/claims.py done ep02 --as account-1 --url https://youtu.be/XXXX
    python3 scripts/claims.py release ep02 --as account-1

The identity is taken from --as, else $OH_ACCOUNT, else the local
`.work-account` file, else git's user.name.

Whoever commits first wins: the file is the lock. If two accounts claim the same
episode, git will conflict on the commit and the second one has to pick another
episode. That is the whole concurrency design, and it is enough for two people.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLAIMS = os.path.join(ROOT, "work", "CLAIMS.json")
QUEUE = os.path.join(ROOT, "work", "QUEUE.md")

STATUSES = ("claimed", "review", "done")


def today() -> str:
    return dt.date.today().isoformat()


def load() -> dict:
    if not os.path.exists(CLAIMS):
        return {"claims": []}
    with open(CLAIMS, encoding="utf-8") as fh:
        return json.load(fh)


def save(doc: dict) -> None:
    os.makedirs(os.path.dirname(CLAIMS), exist_ok=True)
    with open(CLAIMS, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def identity(explicit: str | None) -> str:
    if explicit:
        return explicit
    if os.environ.get("OH_ACCOUNT"):
        return os.environ["OH_ACCOUNT"]
    local = os.path.join(ROOT, ".work-account")
    if os.path.exists(local):
        return open(local, encoding="utf-8").read().strip()
    try:
        name = subprocess.run(["git", "config", "user.name"], cwd=ROOT,
                              capture_output=True, text=True).stdout.strip()
        return name or "unknown"
    except OSError:
        return "unknown"


def find(doc: dict, episode: str) -> dict | None:
    for c in doc["claims"]:
        if c["episode"] == episode:
            return c
    return None


def ep_dirs() -> list[str]:
    d = os.path.join(ROOT, "episodes")
    if not os.path.isdir(d):
        return []
    return sorted(os.listdir(d))


def cmd_list(args) -> int:
    doc = load()
    claims = {c["episode"]: c for c in doc["claims"]}

    print("episodes on disk:")
    for ep in ep_dirs():
        c = claims.get(ep.split("_")[0]) or claims.get(ep)
        state = f"{c['status']} by {c['account']}" if c else "—"
        print(f"  {ep:34s} {state}")

    if claims:
        print("\nclaims:")
        for c in doc["claims"]:
            extra = f"  {c.get('url', '')}" if c.get("url") else ""
            print(f"  {c['episode']:8s} {c['status']:8s} {c['account']:12s} "
                  f"{c['updated']}{extra}")

    if os.path.exists(QUEUE):
        print(f"\nbacklog: {QUEUE}")
        for line in open(QUEUE, encoding="utf-8"):
            if line.startswith("| ") and "ep0" in line.lower():
                print("  " + line.strip())
    return 0


def cmd_claim(args) -> int:
    doc = load()
    who = identity(args.account)
    existing = find(doc, args.episode)
    if existing:
        if existing["account"] != who and not args.force:
            print(f"{args.episode} is already claimed by {existing['account']} "
                  f"({existing['status']}). Pick another episode, or pass --force "
                  f"only if you know they are done with it.", file=sys.stderr)
            return 1
        existing.update(status="claimed", account=who, updated=today())
    else:
        doc["claims"].append({"episode": args.episode, "account": who,
                              "status": "claimed", "updated": today()})
    save(doc)
    print(f"{who} claimed {args.episode}")
    return finish(args, f"queue: {who} claims {args.episode}")


def cmd_done(args) -> int:
    doc = load()
    who = identity(args.account)
    c = find(doc, args.episode)
    if not c:
        print(f"{args.episode} was never claimed; claiming it now for {who}",
              file=sys.stderr)
        c = {"episode": args.episode, "account": who}
        doc["claims"].append(c)
    if c["account"] != who and not args.force:
        print(f"{args.episode} is {c['account']}'s, not yours. Use --force to "
              f"override deliberately.", file=sys.stderr)
        return 1
    c.update(status="done", account=who, updated=today())
    if args.url:
        c["url"] = args.url
    if args.pr:
        c["pr"] = args.pr
    save(doc)
    print(f"{args.episode} marked done" + (f" — {args.url}" if args.url else ""))
    return finish(args, f"queue: {who} finished {args.episode}"
                         + (f" ({args.url})" if args.url else ""))


def cmd_release(args) -> int:
    doc = load()
    who = identity(args.account)
    c = find(doc, args.episode)
    if not c:
        print(f"{args.episode} is not claimed", file=sys.stderr)
        return 1
    if c["account"] != who and not args.force:
        print(f"{args.episode} is {c['account']}'s. --force to release it anyway.",
              file=sys.stderr)
        return 1
    doc["claims"] = [x for x in doc["claims"] if x["episode"] != args.episode]
    save(doc)
    print(f"{args.episode} released back to the queue")
    return finish(args, f"queue: {who} releases {args.episode}")


def finish(args, message: str) -> int:
    """Optionally publish the claim immediately, so the other account sees it."""
    if not getattr(args, "push", False):
        print("(not pushed — commit and push so the other account can see it, "
              "or pass --push)")
        return 0
    for cmd in (["git", "add", "work/CLAIMS.json"],
                ["git", "commit", "-m", message],
                ["git", "pull", "--rebase", "--autostash", "origin", "main"],
                ["git", "push", "origin", "main"]):
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        if r.returncode != 0:
            print(f"{' '.join(cmd[:2])} failed:\n{r.stdout}{r.stderr}",
                  file=sys.stderr)
            return 1
    print("pushed")
    return 0


def main() -> int:
    # Shared so --as works on either side of the subcommand: people type
    # `claims.py claim ep02 --as x` far more often than the other order.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--as", dest="account", help="which account you are")
    common.add_argument("--push", action="store_true",
                        help="commit and push the change right away")

    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter,
                                 parents=[common])
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", parents=[common],
                   help="show episodes, claims and the backlog").set_defaults(
        func=cmd_list)
    sub.add_parser("whoami", parents=[common],
                   help="print the identity this checkout will use"
                   ).set_defaults(func=lambda a: (print(identity(a.account)), 0)[1])

    p = sub.add_parser("claim", parents=[common], help="take an episode")
    p.add_argument("episode")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_claim)

    p = sub.add_parser("done", parents=[common],
                       help="mark an episode finished")
    p.add_argument("episode")
    p.add_argument("--url", help="public link, if published")
    p.add_argument("--pr", help="pull request number")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_done)

    p = sub.add_parser("release", parents=[common], help="give an episode back")
    p.add_argument("episode")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_release)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
