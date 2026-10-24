# GOAL — Thai story videos, free tools only

This file is the durable statement of what we are building. Read it at the start
of any new session. It is written so a fresh agent can pick the work up without
asking. Companion documents: `docs/CONTENT-PLAN.md` (episode slate and the
copyright evidence), `docs/RECIPE.md` (measured technical settings),
`.agents/skills/thai-story-video/SKILL.md` (how to actually build one).

## The brief

Build narrated Thai story videos, roughly **20 minutes each**, from **Thai
literary works in the public domain**, using only free tools. One finished
episode must be watchable through a shareable link.

Seven requirements, and where each one is handled:

| # | Requirement | Where |
|---|---|---|
| 1 | Thai-culture stories, open subject, long enough for ~20 min | `docs/CONTENT-PLAN.md` |
| 2 | A director's script written for Thai voice-over | `scripts/make_audio.py` + script format below |
| 3 | Male and female voices, adjusted to the story and the emotion | voice presets below |
| 4 | Poster-style background art | `scripts/make_poster.py` |
| 5 | Background music, chosen by the director | `scripts/fetch_music.py` + `make_video.py` |
| 6 | A link to watch the finished result | `scripts/serve.py` + `scripts/watch_site.sh` |
| 8 | A machine-readable channel so an AI can pull and post | `scripts/build_api.py` + `docs/API.md` |
| 7 | The goal, the skill and the memory must survive a session change | this file, `AGENTS.md`, `.agents/skills/`, `.openhands/memory/` |

## Why Thai sources, not translated ones

Episode 1 was O. Henry's *The Gift of the Magi*. It read badly in Thai: the whole
plot turns on one dollar eighty-seven cents, and a Thai listener has no feel for
what that buys. Money, rent, wages and Christmas are load-bearing in that story
and none of them land.

Rule that follows: **the story must be Thai, and any amount of money must be
translated into something the listener can feel** — a bowl of noodles, a day's
wages, a sack of rice — or left out entirely.

## What "public domain" means here

Thai copyright runs for the life of the author **plus 50 years** (Copyright Act
B.E. 2537, section 19). So a work is free to use once the author died more than
50 years ago — currently anyone who died before 1976.

Verified examples (evidence in `docs/CONTENT-PLAN.md`):

| Work | Author | Author died | Status |
|---|---|---|---|
| มัทนะพาธา | King Rama VI | 2468 (1925) | public domain |
| ลิลิตพระลอ | anonymous, Ayutthaya | — | public domain |
| ขุนช้างขุนแผน | traditional / folk | — | public domain |
| ไกรทอง, สังข์ทอง | traditional, Rama II redaction | 2367 (1824) | public domain |
| ข้างหลังภาพ | ศรีบูรพา (กุหลาบ สายประดิษฐ์) | 2517 (1974) | public domain since 2024 |

A translation is a separate work with its own copyright. Use the Thai original,
not an English translation.

## Voices: two voices, many characters

edge-tts offers exactly two Thai voices — `th-TH-NiwatNeural` (male) and
`th-TH-PremwadeeNeural` (female). Piper has one Thai voice. So a cast is built by
**varying prosody per character**, not by finding more voices.

Director's presets (tune by ear, these are starting points):

| Role | Voice | rate | pitch | Reads as |
|---|---|---|---|---|
| ผู้เล่า (narrator) | Niwat | -12% | -10Hz | calm storyteller |
| พระเอก / หนุ่ม | Niwat | -6% | +12Hz | younger, brighter |
| นางเอก | Premwadee | -8% | +0Hz | warm, clear |
| ตัวร้าย / ผู้ใหญ่ | Niwat | -16% | -18Hz | heavier, slower |
| เด็ก | Premwadee | -4% | +25Hz | light, quick |
| บรรยายอารมณ์เศร้า | Niwat | -18% | -14Hz | grief, slow |

