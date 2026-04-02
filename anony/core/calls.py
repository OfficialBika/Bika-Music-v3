# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of AnonXMusic

import html

from ntgcalls import (
    ConnectionNotFound,
    RTMPStreamingUnsupported,
    TelegramServerError,
)
from pyrogram.errors import (
    ChatSendMediaForbidden,
    ChatSendPhotosForbidden,
    MessageIdInvalid,
)
from pyrogram.types import InputMediaPhoto, Message
from pytgcalls import PyTgCalls, exceptions, types
from pytgcalls.pytgcalls_session import PyTgCallsSession

from anony import app, config, db, lang, logger, queue, thumb, userbot, yt
from anony.helpers import Media, Track, buttons, rawtg


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
        client = await db.get_assistant(chat_id)
        await db.playing(chat_id, paused=True)
        return await client.pause(chat_id)

    async def resume(self, chat_id: int) -> bool:
        client = await db.get_assistant(chat_id)
        await db.playing(chat_id, paused=False)
        return await client.resume(chat_id)

    async def stop(self, chat_id: int) -> None:
        client = await db.get_assistant(chat_id)
        queue.clear(chat_id)
        await db.remove_call(chat_id)
        await db.set_loop(chat_id, 0)

        try:
            await client.leave_call(chat_id, close=False)
        except Exception:
            pass

    async def play_media(
        self,
        chat_id: int,
        message: Message,
        media: Media | Track,
        seek_time: int = 0,
    ) -> None:
        client = await db.get_assistant(chat_id)
        _lang = await lang.get_lang(chat_id)

        _thumb = (
            await thumb.generate(media)
            if isinstance(media, Track)
            else config.DEFAULT_THUMB
        ) if config.THUMB_GEN else None

        if not media.file_path:
            await message.edit_text(
                _lang["error_no_file"].format(config.SUPPORT_CHAT)
            )
            return await self.play_next(chat_id)

        stream = types.MediaStream(
            media_path=media.file_path,
            audio_parameters=types.AudioQuality.HIGH,
            video_parameters=types.VideoQuality.HD_720p,
            audio_flags=types.MediaStream.Flags.REQUIRED,
            video_flags=(
                types.MediaStream.Flags.AUTO_DETECT
                if media.video
                else types.MediaStream.Flags.IGNORE
            ),
            ffmpeg_parameters=f"-ss {seek_time}" if seek_time > 1 else None,
        )

        try:
            await client.play(
                chat_id=chat_id,
                stream=stream,
                config=types.GroupCallConfig(auto_start=False),
            )

            if not seek_time:
                media.time = 1
                await db.add_call(chat_id)

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
                    else:
                        await message.edit_text(
                            text=text,
                            reply_markup=keyboard,
                            disable_web_page_preview=True,
                        )
                        sent = message
                except (
                    ChatSendMediaForbidden,
                    ChatSendPhotosForbidden,
                    MessageIdInvalid,
                ):
                    if _thumb:
                        sent = await app.send_photo(
                            chat_id=chat_id,
                            photo=_thumb,
                            caption=text,
                            reply_markup=keyboard,
                        )
                    else:
                        sent = await app.send_message(
                            chat_id=chat_id,
                            text=text,
                            reply_markup=keyboard,
                            disable_web_page_preview=True,
                        )

                media.message_id = sent.id

                try:
                    if _thumb:
                        rawtg.edit_message_caption(
                            chat_id=chat_id,
                            message_id=media.message_id,
                            caption=text,
                            reply_markup=buttons.controls(chat_id),
                            parse_mode="HTML",
                        )
                    else:
                        rawtg.edit_message_text(
                            chat_id=chat_id,
                            message_id=media.message_id,
                            text=text,
                            reply_markup=buttons.controls(chat_id),
                            parse_mode="HTML",
                            disable_web_page_preview=True,
                        )
                except Exception:
                    pass

        except FileNotFoundError:
            await message.edit_text(
                _lang["error_no_file"].format(config.SUPPORT_CHAT)
            )
            await self.play_next(chat_id)

        except exceptions.NoActiveGroupCall:
            await self.stop(chat_id)
            await message.edit_text(_lang["error_no_call"])

        except exceptions.NoAudioSourceFound:
            await message.edit_text(_lang["error_no_audio"])
            await self.play_next(chat_id)

        except (
            ConnectionError,
            ConnectionNotFound,
            TelegramServerError,
        ):
            await self.stop(chat_id)
            await message.edit_text(_lang["error_tg_server"])

        except RTMPStreamingUnsupported:
            await self.stop(chat_id)
            await message.edit_text(_lang["error_rtmp"])

    async def replay(self, chat_id: int) -> None:
        if not await db.get_call(chat_id):
            return

        media = queue.get_current(chat_id)
        _lang = await lang.get_lang(chat_id)
        msg = await app.send_message(
            chat_id=chat_id,
            text=_lang["play_again"],
        )
        media.message_id = msg.id
        await self.play_media(chat_id, msg, media)

    async def play_next(self, chat_id: int) -> None:
        if loop := await db.get_loop(chat_id):
            await db.set_loop(chat_id, loop - 1)
            return await self.replay(chat_id)

        current = queue.get_current(chat_id)
        media = queue.get_next(chat_id)

        if not media:
            try:
                if current and getattr(current, "message_id", 0):
                    _lang = await lang.get_lang(chat_id)
                    rawtg.edit_message_reply_markup(
                        chat_id=chat_id,
                        message_id=current.message_id,
                        reply_markup=buttons.controls(
                            chat_id=chat_id,
                            status=_lang["stopped"],
                            remove=True,
                        ),
                    )
            except Exception:
                pass
            return await self.stop(chat_id)

        try:
            if current and getattr(current, "message_id", 0):
                await app.delete_messages(
                    chat_id=chat_id,
                    message_ids=current.message_id,
                    revoke=True,
                )
                current.message_id = 0
        except Exception:
            pass

        _lang = await lang.get_lang(chat_id)
        msg = await app.send_message(
            chat_id=chat_id,
            text=_lang["play_next"],
        )

        if not media.file_path:
            media.file_path = await yt.download(media.id, video=media.video)
            if not media.file_path:
                await self.play_next(chat_id)
                return await msg.edit_text(
                    _lang["error_no_file"].format(config.SUPPORT_CHAT)
                )

        media.message_id = msg.id
        await self.play_media(chat_id, msg, media)

    async def volume(self, chat_id: int, volume: int) -> bool:
        client = await db.get_assistant(chat_id)
        try:
            await client.change_volume_call(chat_id, volume)
            return True
        except Exception:
            return False
        return False

    async def ping(self) -> float:
        pings = [client.ping for client in self.clients]
        return round(sum(pings) / len(pings), 2)

    async def decorators(self, client: PyTgCalls) -> None:
        @client.on_update()
        async def update_handler(_, update: types.Update) -> None:
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

    async def boot(self) -> None:
        PyTgCallsSession.notice_displayed = True
        for ub in userbot.clients:
            client = PyTgCalls(ub, cache_duration=100)
            await client.start()
            self.clients.append(client)
            await self.decorators(client)
        logger.info("PyTgCalls client(s) started.")
