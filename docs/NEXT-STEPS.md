# NEXT-STEPS — the handoff

Written 2026-10-24. Everything an AI can fix on its own is in Part A. The two
things only the owner can do are in Part B. Each item carries the evidence that
found it, so a fresh session does not have to re-investigate.

---

# Part A — for the AI

## A0. Already done in this session — do not redo

Three real defects were found and fixed while writing this handoff. Recorded here
so a fresh session does not spend time rediscovering them.

1. **`scripts/queue.py` shadowed the standard library.** With `scripts/` on
   `sys.path`, `import queue` resolved to that file, so `urllib3` — reached
   through `requests`, through the Google libraries — died with
   `AttributeError: module 'queue' has no attribute 'LifoQueue'`. Anything that
   imports `requests` was broken. Renamed to `scripts/claims.py` and every
   reference updated; `scripts/check_script_names.py` now fails if any script
   shadows a stdlib module. Verified: `import queue` resolves to
   `/usr/local/lib/python3.13/queue.py` again.
2. **`yt_auth.py` now reads the pod host from `$RUNTIME_URL`** instead of a frozen
   literal, which is what caused `redirect_uri_mismatch` after a recycle. See A1.
3. **`yt_auth.py --check` no longer raises a traceback** when the Google libraries
   are absent; it prints the `pip install` command. Verified.

## A1. DONE — `yt_auth.py` now follows the pod

Fixed. `sandbox_hosts()` reads `$RUNTIME_URL` and `$WORK_HOST_{1,2}` first, keeps
the old literals as a fallback, and `--print-redirects` names the source of each
URI. Verified output:

```
  https://zcfjbytjdlcldhbg.prod-runtime.all-hands.dev/oauth2callback   ($RUNTIME_URL)
  https://work-1-zcfjbytjdlcldhbg.prod-runtime.all-hands.dev/oauth2callback   (fallback list)
```

**What remains:** add the `--loopback` mode in A3.

## A1-old. The defect, for the record

The script hardcoded the sandbox hostnames:

```python
SANDBOX_HOSTS = [
    "work-1-zcfjbytjdlcldhbg.prod-runtime.all-hands.dev",
    "work-2-zcfjbytjdlcldhbg.prod-runtime.all-hands.dev",
]
```

Evidence that this is wrong: `grep -n RUNTIME_URL scripts/yt_auth.py` returns
nothing, while the environment already publishes the current pod's public host in
`$RUNTIME_URL` (verified: `https://zcfjbytjdlcldhbg.prod-runtime.all-hands.dev`,
reachable). So every time the pod is recreated the list must be hand-edited, which
is exactly the bug that caused `redirect_uri_mismatch`.

**Do:** build the candidate list from the environment first, and keep the literal
list only as a fallback:

1. `$RUNTIME_URL` (the bare host, already public)
2. `$WORK_HOST_1` / `$WORK_HOST_2` if the platform sets them
3. the current hardcoded list, last

`--print-redirects` must print all candidates, de-duplicated, and say which one
came from the environment. Add a `--check` assertion that fails loudly if
`RUNTIME_URL` is set but not in the printed list.

**Test:** run `python3 scripts/yt_auth.py --print-redirects` and confirm the
current pod's host appears, with the environment named as its source.

## A2. DONE — the stale row in `work/QUEUE.md` is corrected

It said:

```
| Fill in the four channels (name, handle, angle, audience) | blocks everything else | K |
```

That is done — all four channels are recorded in `ax_channels.json` with handles,
ids, directions, goals and quotas. Replace the row with a pointer to
`../AX_CHANNELS.md`, and move any remaining real work to the pipeline rows.

## A3. Add a loopback option so OAuth stops depending on the pod

The sandbox hostname changes, but a **loopback redirect never does**. The owner's
machine runs Windows 11 with Python 3.14.7 (verified), so
`http://127.0.0.1:8080/oauth2callback` is available and permanent.

**Do:** add a `--loopback` mode to `yt_auth.py` that:

* starts the same callback catcher on `127.0.0.1:<port>`, default 8080
* prints the authorisation URL for the owner to open **on their own machine**
* prints the exact redirect URI to register, once, forever:
  `http://127.0.0.1:8080/oauth2callback`
* on success, writes the token to `~/.config/content-lab/yt_token_<slug>.json`

Because the token file is what gets copied back, the token does not need to be
created inside the pod at all. Document that path in `docs/PUBLISHING.md` as the
**preferred** method, with the sandbox-host method kept as a fallback.

**Test:** `--loopback --print-redirects` must print the loopback URI, and the
existing sandbox flow must still work.