Emotion is carried by the same levers: **rate down for grief, rate up for
tension, pitch down for menace, pitch up for youth.** Never push rate past about
-20% or it drags.

## Script format (requirement 2)

The narration file is the director's instrument. One idea per line; a blank line
is a pause. A speaker tag at the start of a line switches voice.

```
[ผู้เล่า] กลางเมืองสุโขทัยยามค่ำ
[ผู้เล่า] มีมาณพหนุ่มผู้หนึ่ง หลงรักดอกกุหลาบที่แปลงกายเป็นหญิง

[มาณพ] เจ้าจงรักข้าเถิด
[มัทนา] ข้ารักเจ้าได้อย่างไร ในเมื่อเจ้ามิใช่คน
```

Rules the builder depends on:

* `[speaker]` at line start selects a preset from `voices.json`; no tag means the
  narrator.
* One clause per line. The synthesiser turns each newline into roughly a second
  of silence — that silence *is* the rhythm.
* Spell out numbers as Thai words; do not rely on the engine.
* Blank line between beats.

## Target length

Measured from episode 1: **0.11 seconds of audio per character**, and each
newline contributes about a second of silence.

For a 20-minute episode that means roughly:

* **8,000–10,000 Thai characters** of script
* **250–300 lines** (one clause each)
* **14–18 poster cards**, so a card holds the screen for about 80 seconds

## Episode slate

Priority order, with reasons, in `docs/CONTENT-PLAN.md`. Short version:

1. **มัทนะพาธา** (ep02) — a love tragedy with a male and a female lead, vivid
   imagery for poster art, and Thailand's most quoted romantic verse.
2. **ข้างหลังภาพ** (ep03) — the most relatable to a modern Thai listener.
3. **ขุนช้างขุนแผน**, one episode only — the epic is far too long to adapt whole.

## Constraints

* **Free tools only.** No paid API, no subscription, no generative image model.
* **Attribute everything.** Photographs keep their licence and creator, listed in
  `assets/images/credits.json` and shown on the page.
* **The sandbox is temporary.** The pod is recycled about 20 minutes after the
  session goes idle, so the link dies with it. Re-run `scripts/watch_site.sh`
  after a recycle. For a link that lasts, the `site/` folder has to be deployed
  somewhere real — that needs the user's approval.
* **Long renders race the idle timer.** Split work into stages and commit often.

## Where the work is stored

Three places, and it matters which is which:

| What | Where | Survives a sandbox recycle? |
|---|---|---|
| Scripts, docs, images, fonts, timings | `kongkeat938/ai-content-lab` (git) | yes — clone it anywhere |
| Video and audio (large) | GitHub **Releases** of the same repo | yes — permanent download URL |
| The API, feed and llms.txt | committed to git under `site/api/` | yes |
| The running site and the link | the sandbox pod, port 12000 | **no** — dies with the pod |

The repo is the source of truth. `git clone` plus `pip install edge-tts` plus
`apt-get install ffmpeg` is enough to rebuild every episode from scratch.

**Large media never goes into git.** A 15 MB video committed per episode means
ten episodes is a ~150 MB repository that is slow to clone and keeps every
version forever. Attach it to a release instead:

```bash
scripts/publish_release.sh episodes/ep02_mattanaphatha
# -> https://github.com/kongkeat938/ai-content-lab/releases/download/ep02/ep02.mp4
```

That URL is permanent, unlike the sandbox link.

## Definition of done for an episode

* narration script with speaker tags, in `episodes/<ep>/narration_th.txt`
* `timing.json` where **every** line matched a boundary event
* audio at **-14 LUFS**, true peak at or below **-3 dBFS**
* a music bed, ducked under the voice
* poster cards, one per scene, no text overflow
* scene cuts landing on the line that opens the scene
* video `yuv420p`, `color_range=tv`, 1920x1080
* the page loads and the video can be **seeked** (range requests work)
* committed to `kongkeat938/ai-content-lab`
* media attached to a GitHub Release with `scripts/publish_release.sh`
