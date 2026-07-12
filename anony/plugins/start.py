# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of AnonXMusic

import asyncio
import inspect

from pyrogram import enums, filters, types

from anony import app, config, db, lang
from anony.helpers import buttons, rawtg, utils
from anony.utils.old_posts import old_post_clean_enabled


async def _maybe_await(result):
    if inspect.isawaitable(result):
        return await result
    return result


async def _send_raw_photo_with_buttons(
    chat_id: int,
    photo,
    caption: str,
    reply_markup,
):
    result = rawtg.send_photo(
        chat_id=chat_id,
        photo=photo,
        caption=caption,
        reply_markup=reply_markup,
        parse_mode="HTML",
    )
    result = await _maybe_await(result)

    # sendPhoto ပြီးချက်ချင်း caption+markup ကို raw edit ပြန်လုပ်
    if isinstance(result, dict) and result.get("ok") and result.get("result"):
        try:
            msg = result["result"]
            msg_id = msg["message_id"]

            edited = rawtg.edit_message_caption(
                chat_id=chat_id,
                message_id=msg_id,
                caption=caption,
                reply_markup=reply_markup,
                parse_mode="HTML",
            )
            edited = await _maybe_await(edited)
            print(f"RAW PHOTO POST-EDIT: {edited}")
        except Exception as e:
            print(f"RAW PHOTO POST-EDIT ERROR: {e}")

    return result


async def _send_raw_text_with_buttons(
    chat_id: int,
    text: str,
    reply_markup,
):
    result = rawtg.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=reply_markup,
        parse_mode="HTML",
    )
    return await _maybe_await(result)


@app.on_message(filters.command(["help"]) & filters.private & ~app.bl_users)
@lang.language()
async def _help(_, m: types.Message):
    key = buttons.help_markup(m.lang)
    result = await _send_raw_photo_with_buttons(
        chat_id=m.chat.id,
        photo=config.HELP_IMG,
        caption=m.lang["help_menu"],
        reply_markup=key,
    )

    if isinstance(result, dict) and result.get("ok") is False:
        print(f"RAW HELP SEND ERROR: {result}")
        await m.reply_photo(
            photo=config.HELP_IMG,
            caption=m.lang["help_menu"],
            reply_markup=key,
            quote=True,
        )


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
    result = await _send_raw_photo_with_buttons(
        chat_id=message.chat.id,
        photo=config.START_IMG,
        caption=_text,
        reply_markup=key,
    )

    if isinstance(result, dict) and result.get("ok") is False:
        print(f"RAW START SEND ERROR: {result}")
        await message.reply_photo(
            photo=config.START_IMG,
            caption=_text,
            reply_markup=key,
            quote=not private,
        )

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
    auto_delete_old_posts = await old_post_clean_enabled(message.chat.id)

    text = message.lang["start_settings"].format(message.chat.title)
    key = buttons.settings_markup(
        message.lang,
        admin_only,
        cmd_delete,
        _language,
        message.chat.id,
        auto_delete_old_posts,
    )

    result = await _send_raw_text_with_buttons(
        chat_id=message.chat.id,
        text=text,
        reply_markup=key,
    )

    if isinstance(result, dict) and result.get("ok") is False:
        print(f"RAW SETTINGS SEND ERROR: {result}")
        await message.reply_text(
            text=text,
            reply_markup=key,
            quote=True,
        )


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
