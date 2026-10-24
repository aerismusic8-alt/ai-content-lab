# QUEUE — what to build next, and who has it

The shared backlog. Two OpenHands accounts work from this file. Claim an episode
with `scripts/queue.py claim <ep>` **before** starting, so the other account does
not build the same one.

Status lives in `work/CLAIMS.json`; this file is the intent, that file is the
record. `python3 scripts/queue.py list` shows both.

## Ground rules

1. **Claim before you build.** One episode, one owner.
2. **Do not edit `scripts/`** unless you are the pipeline owner. Propose a change
   as an issue or a pull request instead. Two people editing the pipeline at once
   is how it breaks.
3. **Work on a branch**, open a pull request. Do not push to `main` directly.
4. **Uploads land private.** Making an episode public is a human decision.
5. **One uploader at a time per Google account.** The ~19/day cap is shared
   across every channel on that account.
6. **Never commit a token.** Tokens live in `~/.config/content-lab/`, mode 600.

## Channel assignment

Two of the four channels were found by inspecting YouTube on 2026-10-24. The
other two are not discoverable without a name, handle or id — see below.

| Channel | Handle | Channel ID | Angle | Account |
|---|---|---|---|---|
| Farmmer | `@Farmmer-n9t` | `UCM3QO5L_pmj34n1JVlbhh-w` | ธรรมะก่อนนอน — คำสอนพระพุทธเจ้า | openhands-1 |
| ตาต้า GenX Shop | `@tatagenxgeny` | `UCI6EfsgM1HNjrYarvigxyrQ` | ปรัชญาชีวิต — มุมมองดี ๆ | openhands-1 |
| _(unknown)_ | ? | ? | ? | ? |
| _(unknown)_ | ? | ? | ? | ? |

Both found channels already have published videos: Farmmer 10, ตาต้า GenX 14.
They are **not yet authorised** in this sandbox — each needs its own OAuth token.

The other two cannot be found by browsing. A channel is only reachable from a
name, a handle, or a channel id, and none of those is recorded anywhere. To find
them, either give the handle, or sign in and open
<https://studio.youtube.com> to list every channel the account can switch to.

## Episode backlog

| # | Episode | Source | Target | Status |
|---|---|---|---|---|
| ep02 | มัทนะพาธา | King Rama VI, d. 2468 | ~20 min | open |
| ep03 | ข้างหลังภาพ | ศรีบูรพา, d. 2517 | ~20 min | open |
| ep04 | ขุนช้างขุนแผน (one ตอน) | traditional | ~20 min | open |
| ep05 | ไกรทอง | traditional | ~20 min | open |
| ep06 | ลิลิตพระลอ | anonymous, Ayutthaya | ~20 min | open |
| ep07 | สังข์ทอง | traditional | ~20 min | open |

Copyright evidence for each is in `docs/CONTENT-PLAN.md`. Before adding a new
work, check the author's death year: Thai copyright is life **plus 50 years**, so
only authors who died before 1976 are free.

## Work that is not an episode

| Task | Why | Account |
|---|---|---|
| Fill in the four channels (name, handle, angle, audience) | blocks everything else | K |
| `channels.json` for each channel | needed before any upload | pipeline owner |
| Quality gate on a finished episode | catches problems the maker cannot see | the other account |
| Copyright check for a new work | slow, parallel, no pipeline work | either |
| Multi-voice narration (`--voices` + `[speaker]`) | requirement 3, not built yet | pipeline owner |
| Music bed ducked under the voice | requirement 5, not built yet | pipeline owner |

## Definition of done for an episode

From `docs/GOAL.md`, so both accounts judge it the same way:

* ~20 minutes of Thai narration from a public-domain Thai work
* male and female voices where the story has dialogue
* poster-style cards, no text overflow, no text under the duration badge
* loudness about -14 LUFS, true peak at or below -3 dBFS
* the machine-readable channel regenerated (`scripts/build_api.py`)
* media attached to a GitHub Release
* uploaded private, with the URL recorded via `scripts/queue.py done`
