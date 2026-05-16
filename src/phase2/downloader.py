"""
Downloads a YouTube video using yt-dlp.
Saves to videos/{asin}/source.mp4
Skips if file already exists.
"""

import subprocess
from pathlib import Path


def download_video(asin: str, url: str, output_dir: Path, max_duration: int = 180) -> bool:
    """
    Download video to output_dir/{asin}/source.mp4.
    Returns True on success, False on failure.
    max_duration: skip videos longer than this many seconds.
    """
    dest_dir = output_dir / asin
    dest_file = dest_dir / "source.mp4"

    if dest_file.exists():
        print(f"  [download] already exists, skipping")
        return True

    dest_dir.mkdir(parents=True, exist_ok=True)

    # Check duration before downloading
    try:
        dur_result = subprocess.run(
            ["yt-dlp", "--get-duration", "--no-warnings", "--quiet", url],
            capture_output=True, text=True, timeout=20
        )
        duration_str = dur_result.stdout.strip()
        if duration_str:
            seconds = _parse_duration(duration_str)
            if seconds and seconds > max_duration:
                print(f"  [download] skipping — video too long ({duration_str})")
                return False
    except Exception:
        pass

    try:
        result = subprocess.run(
            [
                "yt-dlp",
                "-f", "mp4/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                "--merge-output-format", "mp4",
                "-o", str(dest_file),
                "--no-warnings",
                "--quiet",
                url,
            ],
            timeout=300
        )
        if result.returncode == 0 and dest_file.exists():
            size_mb = dest_file.stat().st_size / 1024 / 1024
            print(f"  [download] saved ({size_mb:.1f} MB)")
            return True
        else:
            print(f"  [download] yt-dlp failed (exit {result.returncode})")
            return False
    except Exception as e:
        print(f"  [download] error: {e}")
        return False


def _parse_duration(s: str) -> int | None:
    """Convert HH:MM:SS or MM:SS to seconds."""
    try:
        parts = s.strip().split(":")
        parts = [int(p) for p in parts]
        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        if len(parts) == 2:
            return parts[0] * 60 + parts[1]
        if len(parts) == 1:
            return parts[0]
    except Exception:
        pass
    return None
