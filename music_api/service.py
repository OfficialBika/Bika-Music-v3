from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import mimetypes
import os
import re
import shutil
import subprocess
import time
import unicodedata
from pathlib import Path
from urllib.parse import urlencode

import aiohttp
from aiohttp import web
from dotenv import load_dotenv

load_dotenv()
LOG = logging.getLogger("bika.music_api")
AUDIO_EXTENSIONS = {".aac", ".aif", ".aiff", ".alac", ".flac", ".m4a", ".mp3", ".oga", ".ogg", ".opus", ".wav", ".weba", ".webm"}
VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
TRACK_ID_RE = re.compile(r"^[a-f0-9]{24}$")
MAX_TTL = 7 * 24 * 60 * 60
YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"


def normalise_query(value: str) -> str:
    value = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return " ".join("".join(c if c.isalnum() else " " for c in value).split())


def track_id_for(path: Path, root: Path) -> str:
    relative = path.resolve().relative_to(root.resolve()).as_posix()
    return hashlib.sha256(relative.encode("utf-8")).hexdigest()[:24]


def sign_source(track_id: str, expires: int, secret: str) -> str:
    payload = f"{track_id}:{int(expires)}".encode()
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def verify_source_signature(track_id: str, expires: str, signature: str, secret: str, now: int | None = None) -> bool:
    if not TRACK_ID_RE.fullmatch(track_id or "") or not signature:
        return False
    try:
        expiry = int(expires)
    except (TypeError, ValueError):
        return False
    current = int(time.time()) if now is None else int(now)
    if expiry <= current or expiry > current + MAX_TTL:
        return False
    return hmac.compare_digest(sign_source(track_id, expiry, secret), signature)


def scan_audio_files(root: Path) -> list[Path]:
    root = root.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    result = []
    for path in root.rglob("*"):
        try:
            if path.is_symlink() or not path.is_file():
                continue
            resolved = path.resolve(strict=True)
            resolved.relative_to(root)
            if resolved.suffix.lower() in AUDIO_EXTENSIONS:
                result.append(resolved)
        except (OSError, RuntimeError, ValueError):
            continue
    return sorted(result, key=lambda p: p.relative_to(root).as_posix().casefold())


