"""Thai narration builder — free cloud TTS (edge-tts) + ffmpeg mastering.

Reusable across episodes. Reads a Thai script, prepares it for natural
speech, synthesises with edge-tts, and masters to broadcast level.

Usage:
    python make_audio.py <script.txt> <out.mp3> [--voice VOICE] [--tail SILENCE]

The quality rules encoded here (all measured, see docs/RECIPE.md):
  * newlines are the pause mechanism — edge-tts inserts ~1.1 s per newline
  * Thai digits must be spelled out; edge-tts has no Thai number dictionary
  * Thai has no intra-phrase spaces — strip them, keep newlines
  * loudnorm must be two-pass or it misses the target by ~1 LUFS
"""
import argparse
import asyncio
import json
import os
import re
import subprocess
import sys

import edge_tts

# --- Thai text preparation -------------------------------------------------

DIGITS = ["ศูนย์", "หนึ่ง", "สอง", "สาม", "สี่", "ห้า", "หก", "เจ็ด", "แปด", "เก้า"]
PLACES = ["", "สิบ", "ร้อย", "พัน", "หมื่น", "แสน"]
THAI = "\u0E00-\u0E7F"

# Latin abbreviations the synthesiser would otherwise spell out letter by letter.
ABBREV = {
    "AI": "เอไอ", "OK": "โอเค", "DJ": "ดีเจ", "IQ": "ไอคิว",
    "WiFi": "ไวไฟ", "YouTube": "ยูทูบ", "BTC": "บีทีซี", "CD": "ซีดี",
}

UNITS = {
    "ดอลลาร์": "ดอลลาร์", "เซนต์": "เซนต์", "บาท": "บาท", "ปี": "ปี",
    "นาที": "นาที", "ชั่วโมง": "ชั่วโมง", "วัน": "วัน", "เดือน": "เดือน",
}


def _six(digits: str) -> str:
    """Up to six digits -> spoken Thai, with the ยี่สิบ / เอ็ด exceptions."""
    out, n = [], len(digits)
    for i, ch in enumerate(digits):
        d = int(ch)
        if d == 0:
            continue
        place = n - i - 1
        if place == 0:
            out.append("เอ็ด" if (d == 1 and n > 1) else DIGITS[d])
        elif place == 1:
            out.append("สิบ" if d == 1 else ("ยี่สิบ" if d == 2 else DIGITS[d] + "สิบ"))
        else:
            out.append(DIGITS[d] + PLACES[place])
    return "".join(out)


def spell_number(num: str) -> str:
    """Integer string -> spoken Thai, grouped by ล้าน."""
    num = num.lstrip("0") or "0"
    if num == "0":
        return "ศูนย์"
    groups = []
    while num:
        groups.append(num[-6:])
        num = num[:-6]
    parts = []
    for i in range(len(groups) - 1, -1, -1):
        g = groups[i].lstrip("0")
        if g:
            parts.append(_six(g) + "ล้าน" * i)
    return "".join(parts)


