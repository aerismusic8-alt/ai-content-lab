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

The four channels, verified live 2026-10-24. Source of truth is
`../ax_channels.json` in the `ax-workspace` repository; `ax_channels.py show`
prints this table. Do not edit the table here — edit that file and run
`ax_channels.py emit-content-lab`.

| ch | handle | direction | goal | length | quota | account |
|---|---|---|---|---|---|---|
| ch1 | `@tatagenxgeny` | ช่องปรัชญา | พูดปรัชญาที่คนฟังจนจบ | ~11 นาที | — | openhands-1 |
| ch2 | `@Farmmer-n9t` | ช่องธรรมะก่อนนอน | หลับก่อนจบ กลับมาทุกคืน | 10–12 นาที | — (rail ต้นแบบ) | openhands-1 |
| ch3 | `@aerismusicth` | ช่องสร้างศิลปินเพลง | 1 ศิลปิน/เดือน 10 เพลง | 3–4 นาที | AiPASS เพลง 10/เดือน | to assign |
| ch4 | `@aerisanime` | ช่องละคร · การ์ตูนอะนิเมะ | ซีรี่ส์ที่ติดตามตอนต่อตอน | 10–25 นาที | AiPASS วิดีโอ 10/เดือน ≈ 50 วิ | to assign |

**ch1 and ch2 use this pipeline as it is.** ch2 (dharma) is the reference — make
changes there first. **ch3 and ch4 are new pipelines** and should not start until
ch1/ch2 run unattended.

**Two consequences worth holding on to:**

* **ch4 is slow by construction.** 10 clips a month at ~50 s is about 8 minutes of
  footage, and an episode of 10–25 minutes needs 12–30 clips. That is roughly one
  episode every 1.2–3 months, or 4–10 a year. Plan the first series at 10–12
  minutes, or the cadence will not hold.
* **ch3 has no slack.** 10 songs a month, one artist a month, exactly.

An earlier spec (2026-10-23) had ch3 and ch4 the other way round. The live
channels contradict it: ch3 is the music label. Do not "restore" the old order.

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
