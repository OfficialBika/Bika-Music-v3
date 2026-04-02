# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of AnonXMusic

import asyncio
from pyrogram import enums, filters, types

from anony import app, config, db, lang
from anony.helpers import buttons, rawtg, utils


async def _apply_raw_markup(msg: types.Message, markup):
    try:
        result = rawtg.edit_message_reply_markup(
            chat_id=msg.chat.id,
            message_id=msg.id,
            reply_markup=markup,
        )
        if hasattr(result, "__await__"):
            await result
    except Exception as e:
        print(f"RAW MARKUP APPLY ERROR: {e}")


@app.on_message(filters.command(["help"]) & filters.private & ~app.bl_users)
@lang.language()
async def _help(_, m: types.Message):
    key = buttons.help_markup(m.lang)
    msg = await m.reply_photo(
        photo=config.HELP_IMG,
        caption=m.lang["help_menu"],
        reply_markup=key,
        quote=True,
    )
    await _apply_raw_markup(msg, key)


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
    await _apply_raw_markup(msg, key)

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
    key = buttons.settings_markup(
        message.lang, admin_only, cmd_delete, _language, message.chat.id
    )
    msg = await message.reply_text(
        text=message.lang["start_settings"].format(message.chat.title),
        reply_markup=key,
        quote=True,
    )
    await _apply_raw_markup(msg, key)


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