def prep(text: str) -> str:
    """Normalise Thai text for synthesis without destroying the pauses."""
    for k, v in ABBREV.items():
        text = re.sub(rf"\b{re.escape(k)}\b", v, text)
    text = re.sub(r"\b(\d+)\b", lambda m: spell_number(m.group(1)), text)
    # Strip spaces *between Thai characters* only. `[^\S\n]` is whitespace
    # except newline -- plain `\s` would eat the newlines and kill every pause.
    text = re.sub(rf"(?<=[{THAI}])[^\S\n]+(?=[{THAI}])", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\s*\n\s*", "\n", text)
    return text.strip()


# --- synthesis -------------------------------------------------------------

async def synth_with_boundaries(text: str, voice: str, rate: str, pitch: str,
                                out: str, attempts: int = 5) -> list:
    """Synthesise and capture boundary events for exact timing.

    Thai voices emit `SentenceBoundary` (not `WordBoundary`); both are collected
    so the caller does not care which the engine chose. Each event carries the
    spoken text plus its start offset in 100-nanosecond ticks.
    """
    for i in range(attempts):
        bounds, got = [], 0
        try:
            comm = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
            with open(out, "wb") as f:
                async for chunk in comm.stream():
                    if chunk["type"] == "audio":
                        f.write(chunk["data"])
                        got += len(chunk["data"])
                    elif chunk["type"] in ("WordBoundary", "SentenceBoundary"):
                        bounds.append({
                            "type": chunk["type"],
                            "text": chunk["text"],
                            "offset_sec": chunk["offset"] / 1e7,
                            "duration_sec": chunk["duration"] / 1e7,
                        })
            if got > 5000 and bounds:
                return bounds
            print(f"  incomplete stream, retrying ({i + 1}/{attempts})",
                  file=sys.stderr)
        except Exception as e:  # noqa: BLE001 - retry any transport error
            print(f"  attempt {i + 1} failed: {e}", file=sys.stderr)
        await asyncio.sleep(1.5 * (i + 1))
    raise RuntimeError(f"boundary synthesis failed after {attempts} attempts: {out}")


async def synth(text: str, voice: str, rate: str, pitch: str, out: str,
                attempts: int = 5) -> None:
    """edge-tts with backoff.

    `NoAudioReceived` is intermittent and unrelated to text length; a retry
    almost always succeeds. Never treat one failure as a broken voice.
    """
    for i in range(attempts):
        try:
            comm = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
            with open(out, "wb") as f:
                async for chunk in comm.stream():
                    if chunk["type"] == "audio":
                        f.write(chunk["data"])
            if os.path.getsize(out) > 5000:
                return
            print(f"  short output, retrying ({i + 1}/{attempts})", file=sys.stderr)
        except Exception as e:  # noqa: BLE001 - retry any transport error
            print(f"  attempt {i + 1} failed: {e}", file=sys.stderr)
        await asyncio.sleep(1.5 * (i + 1))
    raise RuntimeError(f"synthesis failed after {attempts} attempts: {out}")


# --- mastering -------------------------------------------------------------

TARGET_I, TARGET_TP, TARGET_LRA = -14.0, -3.0, 11.0

# Warm, even, with a hint of room. The 3.2 kHz cut removes the harsh band
# edge-tts is known for; the compressor evens out the level between lines.
CHAIN = (
    "highpass=f=85,"
    "equalizer=f=110:t=q:w=0.9:g=2.5,"
    "equalizer=f=260:t=q:w=1.0:g=1.2,"
    "equalizer=f=3200:t=q:w=1.2:g=-2.5,"
    "equalizer=f=6800:t=q:w=1.6:g=2.0,"
    "acompressor=threshold=-18dB:ratio=3:attack=8:release=180:makeup=2,"
    "aecho=0.8:0.85:22:0.10"
)


def run(cmd: list) -> None:
    subprocess.run(cmd, check=True, capture_output=True)


def loudnorm2(src: str, dst: str, pad: float = 0.0) -> None:
    """Two-pass EBU R128 normalisation to the -14 LUFS YouTube target.

    Any trailing silence is added inside the same encode. Writing it as a
    separate intermediate and renaming over `dst` silently changed the
    container (a .mp3 target ended up as a 56 MB WAV).
    """
    out = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", src, "-af",
         f"loudnorm=I={TARGET_I}:TP={TARGET_TP}:LRA={TARGET_LRA}:print_format=json",
         "-f", "null", "-"], capture_output=True, text=True).stderr
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", out, re.S)
    if not m:
        raise RuntimeError(f"loudnorm measurement failed for {src}")
    s = json.loads(m.group(0))
    chain = (
        f"loudnorm=I={TARGET_I}:TP={TARGET_TP}:LRA={TARGET_LRA}"
        f":measured_I={s['input_i']}:measured_TP={s['input_tp']}"
        f":measured_LRA={s['input_lra']}:measured_thresh={s['input_thresh']}"
        f":offset={s['target_offset']}:linear=true"
    )
    if pad > 0:
        chain += f",apad=pad_dur={pad}"
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-af", chain,
         "-ar", "48000", "-ac", "2", dst])


def measure(path: str) -> tuple:
    out = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", path,
         "-af", "ebur128=peak=true", "-f", "null", "-"],
        capture_output=True, text=True).stderr
    tail = out.split("Summary:")[-1]
    i = re.search(r"I:\s*(-?\d+\.\d+)\s*LUFS", tail)
    p = re.search(r"Peak:\s*(-?\d+\.\d+)\s*dBFS", tail)
    return (i.group(1) if i else "?", p.group(1) if p else "?")


