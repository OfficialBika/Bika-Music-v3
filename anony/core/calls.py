# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of AnonXMusic
#
# Production stability patch:
# - play_media now returns bool instead of silently failing.
# - Telegram/ntgcalls temporary errors are retried before stopping the call.
# - stop/replay/play_next are guarded against stale DB call state and empty queue.
# - raw Bot API edits are moved to asyncio.to_thread to avoid blocking the event loop.
# - background update exceptions are logged instead of killing handlers.
# - Optional per-chat auto-delete for old Now Playing posts after 10 seconds.

import asyncio
import html
import os
from pathlib import Path
from typing import Any

from ntgcalls import (
    ConnectionNotFound,
    RTMPStreamingUnsupported,
    TelegramServerError,
)
from pyrogram.errors import (
    ChatSendMediaForbidden,
    ChatSendPhotosForbidden,
    MessageIdInvalid,
    MessageNotModified,
    FloodWait,
)
from pyrogram.types import InputMediaPhoto, Message
from pytgcalls import PyTgCalls, exceptions, types
from pytgcalls.pytgcalls_session import PyTgCallsSession

from anony import app, config, db, lang, logger, queue, thumb, userbot, yt
from anony.helpers import Media, Track, buttons, rawtg


TG_RETRY_ERRORS = (
    ConnectionError,
    ConnectionNotFound,
    TelegramServerError,
)


async def _safe_edit_text(message: Message, text: str, **kwargs: Any) -> bool:
    try:
        await message.edit_text(text, **kwargs)
        return True
    except MessageNotModified:
        return True
    except FloodWait as e:
        await asyncio.sleep(int(getattr(e, "value", 1)) + 1)
        try:
            await message.edit_text(text, **kwargs)
            return True
        except Exception:
            return False
    except Exception:
        try:
            await app.send_message(message.chat.id, text, **kwargs)
            return True
        except Exception:
            return False


async def _safe_delete_message(chat_id: int, message_id: int | None) -> None:
    if not message_id:
        return
    try:
        await app.delete_messages(chat_id=chat_id, message_ids=message_id, revoke=True)
    except Exception:
        pass


async def _auto_delete_old_play_message(chat_id: int, message_id: int | None, delay: int = 10) -> None:
    """Delete an old Now Playing post after a delay when the group setting is enabled."""
    if not message_id:
        return

    try:
        enabled = await db.get_auto_delete_play(chat_id)
    except Exception as e:
        logger.warning("auto-delete setting check failed chat=%s: %s", chat_id, e)
        return

    if not enabled:
        return

    async def _runner() -> None:
        try:
            await asyncio.sleep(max(0, int(delay or 10)))
            await _safe_delete_message(chat_id, message_id)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning("auto-delete old play post failed chat=%s msg=%s: %s", chat_id, message_id, e)

    asyncio.create_task(_runner())


async def _mark_old_play_post_finished(chat_id: int, media: Media | Track | None) -> None:
    """Mark the old Now Playing post as ended and optionally delete it after 10 seconds."""
    message_id = getattr(media, "message_id", 0) if media else 0
    if not message_id:
        return

    try:
        _lang = await lang.get_lang(chat_id)
        await _raw_edit_reply_markup(
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=buttons.controls(
                chat_id=chat_id,
                status=_lang.get("stopped", "Stream ended"),
                remove=True,
            ),
        )
    except Exception:
        pass

    await _auto_delete_old_play_message(chat_id, message_id, delay=10)


async def _raw_edit_reply_markup(chat_id: int, message_id: int, reply_markup=None) -> None:
    try:
        await asyncio.to_thread(
            rawtg.edit_message_reply_markup,
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=reply_markup,
        )
    except Exception:
        pass


