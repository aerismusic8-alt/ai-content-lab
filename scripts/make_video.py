"""Assemble the episode video: poster cards synced to the narration.

Every scene in scenes.json becomes one poster card. Card changes land exactly
on the narration line that starts the scene, using the timings captured by
make_audio.py (boundary events, not an estimate).

Usage:
    python make_video.py <episode_dir> [--out FILE] [--music FILE]
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import make_poster  # noqa: E402

FPS = 25
W, H = make_poster.W, make_poster.H


def run(cmd: list, **kw) -> None:
    subprocess.run(cmd, check=True, capture_output=True, **kw)


def duration(path: str) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", path], capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def scene_starts(scenes: list, timings: dict, total: float) -> list:
    """Start time of each scene, taken from the first line it contains."""
    lines = timings["lines"]
    starts = []
    for sc in scenes:
        first = sc["lines"][0]
        t = None
        for i in range(first, len(lines)):
            if lines[i]["start"] is not None:
                t = lines[i]["start"]
                break
        starts.append(0.0 if t is None else float(t))
    # Scene 0 always starts at 0; enforce monotonic order and clamp to length.
    starts[0] = 0.0
    for i in range(1, len(starts)):
        if starts[i] <= starts[i - 1]:
            starts[i] = starts[i - 1] + 0.5
    return [min(s, max(0.0, total - 1.0)) for s in starts]


def build(ep_dir: str, out: str, music: str = None) -> dict:
    scenes = json.load(open(os.path.join(ep_dir, "scenes.json"), encoding="utf-8"))["scenes"]
    timings = json.load(open(os.path.join(ep_dir, "timing.json"), encoding="utf-8"))
    audio = os.path.join(ep_dir, "audio_th.mp3")
    total = duration(audio)
    starts = scene_starts(scenes, timings, total)

    tmp = tempfile.mkdtemp(prefix="epvideo_")
    try:
        cards = []
        for i, sc in enumerate(scenes):
            img = os.path.join(ROOT, sc["image"])
            card = os.path.join(tmp, f"card{i:02d}.jpg")
            make_poster.build(img, card, sc["title"], sc.get("subtitle", ""),
                              sc.get("layout", i), sc.get("chapter", ""),
                              index=f"{i + 1:02d}")
            cards.append(card)
            print(f"  card {i + 1}/{len(scenes)}  t={starts[i]:7.2f}s  {sc['title']}")

        # Concatenate with per-card durations so each card is on screen exactly
        # until the next scene begins.
        listfile = os.path.join(tmp, "list.txt")
        with open(listfile, "w", encoding="utf-8") as f:
            for i, card in enumerate(cards):
                end = starts[i + 1] if i + 1 < len(cards) else total
                seg = max(0.2, end - starts[i])
                f.write(f"file '{card}'\n")
                f.write(f"duration {seg:.3f}\n")
            f.write(f"file '{cards[-1]}'\n")  # concat demuxer needs a final entry

        silent = os.path.join(tmp, "silent.mp4")
        # JPEG sources decode as full-range yuvj420p; convert explicitly or the
        # video plays back with washed-out / crushed levels on most players.
        run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
             "-i", listfile, "-fps_mode", "cfr", "-r", str(FPS),
             "-vf", "scale=in_range=full:out_range=tv,format=yuv420p",
             "-color_range", "tv", "-colorspace", "bt709",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
             "-pix_fmt", "yuv420p", "-t", f"{total:.3f}", silent])

        if music:
            m = duration(music)
            # loop the bed to length, keep it well under the voice, then limit
            af = (f"[1:a]aloop=loop=-1:size=2e9,atrim=0:{total:.3f},"
                  f"volume=0.14,afade=t=in:st=0:d=2,"
                  f"afade=t=out:st={max(0, total - 3):.3f}:d=3[m]")
            run(["ffmpeg", "-y", "-loglevel", "error", "-i", silent, "-i", music,
                 "-filter_complex", af, "-map", "0:v", "-map", "[m]",
                 "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                 "-shortest", out])
        else:
            run(["ffmpeg", "-y", "-loglevel", "error", "-i", silent, "-i", audio,
                 "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                 "-c:a", "aac", "-b:a", "192k", "-shortest", out])

        info = {"out": out, "duration_sec": round(duration(out), 2),
                "scenes": len(scenes),
                "scene_starts": [round(s, 2) for s in starts]}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return info


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("episode_dir")
    ap.add_argument("--out", default=None)
    ap.add_argument("--music", default=None)
    a = ap.parse_args()
    out = a.out or os.path.join(a.episode_dir, "video.mp4")
    info = build(a.episode_dir, out, a.music)
    print(json.dumps(info, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
