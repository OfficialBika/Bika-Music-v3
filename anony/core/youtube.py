# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of AnonXMusic
#
# Production stability patch:
# - Handles missing cookie directory.
# - Avoids None slicing crashes from YouTube search/playlist metadata.
# - Returns the actual downloaded file path from yt-dlp instead of assuming .webm.
# - Runs yt-dlp in a thread and logs failures clearly.

import os
import re
import yt_dlp
import random
import asyncio
import aiohttp
from pathlib import Path

from py_yt import Playlist, VideosSearch

from anony import logger
from anony.helpers import Track, utils


class YouTube:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.cookies = []
        self.checked = False
        self.cookie_dir = "anony/cookies"
        self.warned = False
        self.regex = re.compile(
            r"(https?://)?(www\.|m\.|music\.)?"
            r"(youtube\.com/(watch\?v=|shorts/|playlist\?list=)|youtu\.be/)"
            r"([A-Za-z0-9_-]{11}|PL[A-Za-z0-9_-]+)([&?][^\s]*)?"
        )
        self.iregex = re.compile(
            r"https?://(?:www\.|m\.|music\.)?(?:youtube\.com|youtu\.be)"
            r"(?!/(watch\?v=[A-Za-z0-9_-]{11}|shorts/[A-Za-z0-9_-]{11}"
            r"|playlist\?list=PL[A-Za-z0-9_-]+|[A-Za-z0-9_-]{11}))\S*"
        )

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
            and not p.name.endswith((".part", ".ytdl", ".temp", ".tmp"))
            and p.stat().st_size > 0
        ]

        if not candidates:
            return None

        if video:
            for ext in (".mp4", ".mkv", ".webm", ".mov"):
                for path in candidates:
                    if path.suffix.lower() == ext:
                        return str(path)
        else:
            for ext in (".webm", ".m4a", ".opus", ".mp3", ".aac"):
                for path in candidates:
                    if path.suffix.lower() == ext:
                        return str(path)

        return str(candidates[0])

    def get_cookies(self):
        if not self.checked:
            try:
                os.makedirs(self.cookie_dir, exist_ok=True)
                for file in os.listdir(self.cookie_dir):
                    if file.endswith(".txt"):
                        self.cookies.append(f"{self.cookie_dir}/{file}")
            except Exception as e:
                logger.warning("Failed to read cookies dir: %s", e)
            self.checked = True

        if not self.cookies:
            if not self.warned:
                self.warned = True
                logger.warning("Cookies are missing; downloads might fail.")
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
        logger.info(f"Cookies saved in {self.cookie_dir}.")

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
                track = Track(
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
                tracks.append(track)
        except Exception as e:
            logger.warning("Playlist fetch failed: %s", e)
        return tracks

    async def download(self, video_id: str, video: bool = False) -> str | None:
        if not video_id:
            return None

        os.makedirs("downloads", exist_ok=True)

        existing = self._find_downloaded_file(video_id, video=video)
        if existing:
            return existing

        url = self.base + video_id
        cookie = self.get_cookies()
        base_opts = {
            "outtmpl": "downloads/%(id)s.%(ext)s",
            "quiet": True,
            "noplaylist": True,
            "geo_bypass": True,
            "no_warnings": True,
            "overwrites": False,
            "nocheckcertificate": True,
        }
        if cookie:
            base_opts["cookiefile"] = cookie

        if video:
            ydl_opts = {
                **base_opts,
                "format": "bv*[height<=720][width<=1280]+ba/b[height<=720][width<=1280]/b[height<=720][width<=1280]/best",
                "merge_output_format": "mp4",
            }
        else:
            ydl_opts = {
                **base_opts,
                "format": "ba/bestaudio/best",
            }

        def _download():
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
                return self._find_downloaded_file(video_id, video=video)
            except (yt_dlp.utils.DownloadError, yt_dlp.utils.ExtractorError) as ex:
                logger.warning("Download failed for %s: %s", video_id, ex)
                return None
            except Exception as ex:
                logger.warning("Unexpected download failed for %s: %s", video_id, ex)
                return None

        return await asyncio.to_thread(_download)
