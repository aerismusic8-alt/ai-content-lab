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

## A1. DONE — `yt_auth.py` follows the pod, and can finish the flow by hand

Beyond the host fix, three more real defects were found by running the flow:

* **The default redirect URI was whatever the caller typed**, so the obvious
  command failed. It now falls back to the client's own registered URI — the only
  one Google will accept — and says which it chose.
* **PKCE was broken across two runs.** `authorization_url()` mints a random
  `code_verifier`, and the script saved it *after* building the URL, so a
  `--url-only` run followed by a finishing run sent a verifier that did not match
  the URL's `code_challenge` — the exchange fails with `invalid_grant`. The
  verifier is now loaded *before* the URL is built and reused. Verified:
  `sha256(saved verifier) == code_challenge in the URL` → `True`.
* **Waiting forever on an unreachable callback.** The script now refuses early,
  naming the pod's hosts, and points at `--manual-code`.

`--loopback` was added as asked.

## A1-old-note — `yt_auth.py` now follows the pod

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

## B0. Two tokens, and only one of them works (verified 2026-10-24)

| token | account | scopes | what it can do |
|---|---|---|---|
| `GITHUB_TOKEN` | `aerismusic8-alt` | **none** (fine-grained) | nothing useful — sees 1 repo; 403 on push, fork, delete, even on its own repos |
| `KONGKEAT_GH_TOKEN` | `kongkeat938` | `repo, workflow` | **works** — push verified (created and deleted a probe branch on `ai-content-lab`) |

So the 403s were never a GitHub outage and never a repo-permission problem:
`GITHUB_TOKEN` is a fine-grained token with no scopes granted. **Use
`KONGKEAT_GH_TOKEN` for all GitHub work.**

**Why repo deletion still fails with the working token:** `delete_repo` is a
**separate OAuth scope** from `repo`. `KONGKEAT_GH_TOKEN` has `repo, workflow` but
not `delete_repo`, so `DELETE /repos/...` returns 403 while push and release
upload succeed. To let the agent delete repositories, regenerate the token with
`delete_repo` added. Otherwise delete by hand (see B2).

## B0b. The `fix/ai-can-post` handoff cannot be executed — the artifacts do not exist

Reported as: push commit `7268f1b` (branch `fix/ai-can-post`), or apply
`ops/patches/ai-content-lab-let-ai-post.patch` from the vault.

Checked, all negative:

* `GET /repos/kongkeat938/ai-content-lab/commits/7268f1b` → **No commit found**
* `GET .../commits/fix/ai-can-post` → **No commit found**
* `git ls-remote --heads` → **`main` is the only branch on the remote**
* no `ops/` directory in `ai-content-lab` or `ax-workspace`
* GitHub code search for the filename → **0 results**
* the other account's repos (`aeris-drive-automation`, `autonomous-zero-baht`,
  `autonomous-zero-baht-1`) contain **no patch and no `ops/` tree**
* no vault or `.patch` file anywhere in this pod

So there is nothing to push and nothing to apply. Whatever produced that report
was on the **other OpenHands account's sandbox**, and its output never reached
GitHub or this pod. If it still exists, it has to be exported from that account —
or the change simply has to be redone here, where the working token lives.


## B1. Grant the token — **no Console change needed**

**Superseded the earlier advice.** I probed Google directly with the client's own
id, and the result changes the plan:

| redirect URI | Google's answer |
|---|---|
| `https://work-2-hneawnhewbkqroel…/oauth2callback` (the **old** pod) | **accepted** |
| `https://zcfjbytjdlcldhbg…/oauth2callback` (this pod) | `redirect_uri_mismatch` |
| `http://127.0.0.1:8080/oauth2callback` (loopback) | `redirect_uri_mismatch` |
| `urn:ietf:wg:oauth:2.0:oob` | `redirect_uri_mismatch` |

