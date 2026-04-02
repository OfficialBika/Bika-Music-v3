# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of AnonXMusic

import html

from pyrogram import filters, types

from anony import app, config, db, lang, queue, thumb
from anony.helpers import Track, buttons, rawtg
from anony.utils.rawsafe import safe_delete, safe_send_text


@app.on_message(filters.command(["queue", "playing"]) & filters.group & ~app.bl_users)
@lang.language()
async def _queue_func(_, m: types.Message):
    if not await db.get_call(m.chat.id):
        return await m.reply_text(m.lang["not_playing"])

    _reply = await m.reply_text(m.lang["queue_fetching"])

    try:
        _queue = queue.get_queue(m.chat.id)
        if not _queue:
            return await _reply.edit_text(m.lang["not_playing"])

        _media = _queue[0]
        _thumb = (
            await thumb.generate(_media)
            if isinstance(_media, Track) and config.THUMB_GEN
            else config.DEFAULT_THUMB if config.THUMB_GEN else None
        )

        _text = m.lang["queue_curr"].format(
            _media.url,
            html.escape(_media.title[:50]),
            _media.duration,
            _media.user,
        )

        _queue.pop(0)

        if _queue:
            _text += "\n> "
            for i, media in enumerate(_queue, start=1):
                if i == 15:
                    break
                _text += m.lang["queue_item"].format(
                    i + 1,
                    html.escape(media.title),
                    media.duration,
                )
            _text += "\n"

        _playing = await db.playing(m.chat.id)
        _buttons = buttons.queue_markup(
            m.chat.id,
            m.lang["playing"] if _playing else m.lang["paused"],
            _playing,
        )

        sent = await safe_send_text(
            rawtg,
            m,
            text=_text,
            reply_markup=_buttons,
        )

        if sent:
            await safe_delete(_reply)

    except Exception as e:
        print(f"QUEUE ERROR: {e}")
        try:
            await _reply.edit_text(f"{m.lang['not_playing']}\n\nError: {e}")
        except Exception:
            await m.reply_text(f"{m.lang['not_playing']}\n\nError: {e}")
