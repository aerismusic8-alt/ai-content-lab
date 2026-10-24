# GITHUB LIMITS — will it be a bottleneck, and is two accounts worth it

Every number below was measured in this repository on 2026-10-24, or quoted from
GitHub's own documentation. Nothing here is from memory.

## The three separate limits people mix up

They are independent, and only one of them is close.

| Limit | Value | Our position | Headroom |
|---|---|---|---|
| API requests | 5,000/hour per account | 12 used | enormous |
| Content-generating requests | 80/minute, 500/hour | a few per episode | enormous |
| Repository size | ideally < 1 GB, strongly < 5 GB | **4.0 MB** | enormous |

Measured directly:

```
GET /rate_limit  ->  core: limit 5000, used 12, left 4988
GET /repos/...   ->  size: 4.0 MB
```

Two accounts means **two of each**. The API limit is per account, so two accounts
literally double the hourly budget — but at 12 requests used out of 5,000 that
budget was never the constraint.

**So: GitHub will not be a bottleneck for API calls.** Not now, and not at any
volume this project can reach.

## The one limit that does approach

Repository **size**, because git keeps every version of every file forever.

What one episode actually adds to the clone:

| Content | Size | Notes |
|---|---|---|
| source images | 3.16 MB | 16 files, ~200 KB each — the growth driver |
| poster + API JSON | 0.36 MB | |
| narration, timings, scenes | 0.05 MB | negligible |
| **total per episode** | **3.57 MB** | |
| video + audio | 18.9 MB | **kept out** — lives in a GitHub Release |

Projection, from those measured numbers:

| Pace | Per month | Per year | 1 GB reached |
|---|---|---|---|
| 4 channels × 2 episodes | 29 MB | 0.33 GB | ~3.1 years |
| 4 channels × 4 episodes | 57 MB | 0.67 GB | ~1.5 years |
| 4 channels × 8 episodes | 114 MB | 1.34 GB | ~9 months |

And git keeps earlier versions too. Re-rendering an image twice on average
triples the history:

| Pace (with 3× blob history) | Per year | 1 GB reached |
|---|---|---|
| 4 × 2 episodes | 1.00 GB | **~1.0 year** |
| 4 × 4 episodes | 2.01 GB | **~6 months** |

So the honest answer: **at a real production pace, the repository crosses 1 GB
within about a year, and 5 GB in a few years.** That is the actual bottleneck,
and it is a size problem, not a rate problem.

Note the two distinct ceilings, both from GitHub's docs:

* **50 MiB** per file — git warns, the push still succeeds.
* **100 MiB** per file — GitHub blocks it outright. A video that big is exactly
  why videos go to Releases and never into the clone.

## What was fixed

The source images were being stored exactly as downloaded — a 207 KB file for an
image used at 1024 px. `scripts/fetch_images.py` now re-encodes on save
(`shrink()`), capping the width and using quality 82.

Measured on a real file:

```
raw 207KB -> shrunk 131KB   (37% smaller)
```

and the same measurement across all 16 source images:

```
current files            3236K
recompress q82 at 1024px 2263K   (31% smaller)
```

Nothing is lost: the sources are about 1024 px and the poster is 1920×1080, so
the cap does not touch the visible quality. The function refuses to grow a file,
and `--max-width 0 --quality 0` restores the old behaviour exactly (verified: it
returns the identical bytes).

That roughly **halves the time to reach 1 GB** and costs nothing.

## Pros and cons of running two accounts

### Advantages

1. **The YouTube upload cap doubles.** This is the real prize and the reason to
   do it at all. The cap is ~**19 uploads/day per Google account, shared across
   every channel on it**. Four channels on one account share 19; on two accounts
   each side gets its own 19, and one side being blocked does not stop the other.
   *No GitHub limit is fixed by a second account — GitHub's limits are not the
   problem.*
2. **Parallel work without collisions.** Two accounts can build two episodes at
   once, coordinated by `work/CLAIMS.json`.
3. **A genuine second reviewer.** A quality gate run by someone who did not make
   the episode catches more.
4. **Blast-radius separation.** A token leak or a bad change on one account does
   not touch the other's channels.

### Disadvantages

1. **Coordination cost.** Two writers to one repository need the claim rule and
   pull requests. Skip that and they overwrite each other. This is the price, and
   it is why `scripts/queue.py` exists.
2. **Two sandboxes, two sets of credentials.** Each account needs its own OAuth
   authorisation, and each token dies with its pod.
3. **Two clones, twice the disk.** GitHub's size limit is per repository, so this
   does **not** double our size headroom — the same repository is cloned twice.
4. **Easy to publish from the wrong account.** The wrong-channel hazard already
   bit once; two accounts and four channels multiply it. That is why
   `assert_channel()` refuses to upload when the token belongs to another channel.
5. **The upload cap is still shared per account.** Two channels on the *same*
   account still share 19/day. Splitting accounts only helps if the channels are
   split *across* the accounts.

## Ranked bottlenecks, and what to do

| # | Bottleneck | When it bites | Action |
|---|---|---|---|
| 1 | YouTube ~19 uploads/day per Google account | immediately at 4 channels | split channels across the two accounts |
| 2 | Repository size | ~6–12 months at a real pace | compression (done), and prune blob history when it hurts |
| 3 | Two writers colliding | immediately, if unmanaged | `scripts/queue.py` claim rule (done) |
| 4 | GitHub API rate limit | never at this scale | nothing |
| 5 | 100 MiB per-file block | never, if media stays in Releases | keep the release step |

## Verdict

* **GitHub is not the bottleneck.** 12 of 5,000 requests used, 4 MB of a
  recommended 1 GB. Rate limits are irrelevant here.
* **Size is the only GitHub limit that approaches**, and it is a year away, and
  the cheap fix is already in.
* **Two accounts are worth it — for the YouTube cap, not for GitHub.** GitHub
  gains nothing from a second account except parallelism and a second reviewer.
* **The cost of two accounts is coordination**, and that is now handled by the
  claim file. Without it, two accounts would be worse than one.
