# PLAN — two OpenHands accounts, four YouTube channels

Written 2026-10-24. Read with `docs/GOAL.md` and `docs/CONTENT-PLAN.md`.

## The situation

* Two OpenHands accounts. This one is the **builder**.
* Four YouTube channels already created, each with its own angle. The angle for
  each is not recorded anywhere yet — that is the first gap to close.
* The current pipeline (ep01: Thai narration, poster cards, loudness master,
  Range server, machine-readable channel, YouTube upload) is approved.

## The short answer

**Do not split the pipeline between the two accounts. Split the channels.**

The pipeline is one machine. Two people maintaining it is how it rots: the second
account would hit the same sandbox limits, the same ffmpeg traps, the same
copyright checks, and would fix them a second time in a second repository. What
actually needs two hands is not the code, it is the **channels**, because of one
hard limit found earlier:

> A YouTube upload cap of roughly **19 videos/day applies per Google account,
> and is shared across every channel under that account** (measured: a burst was
> still blocked 12 hours later; it is a rolling ~24h window, not a midnight
> reset).

Four channels on one Google account share that 19/day. Split across two accounts
and each side gets its own 19/day, and one side failing does not stop the other.

## Who does what

| | OpenHands account 1 (builder) | OpenHands account 2 |
|---|---|---|
| Owns | the pipeline, `scripts/`, the skill | a channel or two, end to end |
| Owns channels | 1–2 channels | the other 2–3 channels |
| Job | make the machine, keep it honest | run the machine, feed it, publish |
| Writes to | `scripts/`, `docs/`, `.agents/skills/` | `episodes/`, its channel's `meta.json` |
| Does not touch | its own channel's editorial calls | `scripts/` (proposes instead) |

Reason for that split: the pipeline is a shared dependency, so it needs one
owner and a stable interface. The channel work is parallel, so it scales by
adding hands. Account 2 gets a real job — producing episodes and posting them —
without needing to understand the colour grade or the ffmpeg flags.

## How account 2 plugs in

Not by cloning and forking. Three options, best first.

### 1. Collaborator on the same repo (recommended)

The repo token already has **admin** on `kongkeat938/ai-content-lab`, so the
second account can be invited as a collaborator and push branches.

* One repository, one skill, one pipeline. Nobody re-fixes a bug twice.
* Account 2 works on `episodes/<slug>/` and opens a pull request.
* Conflicts stay small because the work is file-per-episode.
* GitHub is the coordination point, and it survives both sandboxes being recycled.

Invite: repo → Settings → Collaborators → add the second account → it accepts →
then it can push.

### 2. Separate repo per channel, same pipeline as a submodule

Works if the two accounts must not share a repository. Costs a sync step every
time the pipeline changes, and the copy will drift. Only worth it if the accounts
belong to different people who do not trust each other's commits.

### 3. Fully separate, copied pipeline

Worst. Guarantees the two sides diverge and both re-learn the same traps. Do not.

## Credentials: the part that will bite

This is the hazard that already bit once, recorded in memory:

> A browser can silently reuse whichever Google account is already signed in, so
> authorising can hand back a token for a **different channel than intended**.

With two accounts and four channels that risk multiplies. The rules:

1. **One token per channel**, never one token for everything.
   `scripts/publish_youtube.py` already resolves a separate token file per
   channel and refuses to upload when the token belongs to the wrong channel
   (`assert_channel`). Channel 1's token cannot publish to channel 2.
2. **Record `channel_id` per channel** in `channels.json`. The upload hard-stops
   on a mismatch instead of quietly posting to the wrong place.
3. **One uploader at a time.** The 19/day cap is per account, so two processes on
   the same account will fight. Queue instead of running in parallel.
4. **Never commit a token.** They live in `~/.config/content-lab/`, mode 600, and
   are gitignored. A token on a shared repo is a channel takeover.

## Why this is the right shape, in one line

The pipeline is a **shared dependency** — it needs one owner and a stable
interface. The channels are **parallel work** — they scale by adding hands. That
is the same reason a factory does not build two copies of its own assembly line.

## Also worth doing with account 2

Account 2 should not only produce more episodes. Two jobs that are genuinely
separate and genuinely useful:

* **Quality gate.** A second pair of eyes on each episode before it goes public:
  loudness, timing, text overflow, and whether the story reads in Thai. This is
  the job that catches a bad episode before a viewer does, and it is better done
  by someone who did not make it.
* **Channel research.** Which public-domain Thai works fit which channel's angle,
  and the copyright check for each. That is slow, parallel, and does not touch
  the pipeline.

## Steps, in order

| # | Step | Owner |
|---|---|---|
| 1 | Write down the four channels: name, handle, angle, target audience | K |
| 2 | Invite account 2 as a collaborator on the repo | K |
| 3 | Fill `channels.json`: one entry per channel, with `channel_id` and token path | builder |
| 4 | Register the sandbox redirect URI in Google Cloud console, authorise each channel once | K, one click per channel |
| 5 | Build ep02 มัทนะพาธา as the reference episode for the new format | builder |
| 6 | Account 2 produces its first episode using the same pipeline | account 2 |
| 7 | Account 2 reviews one of the builder's episodes | account 2 |

## What not to do

* Do not let both accounts edit `scripts/` at the same time. One owner.
* Do not share one OAuth token across channels.
* Do not run two uploaders on the same account; the cap is shared.
* Do not let either account publish publicly without review. Uploads land private
  by design.
