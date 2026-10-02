"""Background cleanup for downloaded media and transient cache files."""
from __future__ import annotations
import time
from pathlib import Path

DOWNLOAD_DIR = Path("downloads")
CACHE_DIR = Path("cache")
MEDIA_MAX_AGE = 24 * 60 * 60
PARTIAL_MAX_AGE = 2 * 60 * 60
THUMB_MAX_AGE = 7 * 24 * 60 * 60
MEDIA_EXTENSIONS = {".mp4", ".mkv", ".webm", ".mov", ".mp3", ".m4a", ".opus", ".aac", ".flac", ".ogg", ".wav", ".ts", ".flv"}
PARTIAL_SUFFIXES = (".part", ".ytdl", ".temp", ".tmp", ".download")

def _cleanup_dir(directory: Path, max_age: int, *, extensions=None, suffixes=()):
    if not directory.exists():
        return 0
    now = time.time()
    deleted = 0
    for path in directory.iterdir():
        if not path.is_file():
            continue
        name = path.name.lower()
        if extensions is not None and path.suffix.lower() not in extensions:
            continue
        if suffixes and not name.endswith(suffixes):
            continue
        try:
            if now - path.stat().st_mtime <= max_age:
                continue
            path.unlink()
            deleted += 1
        except OSError:
            continue
    return deleted

async def cleanup_downloads():
    deleted_media = _cleanup_dir(DOWNLOAD_DIR, MEDIA_MAX_AGE, extensions=MEDIA_EXTENSIONS)
    deleted_partial = _cleanup_dir(DOWNLOAD_DIR, PARTIAL_MAX_AGE, suffixes=PARTIAL_SUFFIXES)
    deleted_cache = _cleanup_dir(CACHE_DIR, THUMB_MAX_AGE, extensions={".png", ".jpg", ".jpeg", ".webp"})
    return deleted_media + deleted_partial + deleted_cache
