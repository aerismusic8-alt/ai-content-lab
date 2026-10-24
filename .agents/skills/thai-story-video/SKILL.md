---
name: thai-story-video
description: Build Thai narrated story videos (about 20 minutes) from public-domain Thai literature using only free tools. Use when asked to create a Thai story video, a Thai narration, an audio drama, a poster-style video, or to work in the content-lab / ai-content-lab project. Covers copyright checks, director scripts, multi-voice narration, poster art, music, and serving a shareable link.
---

# Thai story video

Turn a public-domain Thai story into a ~20-minute narrated video with poster
art, male and female voices, and a link to watch. Free tools only.

The project lives in `content-lab/` in the workspace and is pushed to
`kongkeat938/ai-content-lab`. Read `docs/GOAL.md` first — it is the brief — and
`docs/CONTENT-PLAN.md` for the episode slate.

## Order of work

1. **Check the copyright.** Thai copyright is the author's life **plus 50
   years**. A work is free once the author died more than 50 years ago. Record
   the death date and its source before writing a single line. Never use a
   translation — a translation is its own copyrighted work.
2. **Write the director's script**, not prose. One clause per line, blank line
   between beats, `[speaker]` tag to switch voice.
3. **Synthesise**, then confirm every line got a timing.
4. **Fetch images**, then build poster cards.
5. **Pick music** and lay it under the voice.
6. **Assemble**, then verify.
7. **Serve** and share the link.
8. **Publish the channel**, so an agent can pull the episode and post it.

## Copyright, the short version

```bash
# author's death date (Wikidata is rate-limited; prefer Wikipedia wikitext)
curl -s "https://th.wikipedia.org/w/api.php?action=query&prop=revisions&rvprop=content&rvslots=main&titles=NAME&format=json&formatversion=2"
# look for death_date in the infobox, or เสียชีวิต / สวรรคต / ถึงแก่อสัญกรรม in the text
```

Verified free: มัทนะพาธา, ลิลิตพระลอ, ขุนช้างขุนแผน, ไกรทอง, สังข์ทอง,
ข้างหลังภาพ. Full texts for most are on Thai Wikisource.

## Director's script format

```
[ผู้เล่า] กลางเมืองสุโขทัยยามค่ำ
[มาณพ] เจ้าจงรักข้าเถิด

[มัทนา] ข้ารักเจ้าได้อย่างไร ในเมื่อเจ้ามิใช่คน
```

* `[speaker]` at the start of a line selects a preset from `voices.json`.
* No tag means the narrator.
* One clause per line — each newline becomes about a second of silence, and that
  silence is the rhythm. Do not write long sentences.
* Spell numbers as Thai words.
* Aim 8,000–10,000 characters and 250–300 lines for 20 minutes.

## Voices

Only two Thai voices exist: `th-TH-NiwatNeural` (male), `th-TH-PremwadeeNeural`
(female). A cast is built by varying rate and pitch per character:

| Role | Voice | rate | pitch |
|---|---|---|---|
| narrator | Niwat | -12% | -10Hz |
| young man | Niwat | -6% | +12Hz |
| woman | Premwadee | -8% | 0Hz |
| villain / elder | Niwat | -16% | -18Hz |
| child | Premwadee | -4% | +25Hz |

Grief = slower and lower. Tension = faster. Menace = lower pitch. Youth = higher
pitch. Never go past about -20% rate; it drags.

## Commands

```bash
cd content-lab

# narration + exact timings
python3 scripts/make_audio.py episodes/<ep>/narration_th.txt \
    episodes/<ep>/audio_th.mp3 \
    --voices episodes/<ep>/voices.json \
    --timing episodes/<ep>/timing.json \
    --info episodes/<ep>/audio_info.json

# background images (licence-gated)
python3 scripts/fetch_images.py queries.json assets/images --per-query 2

# music bed
python3 scripts/fetch_music.py

# poster cards + assembled video
python3 scripts/make_video.py episodes/<ep>

# publish the machine-readable channel (after adding or editing an episode)
python3 scripts/build_api.py

# attach media to a GitHub Release (permanent URL, out of git)
scripts/publish_release.sh episodes/<ep>

# serve with range support, then share
python3 scripts/serve.py 12000 site
```

## The publishing channel

`scripts/build_api.py` writes the channel from the same `scenes.json`,
`timing.json` and `meta.json` the video is built from, so it cannot drift:

| Path | What |
|---|---|
| `/llms.txt` | orientation for an AI agent |
| `/api/index.json` | catalogue |
| `/api/episodes/<slug>.json` | one episode, with a `posting` object |
| `/feed.xml`, `/sitemap.xml` | Atom feed and crawler map |
| `POST /api/receipts` | an agent reports what it posted |

`posting.youtube` / `facebook` / `tiktok` / `blog` hold text already formatted
for each platform. `media.video.url` is a permanent release download link.

Add `episodes/<ep>/meta.json` to control the title, description, tags, hook,
release tag and attribution. Without it, values are derived from `scenes.json`.

Client for the pulling side: `scripts/post.py --list | --platform | --download
| --report`. Docs: `docs/API.md`.

### Handing the channel to another AI

Three ways, in order of how little work they need:

1. **MCP** — `scripts/mcp_server.py` exposes five tools over stdio
   (`list_episodes`, `get_episode`, `get_posting`, `report_posted`,
   `list_posted`). Registration is in `mcp.json`. Needs `pip install mcp`; the
   server handles both the 1.x and 2.x API, because 2.x renamed `FastMCP` to
   `MCPServer`.