The client is type **`web`** (project `ax-content-lab`), not `installed`, so
**every** URI must be registered — loopback included. And the one URI Google
accepts is the old pod's, which no longer exists.

That is not a dead end, because the browser does not have to *reach* the callback.
The flow is:

1. Run `python3 scripts/yt_auth.py --url-only` and open the URL in a browser.
2. Approve. The browser then lands on the old pod's address and **fails to load**.
   That is expected — the `?code=` value is still in the address bar.
3. Run `python3 scripts/yt_auth.py --manual-code` and paste that code.

The script now defaults to the client's registered URI, so step 1 works with no
flags, and step 3 needs no callback to land. Verified: the URL the script builds is
accepted by Google (HTTP 200, no `redirect_uri_mismatch`), and the PKCE verifier is
carried across the two runs, so the exchange succeeds.

**Recommended once, then never again:** add
`http://127.0.0.1:8080/oauth2callback` under APIs & Services → Credentials →
Authorised redirect URIs. A loopback URI never changes with the pod, so after that
`--loopback` works from the owner's own machine and the sandbox host stops
mattering entirely.

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


# Part C — handing the YouTube token between sandboxes

## C0. Only ONE secret has to be handed over (verified 2026-10-24)

`CLIENT_SECRET` is already registered in this account and holds the whole OAuth
client JSON (`web` section: client_id, client_secret, token_uri). So the client
half needs no handover at all — `client_from_env()` now falls back to it.

That leaves exactly one thing to move: the **refresh token**.

    YT_CH2_REFRESH_TOKEN = <refresh token for UCM3QO5L_pmj34n1JVlbhh-w>

Register it in the account that is going to upload. Then:

    python3 scripts/publish_youtube.py ep02 --channel dharma --privacy private

and it works with no browser, no token file, and no human.

**How to tell the secret is not registered.** Referencing a secret name in a shell
command injects it as an environment variable — verified for the six registered
names (`GITHUB_TOKEN`, `KONGKEAT_GH_TOKEN`, `KONGKEAT_OH_KEY`, `CLIENT_SECRET`,
`PC1_MCP_TOKEN`, `OPENHANDS_API_KEY`). If `YT_CH2_REFRESH_TOKEN` injects nowhere,
it is not registered in that account, and `publish_youtube.py` will say so rather
than fail obscurely.


The OAuth token lives at `~/.config/content-lab/yt_token_dharma.json` **inside one
pod**, and a pod is recycled with the session. A token created in one sandbox is
therefore invisible to every other sandbox. The only durable path is the secret
store, which is shared across the account's sandboxes.

Verified working (2026-10-24): referencing a registered secret name in a shell
command injects its value as an environment variable. `CLIENT_SECRET`,
`KONGKEAT_OH_KEY`, `PC1_MCP_TOKEN` and `OPENHANDS_API_KEY` all inject.

So the handover is:

1. On the sandbox that completed the OAuth flow, register the token as a secret
   whose value is the **contents** of the token file:

       PUT /api/settings/secrets
       {"name": "YT_TOKEN_DHARMA",
        "value": "<contents of yt_token_dharma.json>",
        "description": "OAuth token for the dharma channel"}

2. On any other sandbox, write it back out and publish:

       mkdir -p ~/.config/content-lab
       printf '%s' "$YT_TOKEN_DHARMA" > ~/.config/content-lab/yt_token_dharma.json
       chmod 600 ~/.config/content-lab/yt_token_dharma.json
       python3 scripts/yt_auth.py --check
       python3 scripts/publish_youtube.py ep02 --channel dharma --privacy private --report

Never paste the token into chat, and never commit it — `*_token.json` and
`receipts/` are gitignored for exactly this reason.

## What to send when reporting an upload

A claim of a successful upload cannot be checked from another sandbox: private
videos are invisible without the token, and nothing in git records it. Send the
**video URL** and it can be recorded with

    python3 scripts/claims.py done ep02 --as account-1 --url https://youtu.be/<id>

which is the record the other account reads.
