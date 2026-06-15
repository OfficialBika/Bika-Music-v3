# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of AnonXMusic
#
# Production stability patch:
# - Handles stale active-call state where DB says playing but queue is empty.
# - Validates missing file path before seeking.
# - Updates media.time only after PyTgCalls play succeeds.

from pyrogram import filters, types

from anony import anon, app, config, db, lang, queue
from anony.helpers import can_manage_vc


@app.on_message(filters.command(["seek", "seekback"]) & filters.group & ~app.bl_users)
@lang.language()
@can_manage_vc
async def _seek(_, m: types.Message):
    if len(m.command) < 2:
        return await m.reply_text(m.lang["play_seek_usage"].format(m.command[0]))

    try:
        to_seek = int(m.command[1])
    except (TypeError, ValueError):
        return await m.reply_text(m.lang["play_seek_usage"].format(m.command[0]))

    if to_seek < 10:
        return await m.reply_text(m.lang["play_seek_min"])

    if not await db.get_call(m.chat.id):
        return await m.reply_text(m.lang["not_playing"])

    if not await db.playing(m.chat.id):
        return await m.reply_text(m.lang["play_already_paused"])

    media = queue.get_current(m.chat.id)
    if not media:
        await db.remove_call(m.chat.id)
        return await m.reply_text(m.lang["not_playing"])

    if not getattr(media, "duration_sec", 0):
        return await m.reply_text(m.lang["play_seek_no_dur"])

    if not getattr(media, "file_path", None):
        return await m.reply_text(m.lang["error_no_file"].format(config.SUPPORT_CHAT))

    sent = await m.reply_text(m.lang["play_seeking"])
    current_time = max(1, int(getattr(media, "time", 1) or 1))
    duration = int(media.duration_sec)

    if m.command[0] == "seekback":
        stype = m.lang["backward"]
        start_from = max(1, current_time - to_seek)
    else:
        stype = m.lang["forward"]
        start_from = current_time + to_seek
        if start_from + 10 > duration:
            start_from = max(1, duration - 5)

    ok = await anon.play_media(m.chat.id, sent, media, start_from)
    if not ok:
        return

    media.time = start_from
    mention = getattr(m.from_user, "mention", "User")
    await sent.edit_text(
        m.lang["play_seeked"].format(stype, start_from, mention)
    )
