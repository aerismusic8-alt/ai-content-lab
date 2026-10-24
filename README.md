# ของขวัญของคนโง่ — The Gift of the Magi

A 5-minute Thai narrated story video, built end to end with free tools only.
No paid API, no stock subscription, no generative image model.

**ฟัง / listen:** open `site/index.html` (see "Running locally" below).

| | |
|---|---|
| Episode | `ep01_gift_of_the_magi` |
| Length | 5:05 |
| Narration | Thai, `th-TH-NiwatNeural` (edge-tts, free) |
| Loudness | -14.4 LUFS, true peak -3.4 dBFS |
| Visuals | 8 poster-style cards, 1920x1080 |
| Source text | O. Henry, *The Gift of the Magi* (1905) — public domain |
| Images | Openverse, CC BY 2.0 / PDM 1.0 |
| Fonts | Kanit, Prompt (SIL Open Font License) |

## Pipeline

```
narration_th.txt ──> make_audio.py ──> audio_th.mp3 + timing.json
                          │                    │
                          │                    ▼
scenes.json ──────────────┴────────> make_video.py ──> video.mp4
      │                                   ▲
      └──> make_poster.py ────────────────┘
                 ▲
   fetch_images.py ──> assets/images/
```

### 1. Source text

```bash
curl -sL -o sources/gift_magi_raw.txt https://www.gutenberg.org/cache/epub/7256/pg7256.txt
```

Gutenberg requires following redirects (`-L`). The text is public domain, so the
only obligation is not to imply endorsement by Project Gutenberg.

### 2. Narration script

`episodes/<ep>/narration_th.txt` is written for the ear, not the page. One idea
per line; a blank line is a real pause. The synthesiser turns each newline into
roughly a second of silence, so line breaks are the rhythm instrument.

### 3. Audio

```bash
python3 scripts/make_audio.py episodes/ep01_gift_of_the_magi/narration_th.txt \
    episodes/ep01_gift_of_the_magi/audio_th.mp3 \
    --timing episodes/ep01_gift_of_the_magi/timing.json \
    --info episodes/ep01_gift_of_the_magi/audio_info.json
```

### 4. Background images

```bash
python3 scripts/fetch_images.py queries.json assets/images --per-query 2
```

Every image is recorded in `assets/images/credits.json` with its licence and
creator. Only CC0, PDM, CC BY and CC BY-SA are accepted.

### 5. Video

```bash
python3 scripts/make_video.py episodes/ep01_gift_of_the_magi
```

### 6. Listen

```bash
python3 scripts/serve.py 12000 site
```

## Publishing channel

Every episode is published as machine-readable JSON so an agent can pull it and
post it without a human copying anything:

| | |
|---|---|
| `GET /llms.txt` | orientation written for an AI agent |
| `GET /api/index.json` | catalogue of all episodes |
| `GET /api/episodes/<slug>.json` | one episode, including ready-to-post text |
| `GET /feed.xml` | Atom feed with media enclosures |
| `POST /api/receipts` | report what was posted |

`posting.youtube`, `posting.facebook`, `posting.tiktok` and `posting.blog` hold
text that is already formatted, and `media.video.url` is a permanent download
link. See `docs/API.md`.

Three ways for an agent to use it:

* `GET /llms.txt` — the instructions are inline, so nothing else is needed
* `scripts/mcp_server.py` — the channel as five MCP tools (config: `mcp.json`)
* `scripts/post.py` — a command-line client, `--list | --platform | --download | --report`

A copy-paste prompt for an AI is in `docs/AGENT-PROMPT.md`.

## Publishing to YouTube

The pipeline can upload an episode and report the link back on the channel.
It needs a one-time OAuth token, which only a human with a browser can grant:

```bash
python3 scripts/yt_auth.py          # once; prints a URL to approve
scripts/publish_episode.sh episodes/ep02_mattanaphatha private
```

Uploads land **private** by default. Setup details, including the redirect URI
that has to be registered in Google Cloud console, are in
`docs/PUBLISHING.md`.

## Working with a second account

Two OpenHands accounts cannot see each other's conversations, so they coordinate
through this repository: `work/QUEUE.md` is the backlog and
`scripts/queue.py` records who has which episode.

```bash
python3 scripts/queue.py list
python3 scripts/queue.py claim ep02 --as account-1 --push
```

See `docs/TWO-ACCOUNTS.md`.

## Layout

```
scripts/          pipeline (audio, images, posters, video, API, posting client)
assets/fonts/     OFL fonts
assets/images/    fetched photos + credits.json
episodes/<ep>/    narration_th.txt, scenes.json, audio, timing, video
site/             the listening page (index.html + media/)
docs/RECIPE.md    what was learned, and the traps
```

## Licence

Source story is public domain. Photographs keep their original licences, listed
in `assets/images/credits.json` and shown on the page. Fonts are OFL. The
scripts in `scripts/` are free to reuse.
