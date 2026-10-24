# AGENT-PROMPT — copy this to an AI to have it publish the stories

Two ways to connect an AI. Pick one.

* **MCP** if the AI supports it (Claude Desktop, OpenHands, any MCP host). It
  gets real tools and needs no URLs.
* **Prompt** if it does not. Paste the block below.

---

## Option 1 — MCP

Register this server with the AI host:

```json
{
  "mcpServers": {
    "thai-story-channel": {
      "command": "python3",
      "args": ["/abs/path/to/content-lab/scripts/mcp_server.py"],
      "env": { "CHANNEL_BASE": "https://work-1-zcfjbytjdlcldhbg.prod-runtime.all-hands.dev" }
    }
  }
}
```

The AI then has five tools: `list_episodes`, `get_episode`, `get_posting`,
`report_posted`, `list_posted`. Nothing else is needed.

Requires `pip install mcp` (the server works with both the 1.x and 2.x API).

---

## Option 2 — paste this prompt

> You publish Thai narrated story episodes from my channel.
>
> **Channel:** `https://work-1-zcfjbytjdlcldhbg.prod-runtime.all-hands.dev`
>
> Start by reading `{channel}/llms.txt`. Then:
>
> 1. `GET {channel}/api/index.json` — the catalogue. Each entry has `id`,
>    `title`, `duration_hms`, `video_url`, `audio_url`, `poster_url`.
> 2. `GET {channel}/api/episodes/<slug>.json` — one episode. Use the `posting`
>    object, which already contains text shaped for the platform. Do not rewrite
>    it unless I ask.
> 3. `GET {channel}/api/receipts` before posting, so you do not publish the same
>    episode twice.
> 4. `POST {channel}/api/receipts` with
>    `{"episode":"ep01","platform":"youtube","url":"<link>"}` after posting.
>
> **Rules:**
> - The `posting.youtube.description` already includes the chapter timestamps,
>   the source work and the attribution. Keep all of it.
> - Stories are public-domain Thai literature, but the photographs are not all
>   public domain. Keep the attribution block and the `credits` list.
> - Attach `media.video.url` as the video and `media.poster.url` as the
>   thumbnail. Both are permanent download links.
> - If a request returns 502 on every path, the host is restarting; tell me
>   rather than retrying in a loop.
>
> **What I want:** publish episode `ep01` to YouTube as a private video first,
> with the title, description, tags and thumbnail from the channel, then report
> the URL back to me.

Replace the last paragraph with what you actually want done.

---

## What the AI gets

`posting` contains, ready to use:

| Field | Content |
|---|---|
| `posting.youtube` | `title`, `description` (with chapters, source, attribution), `tags`, `category_id`, `language`, `made_for_kids` |
| `posting.facebook` | `caption` |
| `posting.tiktok` | `caption` |
| `posting.blog` | `title`, `excerpt`, `body_markdown` |
| `posting.hashtags` | tag list |
| `chapters[]` | `time` + `title`, for YouTube chapters |
| `media.video.url` | permanent video download |
| `media.audio.url` | permanent audio download |
| `media.poster.url` | poster art for the thumbnail |
| `script` | the full Thai narration |
| `credits[]` | image licences and creators |
| `source` | work, author, year, licence, URL |

## Example: a complete run

```bash
# 1. what is there
curl -s $C/api/index.json | python3 -m json.tool | head -30

# 2. the text for one platform
curl -s $C/api/episodes/ep01_gift_of_the_magi.json \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['posting']['youtube']['description'])"

# 3. post it somewhere, then record it
curl -s -X POST $C/api/receipts -H 'Content-Type: application/json' \
  -d '{"episode":"ep01","platform":"youtube","url":"https://youtu.be/XXXX"}'

# 4. confirm
curl -s $C/api/receipts
```

With the bundled client, the same in one line:

```bash
python3 scripts/post.py ep01 --platform youtube
python3 scripts/post.py ep01 --platform youtube --report https://youtu.be/XXXX
```

## Limits an agent should know

* The host is a temporary sandbox. If every path returns 502, it was recycled.
* `POST /api/receipts` is a log, not a database: JSON object only, up to 64 KB,
  no authentication. Do not put anything confidential in it.
* Receipts do not survive a restart of the sandbox.