def duration(path: str) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", path], capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def build(script: str, out: str, voice: str, rate: str, pitch: str,
          tail: float) -> dict:
    text = prep(open(script, encoding="utf-8").read())
    tmp = out + ".raw.mp3"
    staged = out + ".staged.wav"
    asyncio.run(synth(text, voice, rate, pitch, tmp))
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", tmp, "-af", CHAIN,
         "-ar", "48000", "-ac", "2", staged])
    loudnorm2(staged, out, pad=tail)
    lufs, peak = measure(out)
    info = {
        "script": script, "out": out, "voice": voice, "rate": rate,
        "pitch": pitch, "chars": len(text), "lines": len(text.splitlines()),
        "duration_sec": round(duration(out), 2),
        "lufs": lufs, "true_peak_dbfs": peak,
    }
    for f in (tmp, staged):
        if os.path.exists(f):
            os.remove(f)
    return info


def build_with_timing(script: str, out: str, voice: str, rate: str, pitch: str,
                      tail: float, timing_out: str) -> dict:
    """Same as build(), but also records exact per-line start times.

    The line timings drive the video: every newline in the script becomes one
    card, and the card changes when the synthesiser reaches that line. Word
    boundaries are used (not a chars/sec estimate) because estimates have been
    wrong by 2x.
    """
    raw_text = open(script, encoding="utf-8").read()
    text = prep(raw_text)
    tmp = out + ".raw.mp3"
    staged = out + ".staged.wav"
    bounds = asyncio.run(synth_with_boundaries(text, voice, rate, pitch, tmp))

    # Map each prepared line to the moment the synthesiser starts speaking it.
    # The boundary events carry the spoken text, so we concatenate them into one
    # string, remember the time of every character, then locate each line in it.
    # This is exact — no chars/sec estimate (those have been wrong by 2x).
    lines = text.split("\n")
    spoken = "".join(b["text"] for b in bounds)
    times = []
    for b in bounds:
        times.extend([b["offset_sec"]] * len(b["text"]))

    def norm(s: str) -> str:
        return re.sub(r"\s+", "", s)

    starts, cursor = [], 0
    for ln in lines:
        key = norm(ln)
        if not key:
            starts.append(None)
            continue
        idx = spoken.find(key, cursor)
        if idx < 0:
            idx = spoken.find(key)
        if idx < 0 or idx >= len(times):
            starts.append(None)
        else:
            starts.append(times[idx])
            cursor = idx + len(key)
    matched = sum(1 for s in starts if s is not None)
    print(f"  timing: {matched}/{len(lines)} lines matched", file=sys.stderr)

    run(["ffmpeg", "-y", "-loglevel", "error", "-i", tmp, "-af", CHAIN,
         "-ar", "48000", "-ac", "2", staged])
    loudnorm2(staged, out, pad=tail)

    dur = duration(out)
    timing = {
        "duration_sec": round(dur, 3),
        "words": bounds,
        "lines": [
            {"text": lines[i], "start": round(starts[i], 3) if starts[i] is not None else None}
            for i in range(len(lines))
        ],
    }
    with open(timing_out, "w", encoding="utf-8") as f:
        json.dump(timing, f, ensure_ascii=False, indent=2)

    lufs, peak = measure(out)
    info = {
        "script": script, "out": out, "voice": voice, "rate": rate,
        "pitch": pitch, "chars": len(text), "lines": len(lines),
        "words": len(bounds), "duration_sec": round(dur, 2),
        "lufs": lufs, "true_peak_dbfs": peak, "timing": timing_out,
    }
    for f in (tmp, staged):
        if os.path.exists(f):
            os.remove(f)
    return info


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    ap.add_argument("out")
    ap.add_argument("--voice", default="th-TH-NiwatNeural")
    ap.add_argument("--rate", default="-12%")
    ap.add_argument("--pitch", default="-10Hz")
    ap.add_argument("--tail", type=float, default=2.5,
                    help="seconds of silence appended at the end")
    ap.add_argument("--info", default=None, help="write JSON report here")
    ap.add_argument("--timing", default=None,
                    help="write per-line timings JSON here (enables exact sync)")
    a = ap.parse_args()
    if a.timing:
        info = build_with_timing(a.script, a.out, a.voice, a.rate, a.pitch,
                                 a.tail, a.timing)
    else:
        info = build(a.script, a.out, a.voice, a.rate, a.pitch, a.tail)
    print(json.dumps(info, ensure_ascii=False, indent=2))
    if a.info:
        with open(a.info, "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
