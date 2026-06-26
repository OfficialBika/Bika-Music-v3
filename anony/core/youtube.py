# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of AnonXMusic
#
# Bika-Music-v3 YouTube reliable downloader patch
# - Uses YouTube WEB client only, matching the VPS command that worked:
#   yt-dlp --cookies anony/cookies/cookies.txt --force-ipv4 --extractor-args "youtube:player_client=web"
# - Tries progressive WEB format 18 first because it succeeded on this VPS while audio-only streams returned 403.
# - Falls back to audio-only formats if progressive format is unavailable.
# - Keeps cookie loading, playlist/search safety, actual downloaded file detection, and threaded yt-dlp execution.

import asyncio
import os
import random
import re
from pathlib import Path

import aiohttp
import yt_dlp
from py_yt import Playlist, VideosSearch

from anony import logger
from anony.helpers import Track, utils


class YouTube:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.cookies: list[str] = []
        self.checked = False
        self.cookie_dir = "anony/cookies"
        self.warned = False
        self._patch_logged = False

        # Accept videos, shorts, playlist pages, and watch URLs that include list=.
        self.regex = re.compile(
            r"(https?://)?(www\.|m\.|music\.)?"
            r"(youtube\.com/(watch\?v=|shorts/|playlist\?list=)|youtu\.be/)"
            r"([A-Za-z0-9_-]{11}|[A-Za-z0-9_-]+)([&?][^\s]*)?"
        )
        self.iregex = re.compile(
            r"https?://(?:www\.|m\.|music\.)?(?:youtube\.com|youtu\.be)"
            r"(?!/(watch\?v=[A-Za-z0-9_-]{11}|shorts/[A-Za-z0-9_-]{11}"
            r"|playlist\?list=[A-Za-z0-9_-]+|[A-Za-z0-9_-]{11}))\S*"
        )

    def _log_patch_once(self) -> None:
        if not self._patch_logged:
            self._patch_logged = True
            logger.info("YouTube downloader patch active: web-client, cookies, IPv4, format-18 fallback")

    def _safe_title(self, value, limit: int = 50) -> str:
        return str(value or "Unknown")[:limit]

    def _safe_duration_sec(self, value) -> int:
        try:
            return utils.to_seconds(value or "00:00")
        except Exception:
            return 0

    def _safe_thumb(self, thumbnails) -> str | None:
        try:
            if not thumbnails:
                return None
            return thumbnails[-1].get("url", "").split("?")[0] or None
        except Exception:
            return None

    def _find_downloaded_file(self, video_id: str, video: bool = False) -> str | None:
        downloads = Path("downloads")
        if not downloads.exists():
            return None

        candidates = [
            p for p in downloads.glob(f"{video_id}.*")
            if p.is_file()
            and not p.name.endswith((".part", ".ytdl", ".temp", ".tmp", ".download"))
            and p.stat().st_size > 0
        ]
        if not candidates:
            return None

        if video:
            preferred_exts = (".mp4", ".mkv", ".webm", ".mov")
        else:
            # Format 18 is mp4 with audio+video. PyTgCalls/ffmpeg can still use it for /play audio.
            preferred_exts = (".mp4", ".webm", ".m4a", ".opus", ".mp3", ".aac")

        for ext in preferred_exts:
            for path in candidates:
                if path.suffix.lower() == ext:
                    return str(path)
        return str(candidates[0])

    def _cleanup_partial_files(self, video_id: str) -> None:
        downloads = Path("downloads")
        if not downloads.exists():
            return
        for path in downloads.glob(f"{video_id}.*"):
            if path.name.endswith((".part", ".ytdl", ".temp", ".tmp", ".download")):
                try:
                    path.unlink()
                except Exception:
                    pass

    def get_cookies(self) -> str | None:
        if not self.checked:
            try:
                os.makedirs(self.cookie_dir, exist_ok=True)
                self.cookies = [
                    f"{self.cookie_dir}/{file}"
                    for file in os.listdir(self.cookie_dir)
                    if file.endswith(".txt")
                ]
            except Exception as e:
                logger.warning("Failed to read cookies dir: %s", e)
                self.cookies = []
            self.checked = True

        if not self.cookies:
            if not self.warned:
                self.warned = True
                logger.warning("Cookies are missing; YouTube downloads may fail.")
            return None
        return random.choice(self.cookies)

    async def save_cookies(self, urls: list[str]) -> None:
        logger.info("Saving cookies from urls...")
        os.makedirs(self.cookie_dir, exist_ok=True)
        async with aiohttp.ClientSession() as session:
            for url in urls:
                try:
                    name = url.split("/")[-1]
                    link = "https://batbin.me/raw/" + name
                    async with session.get(link) as resp:
                        resp.raise_for_status()
                        with open(f"{self.cookie_dir}/{name}.txt", "wb") as fw:
                            fw.write(await resp.read())
                except Exception as e:
                    logger.warning("Failed to save cookie from %s: %s", url, e)
        self.checked = False
        self.cookies.clear()
        logger.info("Cookies saved in %s.", self.cookie_dir)

    def valid(self, url: str) -> bool:
        return bool(re.match(self.regex, url or ""))

    def invalid(self, url: str) -> bool:
        return bool(re.match(self.iregex, url or ""))

    async def search(self, query: str, m_id: int, video: bool = False) -> Track | None:
        try:
            _search = VideosSearch(query, limit=1, with_live=False)
            results = await _search.next()
        except Exception as e:
            logger.warning("YouTube search failed for %r: %s", query, e)
            return None

        if results and results.get("result"):
            data = results["result"][0]
            video_id = data.get("id")
            if not video_id:
                return None

            return Track(
                id=video_id,
                channel_name=data.get("channel", {}).get("name"),
                duration=data.get("duration") or "00:00",
                duration_sec=self._safe_duration_sec(data.get("duration")),
                message_id=m_id,
                title=self._safe_title(data.get("title"), 50),
                thumbnail=self._safe_thumb(data.get("thumbnails", [])),
                url=data.get("link") or f"{self.base}{video_id}",
                view_count=data.get("viewCount", {}).get("short"),
                video=video,
            )
        return None

    async def playlist(self, limit: int, user: str, url: str, video: bool) -> list[Track | None]:
        tracks = []
        try:
            plist = await Playlist.get(url)
            videos = plist.get("videos", [])
            for data in videos[:limit]:
                video_id = data.get("id")
                if not video_id:
                    continue

                link = data.get("link") or f"{self.base}{video_id}"
                tracks.append(
                    Track(
                        id=video_id,
                        channel_name=data.get("channel", {}).get("name", ""),
                        duration=data.get("duration") or "00:00",
                        duration_sec=self._safe_duration_sec(data.get("duration")),
                        title=self._safe_title(data.get("title"), 50),
                        thumbnail=self._safe_thumb(data.get("thumbnails", [])),
                        url=link.split("&list=")[0],
                        user=user,
                        view_count="",
                        video=video,
                    )
                )
        except Exception as e:
            logger.warning("Playlist fetch failed for %s: %s", url, e)
        return tracks

    def _base_ydl_opts(self, cookie: str | None, fmt: str, video: bool) -> dict:
        opts = {
            "outtmpl": "downloads/%(id)s.%(ext)s",
            "format": fmt,
            "quiet": True,
            "noplaylist": True,
            "geo_bypass": True,
            "no_warnings": True,
            "overwrites": False,
            "nocheckcertificate": True,
            # This is the Python equivalent of the working CLI --force-ipv4.
            "source_address": "0.0.0.0",
            "retries": 3,
            "fragment_retries": 3,
            "extractor_retries": 3,
            "extractor_args": {
                "youtube": {
                    # Android/iOS skipped cookies on your VPS; web client worked.
                    "player_client": ["web"],
                }
            },
        }
        if cookie:
            opts["cookiefile"] = cookie
        if video:
            opts["merge_output_format"] = "mp4"
        return opts

    async def download(self, video_id: str, video: bool = False) -> str | None:
        if not video_id:
            return None

        self._log_patch_once()
        os.makedirs("downloads", exist_ok=True)

        existing = self._find_downloaded_file(video_id, video=video)
        if existing:
            return existing

        url = self.base + video_id
        cookie = self.get_cookies()

        # Try format 18 first because your VPS direct test succeeded by downloading format 18.
        # If 18 is unavailable, fall back to audio-only / best formats.
        if video:
            formats_to_try = [
                "18",
                "22",
                "18/22/b[height<=720][width<=1280]/best[height<=720]/best",
                "best",
            ]
        else:
            formats_to_try = [
                "18",
                "251/140/ba/bestaudio/best",
                "ba/bestaudio/best",
                "best",
            ]

        def _download_with_fallbacks() -> str | None:
            last_error = None
            for fmt in formats_to_try:
                self._cleanup_partial_files(video_id)
                opts = self._base_ydl_opts(cookie, fmt, video=video)
                try:
                    logger.info("Downloading YouTube %s with web client format=%s", video_id, fmt)
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        ydl.download([url])
                    found = self._find_downloaded_file(video_id, video=video)
                    if found:
                        return found
                except (yt_dlp.utils.DownloadError, yt_dlp.utils.ExtractorError) as ex:
                    last_error = ex
                    logger.warning("Download attempt failed for %s format=%s: %s", video_id, fmt, ex)
                except Exception as ex:
                    last_error = ex
                    logger.warning("Unexpected download attempt failed for %s format=%s: %s", video_id, fmt, ex)

            if last_error:
                logger.warning("All YouTube download attempts failed for %s: %s", video_id, last_error)
            return None

        return await asyncio.to_thread(_download_with_fallbacks)
