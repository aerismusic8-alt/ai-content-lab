# AGENTS.md

The live copy of this file sits at the workspace root (`/workspace/project/AGENTS.md`),
where an agent finds it automatically. This copy is committed so the rules travel
with the repository to GitHub.

---

Instructions for any agent working in this repository.

## What this is

`content-lab/` builds **Thai narrated story videos** — about 20 minutes each —
from **public-domain Thai literature**, using **free tools only**. The finished
work is pushed to `kongkeat938/ai-content-lab` and served from a link.

## Read these first

| Document | What it holds |
|---|---|
| `content-lab/docs/GOAL.md` | the brief, the seven requirements, and the definition of done |
| `content-lab/docs/CONTENT-PLAN.md` | the episode slate and the copyright evidence |
| `content-lab/docs/RECIPE.md` | measured technical settings for audio, colour, sync |
| `content-lab/docs/API.md` | the publishing channel an agent pulls from |
| `.agents/skills/thai-story-video/SKILL.md` | how to build an episode, step by step |

## Non-negotiable rules

1. **Thai sources only.** Do not adapt a foreign story. Episode 1 (O. Henry's
   *The Gift of the Magi*) failed for exactly this reason: its plot turns on one
   dollar eighty-seven cents, and a Thai listener cannot feel what that buys.
2. **Check copyright before writing.** Thai copyright is the author's life plus
   50 years. Record the author's death date and where it came from. Never use a
   translation of a Thai work — the translation has its own copyright.
3. **Free tools only.** No paid API, no subscription, no generative image model.
4. **Attribute everything.** Photograph licences and creators live in
   `assets/images/credits.json` and are shown on the page.
5. **Verify before claiming done.** Loudness, true peak, colour range, line
   timings and seekability all have a check in the skill. Run them.
6. **Publish the channel after every episode.** Run `scripts/build_api.py` and
   attach the media with `scripts/publish_release.sh`. Media goes to a GitHub
   Release, never into git — a 15 MB video per episode would make a repository
   nobody can clone.

## Conventions

* Narration scripts are the director's instrument: one clause per line, blank
  line between beats, `[speaker]` tag to switch voice. See the skill.
* Numbers are spelled as Thai words in scripts, never left as digits.
* Audio targets **-14 LUFS** with true peak at or below **-3 dBFS**.
* Video is **1920x1080, `yuv420p`, `color_range=tv`**.
* Media blobs (mp4, mp3) are gitignored — they are regenerable from the scripts.
  Fonts, images, timings and scripts are committed.
* The page is served with `scripts/serve.py`, never `python3 -m http.server`,
  because the standard library server ignores Range headers and the video then
  cannot be seeked.

## Working style the user expects

* Communicates in **Thai**; wants concise Thai answers.
* Wants **evidence, not claims** — measured numbers, not assurances.
* On **Windows (PowerShell)**. Never hand over `&&`, `chmod` or `mkdir -p`; give
  native PowerShell or UI steps.

## Environment

* Sandbox is a pod that is **recycled about 20 minutes after the session goes
  idle**. Nothing in it survives: no cron, no systemd as PID 1. Re-run
  `scripts/watch_site.sh` after a recycle, and expect the link to die again.
* `ffmpeg` is **not** preinstalled. `sudo apt-get update && sudo apt-get install
  -y ffmpeg` works.
* `ss`, `netstat`, `lsof` and `file` are **not** installed.
* Long renders race the idle timer. Work in stages and commit often.
