"""
add_hebrew_captions.py — Add burned-in Hebrew captions to an English video.

What it does:
  1. Transcribes English audio with faster-whisper (word-level timestamps).
  2. Groups words into short caption-sized chunks (~3–6 words, max ~4s).
  3. Translates each chunk to natural Hebrew via the Claude CLI (batched, 15/call).
  4. Writes a .srt file (Hebrew + timestamps).
  5. Burns the Hebrew subtitles into the video with ffmpeg + libass.

Outputs (next to the input file):
  <name>_he.srt — Hebrew subtitle file
  <name>_he.mp4 — Video with Hebrew captions burned in

Dependencies (Mac):
  brew install ffmpeg
  pip install faster-whisper
  Hebrew system fonts already ship with macOS (Arial Hebrew).

Usage:
  python add_hebrew_captions.py path/to/video.mp4
  python add_hebrew_captions.py video.mp4 --model medium --font "Arial Hebrew"
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from faster_whisper import WhisperModel

BATCH_SIZE = 15
MAX_CHARS_PER_CAPTION = 42
MAX_DURATION_SEC = 4.0
PAUSE_SPLIT_SEC = 0.6
DEFAULT_MODEL = "small"
DEFAULT_FONT = "Noto Sans Hebrew"
CLAUDE_TIMEOUT = 180


def format_timestamp(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", ",")


def transcribe(video_path: Path, model_size: str):
    print(f"Loading Whisper model '{model_size}' (first run downloads ~1 GB)...")
    model = WhisperModel(model_size, device="cpu", compute_type="int8")

    print(f"Transcribing {video_path.name}...")
    segments, info = model.transcribe(
        str(video_path),
        language="en",
        word_timestamps=True,
        vad_filter=True,
    )

    words = []
    for seg in segments:
        if not seg.words:
            continue
        for w in seg.words:
            text = w.word.strip()
            if text:
                words.append((w.start, w.end, text))

    print(f"  → {len(words)} words across {info.duration:.1f}s of audio.")
    return words


def group_into_captions(words):
    """Split words into caption-sized chunks (length + duration + pause + sentence-end)."""
    captions = []
    current = []

    for start, end, word in words:
        if not current:
            current.append((start, end, word))
            continue

        candidate_text = " ".join(w[2] for w in current) + " " + word
        candidate_duration = end - current[0][0]
        gap = start - current[-1][1]
        ends_sentence = current[-1][2].endswith((".", "!", "?"))

        should_break = (
            len(candidate_text) > MAX_CHARS_PER_CAPTION
            or candidate_duration > MAX_DURATION_SEC
            or gap > PAUSE_SPLIT_SEC
            or ends_sentence
        )

        if should_break:
            captions.append((current[0][0], current[-1][1], " ".join(w[2] for w in current)))
            current = [(start, end, word)]
        else:
            current.append((start, end, word))

    if current:
        captions.append((current[0][0], current[-1][1], " ".join(w[2] for w in current)))

    return captions


def translate_batch(english_lines: list[str]) -> list[str]:
    numbered = "\n".join(f"{i+1}. {line}" for i, line in enumerate(english_lines))
    prompt = (
        "תרגם את המשפטים הבאים מאנגלית לעברית שיווקית טבעית.\n"
        "הנחיות:\n"
        "- שמור על תרגום קצר וטבעי, כפי שדובר עברית באמת היה אומר.\n"
        "- ללא ניקוד.\n"
        "- המר יחידות מידה למטריות (אינץ' → ס\"מ, פאונד → ק\"ג, גלון → ליטר).\n"
        "- שמור על אותו מספר שורות, באותו סדר. אל תאחד שורות.\n"
        "- אל תוסיף הסברים, הקדמות או הערות.\n"
        f"החזר JSON בלבד: [\"תרגום1\", \"תרגום2\", ...]\n\n{numbered}"
    )
    result = subprocess.run(
        ["claude", "--print", "-p", prompt],
        capture_output=True, text=True, timeout=CLAUDE_TIMEOUT,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "claude CLI failed")

    output = result.stdout.strip()
    start = output.find("[")
    end = output.rfind("]") + 1
    if start == -1 or end == 0:
        raise ValueError(f"No JSON array in claude output: {output[:300]}")

    translations = json.loads(output[start:end])
    if len(translations) != len(english_lines):
        raise ValueError(
            f"Translation count mismatch: got {len(translations)} for {len(english_lines)} lines"
        )
    return translations


def translate_captions(captions):
    print(f"Translating {len(captions)} caption lines to Hebrew (Claude CLI)...")
    english_lines = [c[2] for c in captions]
    hebrew_lines: list[str] = []

    total_batches = (len(english_lines) + BATCH_SIZE - 1) // BATCH_SIZE
    for i in range(0, len(english_lines), BATCH_SIZE):
        batch = english_lines[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        print(f"  Batch {batch_num}/{total_batches}...", end=" ", flush=True)
        translated = translate_batch(batch)
        hebrew_lines.extend(translated)
        print("✓")

    return [(s, e, he) for (s, e, _), he in zip(captions, hebrew_lines)]


def write_srt(captions, out_path: Path):
    with out_path.open("w", encoding="utf-8") as f:
        for idx, (start, end, text) in enumerate(captions, 1):
            f.write(f"{idx}\n")
            f.write(f"{format_timestamp(start)} --> {format_timestamp(end)}\n")
            f.write(f"{text}\n\n")
    print(f"✓ Wrote {out_path.name}")


def burn_into_video(video_path: Path, srt_path: Path, out_path: Path, font: str):
    """Burn the SRT into the video with libass. Run from the video's folder so
    we can reference both files by basename and avoid path-escape headaches."""
    style = (
        f"FontName={font},"
        "FontSize=22,"
        "PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H00000000,"
        "BorderStyle=1,"
        "Outline=2,"
        "Shadow=0,"
        "Alignment=2,"
        "MarginV=40"
    )
    vf = f"subtitles={srt_path.name}:force_style='{style}'"

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path.name,
        "-vf", vf,
        "-c:a", "copy",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "20",
        out_path.name,
    ]
    print(f"Burning Hebrew captions into video → {out_path.name} ...")
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=video_path.parent)
    if result.returncode != 0:
        tail = "\n".join(result.stderr.splitlines()[-20:])
        raise RuntimeError(f"ffmpeg failed:\n{tail}")
    print(f"✓ Wrote {out_path.name}")


def main():
    parser = argparse.ArgumentParser(description="Add burned-in Hebrew captions to an English video.")
    parser.add_argument("video", help="Path to the English video file")
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        help=f"Whisper model size: tiny | base | small | medium | large (default: {DEFAULT_MODEL})")
    parser.add_argument("--font", default=DEFAULT_FONT,
                        help=f"Hebrew font name for libass (default: '{DEFAULT_FONT}'). "
                             f"On Mac try 'Arial Hebrew'.")
    args = parser.parse_args()

    video_path = Path(args.video).resolve()
    if not video_path.exists():
        sys.exit(f"❌ Video not found: {video_path}")
    if not shutil.which("ffmpeg"):
        sys.exit("❌ ffmpeg not installed. On Mac: `brew install ffmpeg`")
    if not shutil.which("claude"):
        sys.exit("❌ claude CLI not found in PATH.")

    srt_path = video_path.with_name(video_path.stem + "_he.srt")
    out_path = video_path.with_name(video_path.stem + "_he.mp4")

    words = transcribe(video_path, args.model)
    if not words:
        sys.exit("❌ No speech detected in the audio.")

    captions = group_into_captions(words)
    print(f"  → {len(captions)} caption chunks.")

    captions_he = translate_captions(captions)
    write_srt(captions_he, srt_path)
    burn_into_video(video_path, srt_path, out_path, args.font)

    print(f"\n✓ Done!")
    print(f"  Video:     {out_path}")
    print(f"  Subtitles: {srt_path}")


if __name__ == "__main__":
    main()