async def _raw_edit_now_playing(
    chat_id: int,
    message_id: int,
    text: str,
    reply_markup,
    is_caption: bool,
) -> None:
    try:
        if is_caption:
            await asyncio.to_thread(
                rawtg.edit_message_caption,
                chat_id=chat_id,
                message_id=message_id,
                caption=text,
                reply_markup=reply_markup,
                parse_mode="HTML",
            )
        else:
            await asyncio.to_thread(
                rawtg.edit_message_text,
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
    except Exception:
        pass


def build_now_playing_caption(media: Media | Track, _lang: dict) -> str:
    song_link = html.escape(getattr(media, "url", "") or "https://t.me/Official_Bika")
    song_title = html.escape(getattr(media, "title", "") or "Unknown")
    duration = html.escape(str(getattr(media, "duration", "") or "Unknown"))
    requester = str(getattr(media, "user", "") or "User")

    return (
        f'<b><tg-emoji emoji-id="5361979846845014099">💃</tg-emoji> | {html.escape(_lang["np_started"])}</b>\n\n'
        f'<b><tg-emoji emoji-id="5217933090483098080">🎵</tg-emoji> {html.escape(_lang["np_song"])}</b> : '
        f'<a href="{song_link}">{song_title}</a>\n\n'
        f'<b><tg-emoji emoji-id="5780543148782522693">🕒</tg-emoji> {html.escape(_lang["np_duration"])}</b>: {duration}\n\n'
        f'<b><tg-emoji emoji-id="6228686680761569664">💅</tg-emoji> {html.escape(_lang["np_requester"])}</b>: {requester}'
    )


class TgCall(PyTgCalls):
    def __init__(self):
        self.clients = []

    async def pause(self, chat_id: int) -> bool:
        try:
            client = await db.get_assistant(chat_id)
            await client.pause(chat_id)
            await db.playing(chat_id, paused=True)
            return True
        except Exception as e:
            logger.warning("pause failed chat=%s: %s", chat_id, e)
            return False

    async def resume(self, chat_id: int) -> bool:
        try:
            client = await db.get_assistant(chat_id)
            await client.resume(chat_id)
            await db.playing(chat_id, paused=False)
            return True
        except Exception as e:
            logger.warning("resume failed chat=%s: %s", chat_id, e)
            return False

    async def stop(self, chat_id: int) -> None:
        # Clear local state first so stale DB state cannot keep commands stuck.
        queue.clear(chat_id)
        await db.remove_call(chat_id)
        await db.set_loop(chat_id, 0)

        try:
            client = await db.get_assistant(chat_id)
            await client.leave_call(chat_id, close=False)
        except Exception:
            pass

    async def _build_stream(self, media: Media | Track, seek_time: int = 0):
        seek_time = max(0, int(seek_time or 0))
        ffmpeg_parameters = f"-ss {seek_time}" if seek_time > 1 else None

        return types.MediaStream(
            media_path=media.file_path,
            audio_parameters=types.AudioQuality.HIGH,
            video_parameters=types.VideoQuality.HD_720p,
            audio_flags=types.MediaStream.Flags.REQUIRED,
            video_flags=(
                types.MediaStream.Flags.AUTO_DETECT
                if getattr(media, "video", False)
                else types.MediaStream.Flags.IGNORE
            ),
            ffmpeg_parameters=ffmpeg_parameters,
        )

    async def play_media(
        self,
        chat_id: int,
        message: Message,
        media: Media | Track,
        seek_time: int = 0,
    ) -> bool:
        _lang = await lang.get_lang(chat_id)

        if not media:
            await db.remove_call(chat_id)
            await _safe_edit_text(message, _lang["not_playing"])
            return False

        if not getattr(media, "file_path", None):
            await _safe_edit_text(
                message,
                _lang["error_no_file"].format(config.SUPPORT_CHAT),
            )
            if not seek_time:
                await self.play_next(chat_id)
            return False

        # If yt-dlp returned a stale path, try to recover by locating the actual file.
        media_path = str(media.file_path)
        if not (
            media_path.startswith(("http://", "https://", "rtmp://", "rtmps://"))
            or Path(media_path).exists()
        ):
            matches = [
                p for p in Path("downloads").glob(f"{getattr(media, 'id', '')}.*")
                if not p.name.endswith((".part", ".ytdl", ".temp", ".tmp"))
            ]
            if matches:
                media.file_path = str(matches[0])
            else:
                await _safe_edit_text(
                    message,
                    _lang["error_no_file"].format(config.SUPPORT_CHAT),
                )
                if not seek_time:
                    await self.play_next(chat_id)
                return False

        try:
            client = await db.get_assistant(chat_id)
        except Exception as e:
            logger.exception("Failed to get assistant for chat=%s: %s", chat_id, e)
            await _safe_edit_text(message, _lang["error_tg_server"])
            await db.remove_call(chat_id)
            return False

        try:
            stream = await self._build_stream(media, seek_time)
        except Exception as e:
            logger.exception("Failed to build MediaStream chat=%s: %s", chat_id, e)
            await _safe_edit_text(message, _lang["error_no_file"].format(config.SUPPORT_CHAT))
            if not seek_time:
                await self.play_next(chat_id)
            return False

        # Retry temporary Telegram/ntgcalls server errors. Do not clear queue on first hiccup.
        for attempt in range(3):
            try:
                await client.play(
                    chat_id=chat_id,
                    stream=stream,
                    config=types.GroupCallConfig(auto_start=False),
                )
                break
            except TG_RETRY_ERRORS as e:
                logger.warning(
                    "Telegram call play retry chat=%s attempt=%s error=%s",
                    chat_id,
                    attempt + 1,
                    e,
                )
                if attempt == 2:
                    await self.stop(chat_id)
                    await _safe_edit_text(message, _lang["error_tg_server"])
                    return False
                await asyncio.sleep(2 + attempt)
            except FileNotFoundError:
                await _safe_edit_text(
                    message,
                    _lang["error_no_file"].format(config.SUPPORT_CHAT),
                )
                if not seek_time:
                    await self.play_next(chat_id)
                return False
            except exceptions.NoActiveGroupCall:
                await self.stop(chat_id)
                await _safe_edit_text(message, _lang["error_no_call"])
                return False
            except exceptions.NoAudioSourceFound:
                await _safe_edit_text(message, _lang["error_no_audio"])
                if not seek_time:
                    await self.play_next(chat_id)
                return False
            except RTMPStreamingUnsupported:
                await self.stop(chat_id)
                await _safe_edit_text(message, _lang["error_rtmp"])
                return False
            except Exception as e:
                logger.exception("Unhandled play_media error chat=%s: %s", chat_id, e)
                await _safe_edit_text(message, _lang["error_tg_server"])
                if not seek_time:
                    await self.play_next(chat_id)
                return False

        if seek_time:
            return True

        media.time = 1
        await db.add_call(chat_id)

        try:
            _thumb = (
                await thumb.generate(media)
                if isinstance(media, Track)
                else config.DEFAULT_THUMB
            ) if config.THUMB_GEN else None
        except Exception as e:
            logger.warning("Thumbnail generation failed chat=%s: %s", chat_id, e)
            _thumb = None

        text = build_now_playing_caption(media, _lang)
        keyboard = buttons.controls(chat_id)

        try:
            if _thumb:
                await message.edit_media(
                    media=InputMediaPhoto(
                        media=_thumb,
                        caption=text,
                    ),
                    reply_markup=keyboard,
                )
                sent = message
                is_caption = True
            else:
                await message.edit_text(
                    text=text,
                    reply_markup=keyboard,
                    disable_web_page_preview=True,
                )
                sent = message
                is_caption = False
        except (
            ChatSendMediaForbidden,
            ChatSendPhotosForbidden,
            MessageIdInvalid,
            MessageNotModified,
        ):
            try:
                if _thumb:
                    sent = await app.send_photo(
                        chat_id=chat_id,
                        photo=_thumb,
                        caption=text,
                        reply_markup=keyboard,
                    )
                    is_caption = True
                else:
                    sent = await app.send_message(
                        chat_id=chat_id,
                        text=text,
                        reply_markup=keyboard,
                        disable_web_page_preview=True,
                    )
                    is_caption = False
            except Exception as e:
                logger.warning("Failed to send now-playing message chat=%s: %s", chat_id, e)
                sent = message
                is_caption = bool(_thumb)
        except Exception as e:
            logger.warning("Failed to edit now-playing message chat=%s: %s", chat_id, e)
            sent = message
            is_caption = bool(_thumb)

        media.message_id = getattr(sent, "id", getattr(message, "id", 0)) or 0

        if media.message_id:
            await _raw_edit_now_playing(
                chat_id=chat_id,
                message_id=media.message_id,
                text=text,
                reply_markup=buttons.controls(chat_id),
                is_caption=is_caption,
            )

        return True

    async def replay(self, chat_id: int) -> None:
        if not await db.get_call(chat_id):
            return

        media = queue.get_current(chat_id)
        if not media:
            await self.stop(chat_id)
            return

        _lang = await lang.get_lang(chat_id)
        msg = await app.send_message(
            chat_id=chat_id,
            text=_lang["play_again"],
        )
        media.message_id = msg.id
        await self.play_media(chat_id, msg, media)

    async def play_next(self, chat_id: int, _attempt: int = 0) -> None:
        if _attempt > max(3, int(getattr(config, "QUEUE_LIMIT", 25))):
            logger.warning("play_next aborting after too many failures chat=%s", chat_id)
            return await self.stop(chat_id)

        if loop := await db.get_loop(chat_id):
            await db.set_loop(chat_id, loop - 1)
            return await self.replay(chat_id)

        current = queue.get_current(chat_id)
        media = queue.get_next(chat_id)

        if not media:
            await _mark_old_play_post_finished(chat_id, current)
            return await self.stop(chat_id)

        # Keep the old Now Playing post visible briefly, then remove it only when
        # Auto Delete Old Posts is enabled for this chat.
        await _mark_old_play_post_finished(chat_id, current)

        _lang = await lang.get_lang(chat_id)
        msg = await app.send_message(
            chat_id=chat_id,
            text=_lang["play_next"],
        )

        if not getattr(media, "file_path", None):
            try:
                media.file_path = await yt.download(media.id, video=media.video)
            except Exception as e:
                logger.warning("Next track download failed chat=%s id=%s: %s", chat_id, media.id, e)
                media.file_path = None

            if not media.file_path:
                await msg.edit_text(_lang["error_no_file"].format(config.SUPPORT_CHAT))
                return await self.play_next(chat_id, _attempt + 1)

        media.message_id = msg.id
        ok = await self.play_media(chat_id, msg, media)
        if not ok:
            return await self.play_next(chat_id, _attempt + 1)

    async def volume(self, chat_id: int, volume: int) -> bool:
        try:
            client = await db.get_assistant(chat_id)
            await client.change_volume_call(chat_id, volume)
            return True
        except Exception:
            return False

    async def ping(self) -> float:
        if not self.clients:
            return 0.0
        pings = [getattr(client, "ping", 0) for client in self.clients]
        return round(sum(pings) / len(pings), 2)

    async def decorators(self, client: PyTgCalls) -> None:
        @client.on_update()
        async def update_handler(_, update: types.Update) -> None:
            try:
                if isinstance(update, types.StreamEnded):
                    if update.stream_type == types.StreamEnded.Type.AUDIO:
                        await self.play_next(update.chat_id)
                elif isinstance(update, types.ChatUpdate):
                    if update.status in [
                        types.ChatUpdate.Status.KICKED,
                        types.ChatUpdate.Status.LEFT_GROUP,
                        types.ChatUpdate.Status.CLOSED_VOICE_CHAT,
                    ]:
                        await self.stop(update.chat_id)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.exception("PyTgCalls update handler failed: %s", e)

    async def boot(self) -> None:
        PyTgCallsSession.notice_displayed = True
        for ub in userbot.clients:
            try:
                client = PyTgCalls(ub, cache_duration=100)
                await client.start()
                self.clients.append(client)
                await self.decorators(client)
            except Exception as e:
                logger.exception("Failed to start PyTgCalls client: %s", e)

        if not self.clients:
            raise SystemExit("No PyTgCalls clients started. Check SESSION variables.")

        logger.info("PyTgCalls client(s) started.")
