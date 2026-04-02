# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of AnonXMusic

import asyncio
import inspect

from pyrogram import enums, filters, types

from anony import app, config, db, lang
from anony.helpers import buttons, rawtg, utils


async def _maybe_await(result):
    if inspect.isawaitable(result):
        return await result
    return result


async def _apply_raw_message(msg: types.Message, markup, text: str | None = None, caption: str | None = None):
    try:
        if caption is not None:
            # rawtg မှာ edit_message_caption မရှိလို့ pyrogram method သုံး
            return await msg.edit_caption(
                caption=caption,
                reply_markup=markup,
                parse_mode=enums.ParseMode.HTML,
            )

        if text is not None:
            result = rawtg.edit_message_text(
                chat_id=msg.chat.id,
                message_id=msg.id,
                text=text,
                reply_markup=markup,
                parse_mode="HTML",
            )
            result = await _maybe_await(result)

            if isinstance(result, dict) and result.get("ok") is False:
                return await msg.edit_text(
                    text=text,
                    reply_markup=markup,
                    disable_web_page_preview=True,
                    parse_mode=enums.ParseMode.HTML,
                )
            return result

        result = rawtg.edit_message_reply_markup(
            chat_id=msg.chat.id,
            message_id=msg.id,
            reply_markup=markup,
        )
        result = await _maybe_await(result)

        if isinstance(result, dict) and result.get("ok") is False:
            return await msg.edit_reply_markup(reply_markup=markup)

        return result

    except Exception as e:
        print(f"RAW MESSAGE APPLY ERROR: {e}")


@app.on_message(filters.command(["help"]) & filters.private & ~app.bl_users)
@lang.language()
async def _help(_, m: types.Message):
    key = buttons.help_markup(m.lang)
    caption = m.lang["help_menu"]

    msg = await m.reply_photo(
        photo=config.HELP_IMG,
        caption=caption,
        reply_markup=key,
        quote=True,
    )
    await _apply_raw_message(msg, key, caption=caption)


@app.on_message(filters.command(["start"]))
@lang.language()
async def start(_, message: types.Message):
    if message.from_user.id in app.bl_users and message.from_user.id not in db.notified:
        return await message.reply_text(message.lang["bl_user_notify"])

    if len(message.command) > 1 and message.command[1] == "help":
        return await _help(_, message)

    private = message.chat.type == enums.ChatType.PRIVATE
    _text = (
        message.lang["start_pm"].format(message.from_user.first_name, app.name)
        if private
        else message.lang["start_gp"].format(app.name)
    )

    key = buttons.start_key(message.lang, private)
    msg = await message.reply_photo(
        photo=config.START_IMG,
        caption=_text,
        reply_markup=key,
        quote=not private,
    )
    await _apply_raw_message(msg, key, caption=_text)

    if private:
        if await db.is_user(message.from_user.id):
            return
        await utils.send_log(message)
        await db.add_user(message.from_user.id)
    else:
        if await db.is_chat(message.chat.id):
            return
        await utils.send_log(message, True)
        await db.add_chat(message.chat.id)


@app.on_message(filters.command(["playmode", "settings"]) & filters.group & ~app.bl_users)
@lang.language()
async def settings(_, message: types.Message):
    admin_only = await db.get_play_mode(message.chat.id)
    cmd_delete = await db.get_cmd_delete(message.chat.id)
    _language = await db.get_lang(message.chat.id)

    text = message.lang["start_settings"].format(message.chat.title)
    key = buttons.settings_markup(
        message.lang, admin_only, cmd_delete, _language, message.chat.id
    )

    msg = await message.reply_text(
        text=text,
        reply_markup=key,
        quote=True,
    )
    await _apply_raw_message(msg, key, text=text)


@app.on_message(filters.new_chat_members, group=7)
@lang.language()
async def _new_member(_, message: types.Message):
    if message.chat.type != enums.ChatType.SUPERGROUP:
        return await message.chat.leave()

    await asyncio.sleep(3)
    for member in message.new_chat_members:
        if member.id == app.id:
            if await db.is_chat(message.chat.id):
                return
            await utils.send_log(message, True)
            await db.add_chat(message.chat.id)
