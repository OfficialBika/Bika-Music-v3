# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of AnonXMusic
#
# Production stability patch:
# - raw Bot API edits run in a thread so timer updates do not freeze the event loop.
# - background tasks are protected from stale queue/active-call state.
# - vc_watcher no longer dies permanently after one Telegram error.

import time
import asyncio

from pyrogram import enums, errors, filters, types

from anony import anon, app, config, db, lang, logger, queue, tasks, userbot, yt
from anony.helpers import buttons, rawtg


@app.on_message(filters.video_chat_started, group=19)
@app.on_message(filters.video_chat_ended, group=20)
async def _watcher_vc(_, m: types.Message):
    await anon.stop(m.chat.id)


async def _safe_raw_edit_reply_markup(chat_id: int, message_id: int, reply_markup=None) -> None:
    if not message_id:
        return
    try:
        await asyncio.to_thread(
            rawtg.edit_message_reply_markup,
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=reply_markup,
        )
    except Exception:
        pass


async def auto_leave():
    while True:
        await asyncio.sleep(3600)
        for ub in userbot.clients:
            try:
                chats = [
                    dialog.chat.id async for dialog in ub.get_dialogs()
                    if dialog.chat.type in [
                        enums.ChatType.GROUP,
                        enums.ChatType.SUPERGROUP,
                    ]
                ][-20:]
                for chat in chats:
                    if chat in [app.logger, -1001686672798, -1001549206010]:
                        continue
                    if chat in db.active_calls:
                        continue
                    try:
                        await ub.leave_chat(chat)
                    except Exception:
                        pass
                    await asyncio.sleep(7)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning("auto_leave loop error: %s", e)
                continue


async def track_time():
    while True:
        await asyncio.sleep(1)
        for chat_id in list(db.active_calls):
            try:
                if not await db.playing(chat_id):
                    continue
                media = queue.get_current(chat_id)
                if not media:
                    await db.remove_call(chat_id)
                    continue
                media.time = int(getattr(media, "time", 0) or 0) + 1
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning("track_time error chat=%s: %s", chat_id, e)


async def update_timer(length=10):
    while True:
        await asyncio.sleep(7)
        for chat_id in list(db.active_calls):
            try:
                if not await db.playing(chat_id):
                    continue

                media = queue.get_current(chat_id)
                if not media:
                    await db.remove_call(chat_id)
                    continue

                duration = int(getattr(media, "duration_sec", 0) or 0)
                message_id = int(getattr(media, "message_id", 0) or 0)
                played = int(getattr(media, "time", 0) or 0)

                if not duration or not message_id or not played:
                    continue

                remaining = duration - played
                if remaining < 0:
                    remaining = 0

                pos = min(max(int((played / duration) * length), 0), length - 1)
                timer = "—" * pos + "◉" + "—" * (length - pos - 1)

                if remaining <= 30:
                    next_media = queue.get_next(chat_id, check=True)
                    if next_media and not getattr(next_media, "file_path", None):
                        try:
                            next_media.file_path = await yt.download(
                                next_media.id,
                                video=next_media.video,
                            )
                        except Exception as e:
                            logger.warning(
                                "Pre-download failed chat=%s id=%s: %s",
                                chat_id,
                                getattr(next_media, "id", None),
                                e,
                            )

                if remaining < 10:
                    remove = True
                else:
                    if config.THUMB_GEN:
                        timer = (
                            f"{time.strftime('%M:%S', time.gmtime(played))} | "
                            f"{timer} | -{time.strftime('%M:%S', time.gmtime(remaining))}"
                        )
                    else:
                        timer = None
                    remove = False

                if not timer and not remove:
                    continue

                await _safe_raw_edit_reply_markup(
                    chat_id=chat_id,
                    message_id=message_id,
                    reply_markup=buttons.controls(
                        chat_id=chat_id, timer=timer, remove=remove
                    ),
                )

            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning("update_timer error chat=%s: %s", chat_id, e)


async def vc_watcher(sleep=15):
    while True:
        await asyncio.sleep(sleep)
        for chat_id in list(db.active_calls):
            try:
                client = await db.get_assistant(chat_id)
                media = queue.get_current(chat_id)
                if not media:
                    await db.remove_call(chat_id)
                    continue

                participants = await client.get_participants(chat_id)
                if len(participants) < 2 and int(getattr(media, "time", 0) or 0) > 30:
                    _lang = await lang.get_lang(chat_id)
                    await _safe_raw_edit_reply_markup(
                        chat_id=chat_id,
                        message_id=getattr(media, "message_id", 0),
                        reply_markup=buttons.controls(
                            chat_id=chat_id, status=_lang["stopped"], remove=True
                        ),
                    )
                    await anon.stop(chat_id)
                    await app.send_message(chat_id, _lang["auto_left"])
            except asyncio.CancelledError:
                raise
            except errors.MessageIdInvalid:
                pass
            except Exception as e:
                logger.warning("vc_watcher error chat=%s: %s", chat_id, e)


if config.AUTO_END:
    tasks.append(asyncio.create_task(vc_watcher()))
if config.AUTO_LEAVE:
    tasks.append(asyncio.create_task(auto_leave()))
tasks.append(asyncio.create_task(track_time()))
tasks.append(asyncio.create_task(update_timer()))
