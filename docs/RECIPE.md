# RECIPE — building a narrated story video with free tools

Everything here was measured on this project. Where a number appears, it came
from `ffprobe` or `ffmpeg` output, not from an estimate.

## Tools

| Need | Tool | Cost |
|---|---|---|
| Narration | `edge-tts` | free, no key |
| Mastering | `ffmpeg` (`loudnorm`, `acompressor`) | free |
| Images | Openverse API | free, no key |
| Fonts | Google Fonts (Kanit, Prompt) | OFL, commercial use OK |
| Story text | Project Gutenberg | public domain |

## Thai text preparation is the biggest quality lever

The synthesiser reads characters, not meaning. Before synthesis:

* **Spell out every digit.** edge-tts has no Thai number dictionary, so `187`
  becomes English digits or silence. Convert to `หนึ่งร้อยแปดสิบเจ็ด`.
  Exceptions that matter: `21` -> `ยี่สิบเอ็ด` (not `ยี่สิบหนึ่ง`),
  `101` -> `หนึ่งร้อยเอ็ด`, and `ล้าน` for the million group.
* **Expand Latin abbreviations** (`AI` -> `เอไอ`) or they are spelled letter by
  letter.
* **Strip spaces between Thai characters**, but never newlines. Use
  `(?<=[ก-๛])[^\S\n]+(?=[ก-๖])` — a plain `\s` also eats newlines and destroys
  every pause.

## Pauses come from newlines

edge-tts inserts roughly one second of silence per newline. That is the whole
rhythm system: one clause per line, blank line for a beat. Rate `-12%` and pitch
`-10Hz` on `th-TH-NiwatNeural` reads as a calm storyteller rather than a
newsreader.

## Timing: use boundary events, never a character estimate

Thai voices emit **`SentenceBoundary`**, not `WordBoundary`. Both carry the
spoken text and a start offset in 100-nanosecond ticks.

The reliable way to time the visuals is to concatenate the boundary texts into
one string, keep the start time of every character, then `find()` each script
line inside it. That matched **108/108 lines** on this episode.

Estimating from characters per second was wrong by up to 2x — the pauses between
lines dominate, and they are not proportional to text length.

## Two ffmpeg traps that cost real time

1. **`-vsync vfr` together with `-r 25` is a hard error** ("contradictory").
   Use `-fps_mode cfr -r 25` for the concat demuxer.
2. **JPEG input decodes as `yuvj420p` (full range).** Encoding it straight to
   `yuv420p` gives washed-out or crushed levels on most players. Always convert:
   `-vf "scale=in_range=full:out_range=tv,format=yuv420p" -color_range tv`.

## Never pad by renaming an intermediate

Writing the padded audio as `out.padded.wav` and then `os.replace(padded, out)`
silently replaced an `.mp3` with a 56 MB WAV — the extension lied. Fold the
padding into the same encode: append `,apad=pad_dur=<sec>` to the loudnorm
filter chain.

## Loudness

Target **-14 LUFS** (what YouTube normalises to) with true peak at or below
-3 dBFS. `loudnorm` must run **two-pass**: measure first with
`print_format=json`, then encode with `measured_I`, `measured_TP`,
`measured_LRA`, `measured_thresh` and `linear=true`. Single pass missed the
target by about 1 LUFS.

Measured result: **-14.4 LUFS, true peak -3.4 dBFS**.

## Voice chain

```
highpass=f=85
equalizer=f=110:t=q:w=0.9:g=2.5      # body
equalizer=f=260:t=q:w=1.0:g=1.2
equalizer=f=3200:t=q:w=1.2:g=-2.5    # remove the harsh edge
equalizer=f=6800:t=q:w=1.6:g=2.0     # air
acompressor=threshold=-18dB:ratio=3:attack=8:release=180:makeup=2
aecho=0.8:0.85:22:0.10
```

## Poster look

Measured from a set of movie-poster references:

* dark, high contrast (brightness 37-132, sd 36-84)
* muted colour, saturation **0.29-0.60**
* 2:3 portrait for real posters; 16:9 for video cards

To hit that on a video card: raise saturation about 1.35x, add a teal-orange
split (shadows cooler, highlights warmer), then a heavy radial vignette. Note
that the vignette and shadow crush drain colour — grading down first and then
darkening leaves the image grey, so grade *up* and darken after.

## Retries are mandatory

`edge-tts` fails with "No audio was received" intermittently, unrelated to text
length. Retry with backoff; a single failure never means the voice is broken.
Same for Openverse: a page fetch can time out, and continuing on the next page
recovers most of the results.
