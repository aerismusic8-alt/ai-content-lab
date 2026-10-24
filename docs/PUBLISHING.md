# PUBLISHING — set up YouTube once, then it runs unattended

The pipeline can upload an episode to YouTube by itself and report the link back
on the channel. It needs one thing only a human can give: an OAuth token.

## The one step that needs you

Google will not let an agent authorise itself, and the sandbox has no browser.
So this is done once, by hand, and the token is then reused forever.

```bash
python3 scripts/yt_auth.py --print-redirects   # which URI to register
python3 scripts/yt_auth.py                     # prints a URL, then waits
```

1. Open the printed URL, choose the Google account that owns the channel, and
   approve. The browser is redirected back into the sandbox and the script
   catches it.
2. The token is saved to `~/.config/content-lab/yt_token.json`, mode 600, outside
   the repository. It is gitignored as well, so it cannot be committed by
   accident.
3. Verify: `python3 scripts/yt_auth.py --check` prints the channel name and id.

If the browser cannot reach the sandbox, use `--manual-code` and paste the
`?code=` value from the address bar instead.

### The redirect URI problem

Google requires the redirect URI to be registered on the OAuth client, and
`urn:ietf:wg:oauth:2.0:oob` was retired in 2022, so a registered URL is the only
way. The client currently has:

```
https://work-2-hneawnhewbkqroel.prod-runtime.all-hands.dev/oauth2callback
```

That hostname belongs to an **old** sandbox. This sandbox is
`work-1-zcfjbytjdlcldhbg...` / `work-2-zcfjbytjdlcldhbg...`, so the redirect will
fail with `redirect_uri_mismatch` until the new URI is added in
Google Cloud console → APIs & Services → Credentials → your OAuth client →
Authorised redirect URIs. Add:

```
https://work-1-zcfjbytjdlcldhbg.prod-runtime.all-hands.dev/oauth2callback
https://work-2-zcfjbytjdlcldhbg.prod-runtime.all-hands.dev/oauth2callback
```

Because sandbox hostnames change on every pod, either re-register each time or,
better, deploy to a host with a stable name.

## Then, one command per episode

```bash
scripts/publish_episode.sh episodes/ep02_mattanaphatha private
```

It rebuilds the channel, attaches the media to a GitHub Release, uploads with the
title, description, chapters, tags and thumbnail from the channel, and records
the URL. The video is **private** by default: review it in YouTube Studio before
making it public.

Or step by step:

```bash
python3 scripts/publish_youtube.py ep02 --dry-run     # what would be posted
python3 scripts/publish_youtube.py ep02 --privacy private --report
```

## From an AI agent

The MCP server exposes two more tools:

| Tool | Use |
|---|---|
| `youtube_status` | is this machine allowed to upload, and to which channel |
| `publish_to_youtube(episode, privacy, dry_run=True)` | upload and report |

`dry_run` defaults to **true**, so an agent that calls it carelessly prints what
would be posted instead of posting. It only uploads when the caller explicitly
passes `dry_run=false`.

## More than one channel

Four channels under one Google account share the daily upload cap, so give each
channel its own token and its own entry in `channels.json`:

```json
{
  "channels": [
    { "slug": "dharma", "name": "...", "channel_id": "UC...", "account": "openhands-1",
      "token_path": "~/.config/content-lab/yt_token_dharma.json" }
  ]
}
```

Then:

```bash
python3 scripts/yt_auth.py --check --expected-channel UCxxxx   # verify
python3 scripts/publish_youtube.py ep02 --channel dharma
```

`publish_youtube.py` resolves the token per channel and calls `assert_channel`
before it uploads a single byte, so a token that belongs to another channel stops
the upload instead of posting to the wrong place. That guard exists because a
browser can silently reuse whichever Google account is signed in.

## Quota

The YouTube Data API gives every project, free:

| Endpoint | Daily allowance |
|---|---|
| `videos.insert` | 100 calls |
| `thumbnails.set` | 100 calls |
| everything else | 10,000 units shared |

Uploads do not come out of the shared 10,000, so one episode per day is nowhere
near that limit. A bad request still costs quota, so failures are not free.

There is a **second, tighter limit that is not in the API docs**: an account can
only upload roughly **19 videos per day, shared across every channel on that
Google account**. It returns `uploadLimitExceeded` (400) rather than a quota
error, and it does **not** reset at midnight Pacific — it behaves as a rolling
~24-hour window from the first upload of the burst. Measured earlier: a burst was
still blocked 12 hours later. Two things follow: run one uploader at a time, and
if four channels share one account they share those 19 uploads.

## What is deliberately not automated

* **Authorising.** Needs a human with a browser. By design.
* **Making a video public.** Every upload lands private. Publishing to the world
  stays a human decision.
* **Comment and reply management.** Out of scope.

## Honest limits

* The token lives on the sandbox disk, so a pod recycle means authorising again.
  To avoid that, keep a copy in the secret store (see the root `AGENTS.md`) or
  deploy to a stable host.
* The channel has no authentication, so `publish_to_youtube` is only as safe as
  who can run it. Keep it on a machine you control.