class MusicAPI:
    def __init__(self):
        self.youtube_key = os.getenv("YOUTUBE_API_KEY", "").strip()
        self.api_key = os.getenv("MUSIC_API_KEY", "").strip()
        self.signing_secret = os.getenv("MUSIC_API_SIGNING_SECRET", "").strip()
        self.audio_root = Path(os.getenv("MUSIC_API_AUDIO_DIR", "./authorized_audio")).expanduser().resolve()
        self.host = os.getenv("MUSIC_API_HOST", "127.0.0.1").strip() or "127.0.0.1"
        try:
            self.port = min(65535, max(1, int(os.getenv("MUSIC_API_PORT", "8765"))))
        except ValueError:
            self.port = 8765
        self.base_url = (os.getenv("MUSIC_API_PUBLIC_BASE_URL", "").strip().rstrip("/") or f"http://127.0.0.1:{self.port}")
        try:
            self.stream_ttl = min(MAX_TTL, max(300, int(os.getenv("MUSIC_API_STREAM_TTL", "86400"))))
        except ValueError:
            self.stream_ttl = 86400
        self._duration_cache: dict[tuple[str, int, int], int] = {}
        self._youtube_semaphore = asyncio.Semaphore(4)
        self._search_cache: dict[str, tuple[float, list[dict]]] = {}

    def validate(self) -> None:
        if len(self.api_key) < 32:
            raise RuntimeError("Set MUSIC_API_KEY to a random secret of at least 32 characters.")
        if len(self.signing_secret) < 32:
            raise RuntimeError("Set MUSIC_API_SIGNING_SECRET to a different random secret of at least 32 characters.")
        if not self.base_url.startswith(("http://", "https://")):
            raise RuntimeError("MUSIC_API_PUBLIC_BASE_URL must use http:// or https://.")

    def _duration(self, path: Path) -> int:
        try:
            stat = path.stat()
        except OSError:
            return 0
        key = (str(path), stat.st_mtime_ns, stat.st_size)
        if key in self._duration_cache:
            return self._duration_cache[key]
        ffprobe = shutil.which("ffprobe")
        if not ffprobe:
            return 0
        try:
            result = subprocess.run(
                [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
                capture_output=True, text=True, check=True, timeout=4,
            )
            duration = max(0, int(float(result.stdout.strip())))
        except (OSError, subprocess.SubprocessError, ValueError):
            duration = 0
        self._duration_cache[key] = duration
        if len(self._duration_cache) > 2048:
            self._duration_cache.clear()
        return duration

    @staticmethod
    def _format_duration(seconds: int) -> str:
        hours, rest = divmod(max(0, seconds), 3600)
        minutes, seconds = divmod(rest, 60)
        return f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes:02d}:{seconds:02d}"

    def _source_url(self, track_id: str) -> str:
        expires = int(time.time()) + self.stream_ttl
        sig = sign_source(track_id, expires, self.signing_secret)
        return f"{self.base_url}/api/v1/library/{track_id}/stream?{urlencode({'expires': expires, 'sig': sig})}"

    def _file_for_id(self, track_id: str) -> Path | None:
        if not TRACK_ID_RE.fullmatch(track_id or ""):
            return None
        for path in scan_audio_files(self.audio_root):
            if hmac.compare_digest(track_id_for(path, self.audio_root), track_id):
                return path
        return None

    async def search_library(self, query: str, limit: int) -> list[dict]:
        needle = normalise_query(query)
        if not needle:
            return []
        cache_key = f"{needle}:{limit}"
        cached = self._search_cache.get(cache_key)
        if cached and cached[0] > time.monotonic():
            return cached[1]

        def find() -> list[Path]:
            matches = []
            for path in scan_audio_files(self.audio_root):
                title = normalise_query(path.stem.replace("_", " "))
                if not title:
                    continue
                if title == needle:
                    score = 0
                elif title.startswith(needle):
                    score = 1
                elif any(word.startswith(needle) for word in title.split()):
                    score = 2
                elif needle in title:
                    score = 3
                else:
                    continue
                matches.append((score, title, path))
            matches.sort(key=lambda item: (item[0], item[1]))
            return [item[2] for item in matches[:limit]]

        paths = await asyncio.to_thread(find)

        def serialize(path: Path) -> dict:
            seconds = self._duration(path)
            ident = track_id_for(path, self.audio_root)
            return {
                "id": ident,
                "title": path.stem.replace("_", " "),
                "duration": self._format_duration(seconds),
                "duration_seconds": seconds,
                "source": "authorized_library",
                "source_url": self._source_url(ident),
                "playable": seconds > 0,
            }

        results = await asyncio.gather(*(asyncio.to_thread(serialize, p) for p in paths))
        self._search_cache[cache_key] = (time.monotonic() + 15, results)
        if len(self._search_cache) > 512:
            self._search_cache.clear()
        return results

    async def search_youtube(self, query: str, limit: int) -> list[dict]:
        if not self.youtube_key:
            raise web.HTTPServiceUnavailable(text="YOUTUBE_API_KEY is not configured.")
        cache_key = f"yt:{normalise_query(query)}:{limit}"
        cached = self._search_cache.get(cache_key)
        if cached and cached[0] > time.monotonic():
            return cached[1]

        try:
            async with self._youtube_semaphore:
                timeout = aiohttp.ClientTimeout(total=10)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(
                        YOUTUBE_SEARCH_URL,
                        params={"part": "snippet", "type": "video", "maxResults": limit, "q": query, "key": self.youtube_key},
                    ) as response:
                        if response.status != 200:
                            LOG.warning("YouTube Data API returned HTTP %s", response.status)
                            raise web.HTTPBadGateway(text="YouTube search is temporarily unavailable; check API quota and key configuration.")
                        payload = await response.json()
        except (aiohttp.ClientError, asyncio.TimeoutError):
            raise web.HTTPBadGateway(text="YouTube search is temporarily unavailable.") from None

        results = []
        for item in payload.get("items", []):
            video_id = (item.get("id") or {}).get("videoId")
            snippet = item.get("snippet") or {}
            if not video_id or not VIDEO_ID_RE.fullmatch(video_id):
                continue
            thumbs = snippet.get("thumbnails") or {}
            thumb = (thumbs.get("high") or thumbs.get("medium") or thumbs.get("default") or {}).get("url")
            results.append({
                "video_id": video_id,
                "title": str(snippet.get("title") or "Unknown")[:200],
                "channel": str(snippet.get("channelTitle") or "")[:200],
                "published_at": snippet.get("publishedAt"),
                "thumbnail": thumb,
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "playable_in_voice_chat": False,
                "note": "Metadata and watch link only; the official API does not provide audio streams.",
            })
        self._search_cache[cache_key] = (time.monotonic() + 600, results)
        if len(self._search_cache) > 512:
            self._search_cache.clear()
        return results