## A4. Prove the OAuth flow without the real client, then stop

Once Part B is done, run the real thing. Before that, do **not** invent a token.
Instead:

* `python3 scripts/yt_auth.py --check` must fail with a clear message when no
  token exists (already does — keep it)
* `python3 scripts/publish_youtube.py ep01 --channel dharma --dry-run` must
  resolve the channel, print `expect UCM3QO5L_pmj34n1JVlbhh-w`, and exit without
  uploading (already does — keep it)

Report these two outputs as evidence that everything but the owner's grant works.

## A5. Regenerate the two generated files, do not hand-edit them

`content-lab/channels.json` and `content-lab/site/channels.html` are generated by
`ax_channels.py emit-content-lab` and `ax_channels.py emit-html` from
`ax_channels.json` in the `ax-workspace` repository.

**Do:** after any channel change, edit `ax_channels.json` and re-run both. Never
edit the two generated files directly — that is how the table and the upload guard
would drift apart.

## A6. Two reminders about the environment

* **The pod is recycled ~20 minutes after it goes idle.** Anything not committed
  and pushed is lost. `ax-workspace` is the private repo for the spec and the
  memory; `ai-content-lab` is the public repo for the pipeline.
* **`ffmpeg` is not preinstalled** on a fresh pod. `sudo apt-get install -y
  ffmpeg` works; plain `apt-get` fails on the dpkg lock.

---

# Part B — only the owner can do these

## B1. Register the redirect URI, then grant the token

The OAuth client's only registered redirect URI points at an **old pod**
(`work-2-hneawnhewbkqroel…`), so every attempt now fails with
`redirect_uri_mismatch`.

**In Google Cloud Console** → APIs & Services → Credentials → your OAuth 2.0
client → Authorised redirect URIs → **add both**:

```
http://127.0.0.1:8080/oauth2callback
https://work-1-zcfjbytjdlcldhbg.prod-runtime.all-hands.dev/oauth2callback
https://work-2-zcfjbytjdlcldhbg.prod-runtime.all-hands.dev/oauth2callback
```

The first one never needs changing again. Then tell the AI to run the authorisation
and approve it in the browser when the consent screen appears.

## B2. Delete the leftover probe repository

The GitHub token can **create** repositories (verified 201) but **cannot delete**
them (verified 403), so this one is stuck:

```
https://github.com/kongkeat938/__probe_delete_me__/settings
```

Open that URL, scroll to the bottom, **Delete this repository**. It is empty and
private, so nothing is lost.

---

# Handing Part A to an AI

Paste this, with the two repos already cloned:

> Work in `kongkeat938/ax-workspace` (spec + memory) and `kongkeat938/ai-content-lab`
> (the pipeline, in `content-lab/`). Read `AX_CHANNELS.md`, `AGENTS.md` and
> `content-lab/docs/NEXT-STEPS.md`. Do **Part A** only, in order, starting with A1.
> For each item: make the change, run the test named in the item, and report the
> command and its real output as evidence. Do not claim a result you have not run.
> Part B needs the owner; skip it and say so.
>
> Two rules: commit and push when you finish (the pod is recycled ~20 min after it
> goes idle), and never hand-edit `content-lab/channels.json` or
> `content-lab/site/channels.html` — they are generated.

---

# State, so nothing is re-litigated

| Fact | Value |
|---|---|
| ch1 | `@tatagenxgeny` — ตาต้า GenX Shop — ช่องปรัชญา — ~11 min — 14 videos |
| ch2 | `@Farmmer-n9t` — Farmmer — ช่องธรรมะก่อนนอน — 10–12 min — 10 videos |
| ch3 | `@aerismusicth` — AERIS Music — ช่องสร้างศิลปินเพลง — 3–4 min — 1 video |
| ch4 | `@aerisanime` — Aeris Anime — ช่องละคร·การ์ตูนอะนิเมะ — 10–25 min — 3 videos |

* An earlier spec had ch3/ch4 swapped. The live channels contradict it: **ch3 is
  the music label**. The correction is recorded under `_superseded`.
* ch1 and ch2 use the existing pipeline as-is; **ch2 is the reference**. ch3 and
  ch4 are new pipelines and should wait.
* ch4 yields only **4–10 episodes a year** at its AiPASS quota (10 clips/month at
  ~50 s ≈ 8 minutes of footage, against 12–30 clips per episode).
* GitHub is not a bottleneck (12 of 5,000 requests/hour; 4.0 MB of 1 GB). Repo
  size is the only limit that approaches, and `fetch_images.py` now compresses on
  save (measured 31% smaller).