2. **llms.txt** — `GET /llms.txt` carries the publishing steps inline, so an
   agent that reads it needs no other document.
3. **A pasted prompt** — `docs/AGENT-PROMPT.md` has a copy-paste block for hosts
   that support neither.

Test the server over the real protocol, not by importing it: send
`initialize`, then `tools/list`, then a `tools/call`.

### Publishing to YouTube directly

The pipeline uploads by itself once it has an OAuth token:

```bash
python3 scripts/yt_auth.py          # once, needs a browser — a human step
scripts/publish_episode.sh episodes/<ep> private
```

* `yt_auth.py` saves to `~/.config/content-lab/yt_token.json` (mode 600),
  **outside the repo**, and gitignored. The sandbox has no browser and Google
  retired the out-of-band flow in 2022, so the callback lands on a public sandbox
  URL; the hostname is registered on the OAuth client and **changes with the
  pod**, which means the redirect URI has to be re-registered each time.
* Every upload lands **private** on purpose. Making it public stays a human
  decision.
* Quota is not the constraint: `videos.insert` and `thumbnails.set` get 100
  calls/day each, separate from the shared 10,000 units.
* The MCP tool `publish_to_youtube` defaults to `dry_run=True`.

## The four channels

The pipeline serves **four** channels, not one. The table lives in
`../AX_CHANNELS.md` (with `AX_CHANNEL_DOSSIERS.md` for the detail) and the
machine-readable copy is `../ax_channels.json`, loaded by `../ax_channels.py`.
Run `python3 ax_channels.py show` for the current table, or
`python3 ax_channels.py emit-content-lab` to rewrite `channels.json` here.

| ch | handle | direction | length |
|---|---|---|---|
| ch1 | `@tatagenxgeny` | ช่องปรัชญา | ~11 นาที |
| ch2 | `@Farmmer-n9t` | ช่องธรรมะก่อนนอน (rail ต้นแบบ) | 10–12 นาที |
| ch3 | `@aerismusicth` | ช่องสร้างศิลปินเพลง | 3–4 นาที |
| ch4 | `@aerisanime` | ช่องละคร · การ์ตูนอะนิเมะ | 10–25 นาที |

Three things follow for the work in this repository:

* **ch1 and ch2 use this pipeline as it is** — same narration-and-posters machine,
  different voice and script. ch2 (dharma) is the reference; change it first.
* **ch3 and ch4 are new pipelines**, not variations. Music videos and serialised
  animation need generation and character-continuity work this pipeline does not
  do. Do not start them until ch1/ch2 run unattended.
* **One token per channel.** `publish_youtube.py` refuses to upload when the token
  belongs to another channel. With four channels that guard is the main safety
  net.

An earlier spec had ch3/ch4 the other way round; the live channels contradict it.
`ax_channels.json` records the correction under `_superseded`.

## Traps that already cost time — do not rediscover these

* **Thai TTS emits `SentenceBoundary`, not `WordBoundary`.** Use those events for
  video sync: concatenate the boundary texts, keep a start time per character,
  then `find()` each script line. A chars-per-second estimate was wrong by 2x.
* **`-vsync vfr` with `-r 25` is a hard ffmpeg error.** Use `-fps_mode cfr`.
* **JPEG decodes as full-range `yuvj420p`.** Convert with
  `scale=in_range=full:out_range=tv,format=yuv420p -color_range tv`, or playback
  looks washed out.
* **Never pad audio by renaming an intermediate file.** Doing that turned a 4.9 MB
  MP3 into a 56 MB WAV still named `.mp3`. Fold padding into the loudnorm chain
  with `,apad=pad_dur=N`.
* **`python3 -m http.server` ignores Range headers**, so the video cannot seek.
  Use `scripts/serve.py`.
* **`ss`, `netstat` and `lsof` are not installed.** Check a port with a Python
  `socket.connect_ex` probe; a missing tool makes a pipe check report "free" on a
  busy port.
* **`edge-tts` fails intermittently** ("No audio was received"), unrelated to text
  length. Retry with backoff; one failure never means a broken voice.
* **Poster grade:** raise saturation about 1.35x *then* darken. Vignetting first
  drains the colour and the result looks grey.

## Verification, before saying it is done

```bash
# loudness and peak
ffmpeg -hide_banner -nostats -i episodes/<ep>/video.mp4 -af ebur128=peak=true -f null - 2>&1 | grep -A6 Summary

# colour range must be tv, pix_fmt must be yuv420p
ffprobe -v error -show_entries stream=pix_fmt,color_range -of default=noprint_wrappers=1 episodes/<ep>/video.mp4

# the page must serve range requests
curl -s -o /dev/null -D - -r 0-999 http://127.0.0.1:12000/media/<file>.mp4 | grep -i content-range
```

Confirm `timing.json` reports every line matched, and that each scene cut lands on
the line that opens it (compare frames half a second either side of the cut).

## The sandbox is temporary

The pod is recycled about 20 minutes after the session goes idle, and the link
dies with it. Re-run `scripts/watch_site.sh` after a recycle. There is no cron
and no systemd, so nothing survives a recycle on its own. A permanent link means
deploying `site/` somewhere real, which needs the user's approval.

## User preferences

Communicates in Thai and wants concise Thai answers with evidence, not claims.
On Windows (PowerShell), so never hand over `&&`, `chmod` or `mkdir -p` — give
native PowerShell or UI steps.
