# TWO ACCOUNTS — how they work together without mixing things up

Short version: the two OpenHands accounts **cannot talk to each other**. They are
separate logins with separate sandboxes, and a conversation belongs to the
account that started it. So they coordinate through **one shared repository**
instead, which both can read and write.

## What does not work, and why

| Idea | Why not |
|---|---|
| Account 1 sees account 2's chats | Conversations are private to the owning account. No cross-account view, no shared inbox. |
| One agent drives both accounts | Needs a token for each account. Only one account's key is available here. |
| One long shared conversation | Sandboxes are recycled when idle (~20 min), and a conversation cannot be shared anyway. |
| One repo, two people editing `scripts/` | Guaranteed to break. One owner for the pipeline. |

The honest constraint: an agent can only act as **the account whose key it
holds**. With one key, this agent is one account. The second account is a
separate login that you start yourself, and it picks up work from the repository.

## What does work: the repository is the bus

Both accounts clone the same repo and use three shared files:

| File | Purpose |
|---|---|
| `work/QUEUE.md` | the backlog, in priority order |
| `work/CLAIMS.json` | who is doing which episode, right now |
| `docs/` | the shared brief, so both judge quality the same way |

And one tool, `scripts/queue.py`:

```bash
python3 scripts/queue.py list                      # what is free, what is taken
python3 scripts/queue.py claim ep02 --as account-1  # take it
python3 scripts/queue.py done ep02 --as account-1 --url https://youtu.be/XXXX
python3 scripts/queue.py release ep02 --as account-1
```

Add `--push` to publish the claim immediately so the other account sees it at
once.

### Why this cannot mix things up

`work/CLAIMS.json` is a lock. Whoever commits first wins: if both accounts claim
the same episode, the second one's push conflicts and it has to pick another.
The tool also refuses a claim that someone else holds, and refuses to mark
another account's episode done. For two people, that is enough.

## The setup, once

1. **Invite the second account** as a collaborator:
   repo → Settings → Collaborators → add it → it accepts.
   The repo token has admin, so this works.
2. **Give each account an identity**, so the queue records the right name.
   Either put a line in `.work-account` in that checkout, or set `OH_ACCOUNT`:

   ```bash
   echo "account-2" > .work-account     # this checkout is account 2
   ```
3. **Second account clones and reads the brief:**

   ```bash
   git clone https://github.com/kongkeat938/ai-content-lab.git
   cd ai-content-lab
   cat AGENTS.md docs/GOAL.md work/QUEUE.md
   ```

That is the whole handover. The second account now knows the rules, the format,
the quality bar and what is free to build.

## Rules both accounts follow

1. **Claim before you build.** One episode, one owner.
2. **Only the pipeline owner edits `scripts/`.** The other proposes, in an issue
   or a pull request.
3. **Work on a branch, open a pull request.** Do not push to `main`.
4. **Uploads land private.** Making an episode public is a human decision.
5. **One uploader per Google account at a time.** The ~19/day cap is shared
   across every channel on the account.
6. **Never commit a token.** They live in `~/.config/content-lab/`, mode 600.

## Division of work

| | Account 1 (pipeline owner) | Account 2 |
|---|---|---|
| Owns | `scripts/`, `docs/`, the skill | its channels' episodes |
| Builds | the machine, and ep02 as the reference | episodes 3, 5, 7, … |
| Also does | keeps the pipeline honest | quality gate, channel research |

Account 2's two extra jobs are worth calling out, because they are genuinely
separate work:

* **Quality gate.** Check another account's finished episode before it goes
  public: loudness, timing, text overflow, and whether the Thai actually reads
  well. Someone who did not make it catches more.
* **Channel research.** Which public-domain Thai works fit which channel, and the
  copyright check for each. Slow, parallel, touches no pipeline code.

## How you (K) drive it

You do not have to remember which account is which. Type into whichever one is
handy, and it will:

* read `work/QUEUE.md` and `work/CLAIMS.json` to see what is free,
* claim before it starts,
* and push the claim so the other side sees it.

If both accounts are asked for the same episode at the same time, the second one
to push loses the race and picks another — by design.

## Still missing

The four channels exist but their **names, handles and angles are not recorded
anywhere**. That blocks the sensible split: which account owns which channel, and
which stories fit. Fill in the channel table in `work/QUEUE.md` first.
