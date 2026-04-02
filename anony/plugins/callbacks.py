# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of AnonXMusic

import re

from pyrogram import errors, filters, types

from anony import anon, app, db, lang, queue, tg, yt
from anony.helpers import admin_check, buttons, can_manage_vc, rawtg
from anony.utils.rawsafe import (
    safe_answer_callback,
    safe_delete,
    safe_edit_reply_markup,
    safe_edit_text,
    safe_reply_text,
)


@app.on_callback_query(filters.regex("cancel_dl") & ~app.bl_users)
@lang.language()
async def cancel_dl(_, query: types.CallbackQuery):
    await safe_answer_callback(query)
    await tg.cancel(query)


@app.on_callback_query(filters.regex("controls") & ~app.bl_users)
@lang.language()
@can_manage_vc
async def _controls(_, query: types.CallbackQuery):
    args = query.data.split()

    if len(args) < 3:
        return await safe_answer_callback(query, "Invalid control request", show_alert=True)

    action = args[1]
    chat_id = int(args[2])
    qaction = len(args) == 4
    user = query.from_user.mention

    if not await db.get_call(chat_id):
        try:
            return await safe_answer_callback(
                query, query.lang["not_playing"], show_alert=True
            )
        except errors.QueryIdInvalid:
            try:
                await safe_delete(query.message)
            except Exception:
                pass
            return

    if action == "status":
        return await safe_answer_callback(query)

    await safe_answer_callback(query, query.lang["processing"], show_alert=True)

    if action == "pause":
        if not await db.playing(chat_id):
            return await safe_answer_callback(
                query, query.lang["play_already_paused"], show_alert=True
            )

        await anon.pause(chat_id)

        if qaction:
            await safe_edit_reply_markup(
                rawtg,
                query,
                reply_markup=buttons.queue_markup(chat_id, query.lang["paused"], False),
            )
            return

        status = query.lang["paused"]
        reply = query.lang["play_paused"].format(user)

    elif action == "resume":
        if await db.playing(chat_id):
            return await safe_answer_callback(
                query, query.lang["play_not_paused"], show_alert=True
            )

        await anon.resume(chat_id)

        if qaction:
            await safe_edit_reply_markup(
                rawtg,
                query,
                reply_markup=buttons.queue_markup(chat_id, query.lang["playing"], True),
            )
            return

        status = query.lang["playing"]
        reply = query.lang["play_resumed"].format(user)

    elif action == "skip":
        await anon.play_next(chat_id)
        status = query.lang["skipped"]
        reply = query.lang["play_skipped"].format(user)

    elif action == "force":
        if len(args) < 4:
            return await safe_answer_callback(query, "Invalid force request", show_alert=True)

        pos, media = queue.check_item(chat_id, args[3])
        if not media or pos == -1:
            return await safe_edit_text(rawtg, query, query.lang["play_expired"])

        current = queue.get_current(chat_id)
        m_id = current.message_id if current else None

        queue.force_add(chat_id, media, remove=pos)

        try:
            if m_id:
                await app.delete_messages(
                    chat_id=chat_id,
                    message_ids=[m_id, media.message_id],
                    revoke=True,
                )
            media.message_id = None
        except Exception:
            pass

        msg = await app.send_message(chat_id=chat_id, text=query.lang["play_next"])

        if not media.file_path:
            media.file_path = await yt.download(media.id, video=media.video)

        media.message_id = msg.id
        return await anon.play_media(chat_id, msg, media)

    elif action == "replay":
        media = queue.get_current(chat_id)
        media.user = user
        await anon.replay(chat_id)
        status = query.lang["replayed"]
        reply = query.lang["play_replayed"].format(user)

    elif action == "stop":
        await anon.stop(chat_id)
        status = query.lang["stopped"]
        reply = query.lang["play_stopped"].format(user)

    else:
        return await safe_answer_callback(query, "Unknown action", show_alert=True)

    try:
        if action in ["skip", "replay", "stop"]:
            await safe_reply_text(query.message, reply)
            await safe_delete(query.message)
            return

        source_text = ""
        if getattr(query.message, "caption", None):
            try:
                source_text = query.message.caption.html
            except Exception:
                source_text = query.message.caption or ""
        elif getattr(query.message, "text", None):
            try:
                source_text = query.message.text.html
            except Exception:
                source_text = query.message.text or ""

        if source_text:
            source_text = re.sub(
                r"\n\n> .*?\Z",
                "",
                source_text,
                flags=re.DOTALL,
            )

        keyboard = buttons.controls(
            chat_id,
            status=status if action != "resume" else None,
        )

        await safe_edit_text(
            rawtg,
            query,
            text=f"{source_text}\n\n> {reply}" if source_text else reply,
            reply_markup=keyboard,
        )
    except Exception as e:
        print(f"CONTROLS CALLBACK ERROR: {e}")
        try:
            await safe_reply_text(query.message, reply)
        except Exception:
            pass


@app.on_callback_query(filters.regex("help") & ~app.bl_users)
@lang.language()
async def _help(_, query: types.CallbackQuery):
    data = query.data.split()

    if len(data) == 1:
        return await safe_answer_callback(
            query,
            url=f"https://t.me/{app.username}?start=help",
        )

    await safe_answer_callback(query)

    if data[1] == "back":
        return await safe_edit_text(
            rawtg,
            query,
            text=query.lang["help_menu"],
            reply_markup=buttons.help_markup(query.lang),
        )

    elif data[1] == "close":
        try:
            await safe_delete(query.message)
            if query.message.reply_to_message:
                await safe_delete(query.message.reply_to_message)
            return
        except Exception as e:
            print(f"HELP CLOSE ERROR: {e}")
            return

    key = f"help_{data[1]}"
    return await safe_edit_text(
        rawtg,
        query,
        text=query.lang[key],
        reply_markup=buttons.help_markup(query.lang, True),
    )


@app.on_callback_query(filters.regex("settings") & ~app.bl_users)
@lang.language()
@admin_check
async def _settings_cb(_, query: types.CallbackQuery):
    cmd = query.data.split()

    if len(cmd) == 1:
        return await safe_answer_callback(query)

    await safe_answer_callback(query, query.lang["processing"], show_alert=True)

    chat_id = query.message.chat.id
    _admin = await db.get_play_mode(chat_id)
    _delete = await db.get_cmd_delete(chat_id)
    _language = await db.get_lang(chat_id)

    if cmd[1] == "delete":
        _delete = not _delete
        await db.set_cmd_delete(chat_id, _delete)

    elif cmd[1] == "play":
        await db.set_play_mode(chat_id, _admin)
        _admin = not _admin

    await safe_edit_reply_markup(
        rawtg,
        query,
        reply_markup=buttons.settings_markup(
            query.lang,
            _admin,
            _delete,
            _language,
            chat_id,
        ),
    )
