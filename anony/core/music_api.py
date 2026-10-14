from __future__ import annotations

import asyncio
from typing import Any

import aiohttp


class MusicAPIClient:
    """Client for the authorized local audio library exposed by Bika Music API."""

    def __init__(self, base_url: str | None, api_key: str | None, logger):
        self.base_url = (base_url or "").strip().rstrip("/")
        self.api_key = (api_key or "").strip()
        self.logger = logger

    @property
    def enabled(self) -> bool:
        return bool(self.base_url and self.api_key)

    async def search_library(self, query: str, limit: int = 1) -> list[dict[str, Any]]:
        if not self.enabled or not query.strip():
            return []

        timeout = aiohttp.ClientTimeout(total=6, connect=2)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(
                    f"{self.base_url}/api/v1/library/search",
                    params={"q": query[:200], "limit": max(1, min(5, int(limit)))},
                    headers={"X-API-Key": self.api_key},
                ) as response:
                    if response.status != 200:
                        self.logger.warning(
                            "Music API library search returned HTTP %s", response.status
                        )
                        return []
                    payload = await response.json()
                    items = payload.get("results", [])
                    return [
                        item
                        for item in items
                        if isinstance(item, dict)
                        and item.get("playable") is True
                        and item.get("id")
                        and item.get("source_url")
                        and int(item.get("duration_seconds") or 0) > 0
                    ][: max(1, min(5, int(limit)))]
        except asyncio.CancelledError:
            raise
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, TypeError) as error:
            self.logger.warning(
                "Music API library search failed (%s)", type(error).__name__
            )
            return []