@web.middleware
async def auth_middleware(request: web.Request, handler):
    if request.path == "/healthz":
        return await handler(request)
    if request.path.startswith("/api/v1/library/") and request.path.endswith("/stream"):
        return await handler(request)
    api: MusicAPI = request.app["music_api"]
    supplied = request.headers.get("X-API-Key", "")
    if not api.api_key or not hmac.compare_digest(api.api_key, supplied):
        return web.json_response({"error": "unauthorized"}, status=401)
    return await handler(request)


def parse_query(request: web.Request, max_limit: int = 10) -> tuple[str, int]:
    query = request.query.get("q", "").strip()
    if not query or len(query) > 200:
        raise web.HTTPBadRequest(text="q is required and must be at most 200 characters.")
    try:
        limit = int(request.query.get("limit", "5"))
    except ValueError:
        raise web.HTTPBadRequest(text="limit must be an integer.") from None
    if not 1 <= limit <= max_limit:
        raise web.HTTPBadRequest(text=f"limit must be between 1 and {max_limit}.")
    return query, limit


async def health(request: web.Request) -> web.Response:
    api: MusicAPI = request.app["music_api"]
    return web.json_response({"status": "ok", "service": "bika-music-api", "youtube_search_configured": bool(api.youtube_key)})


async def youtube_search(request: web.Request) -> web.Response:
    query, limit = parse_query(request)
    results = await request.app["music_api"].search_youtube(query, limit)
    return web.json_response({"query": query, "count": len(results), "results": results})


async def library_search(request: web.Request) -> web.Response:
    query, limit = parse_query(request)
    results = await request.app["music_api"].search_library(query, limit)
    return web.json_response({"query": query, "count": len(results), "results": results})


async def stream_item(request: web.Request) -> web.StreamResponse:
    api: MusicAPI = request.app["music_api"]
    track_id = request.match_info.get("track_id", "")
    expires = request.query.get("expires", "")
    signature = request.query.get("sig", "")
    if not verify_source_signature(track_id, expires, signature, api.signing_secret):
        return web.json_response({"error": "invalid_or_expired_stream_signature"}, status=403)
    path = await asyncio.to_thread(api._file_for_id, track_id)
    if path is None:
        return web.json_response({"error": "track_not_found"}, status=404)
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return web.FileResponse(path, headers={"Content-Type": content_type, "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


def create_app(api: MusicAPI | None = None) -> web.Application:
    instance = api or MusicAPI()
    app = web.Application(middlewares=[auth_middleware], client_max_size=1024 * 1024)
    app["music_api"] = instance
    app.router.add_get("/healthz", health)
    app.router.add_get("/api/v1/youtube/search", youtube_search)
    app.router.add_get("/api/v1/library/search", library_search)
    app.router.add_get("/api/v1/library/{track_id}/stream", stream_item)
    return app


def main() -> None:
    logging.basicConfig(level=os.getenv("MUSIC_API_LOG_LEVEL", "INFO").upper(), format="[%(asctime)s] %(levelname)s %(name)s: %(message)s")
    api = MusicAPI()
    api.validate()
    api.audio_root.mkdir(parents=True, exist_ok=True)
    LOG.info("Starting Bika Music API on %s:%s", api.host, api.port)
    web.run_app(create_app(api), host=api.host, port=api.port, access_log=None)


if __name__ == "__main__":
    main()
