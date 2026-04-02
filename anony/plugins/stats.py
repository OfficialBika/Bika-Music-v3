# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of AnonXMusic

import os
import platform
import sys
import inspect

import psutil
from pyrogram import __version__, filters, types
from pytgcalls import __version__ as pytgver

from anony import app, config, db, lang, userbot
from anony.helpers import rawtg
from anony.plugins import all_modules


async def _maybe_await(result):
    if inspect.isawaitable(result):
        return await result
    return result


@app.on_message(filters.command(["stats"]) & filters.group & ~app.bl_users)
@lang.language()
async def _stats(_, m: types.Message):
    sent = await m.reply_photo(
        photo=config.PING_IMG,
        caption=m.lang["stats_fetching"],
        parse_mode="HTML",
    )

    try:
        pid = os.getpid()
        _utext = m.lang["stats_user"].format(
            app.name,
            len(userbot.clients),
            config.AUTO_LEAVE,
            len(db.blacklisted),
            len(app.bl_users),
            len(app.sudoers),
            len(await db.get_chats()),
            len(await db.get_users()),
        )

        if m.from_user.id in app.sudoers:
            process = psutil.Process(pid)
            storage = psutil.disk_usage("/")
            _utext += m.lang["stats_sudo"].format(
                len(all_modules),
                platform.system(),
                f"{process.memory_info().rss / 1024**2:.2f}",
                round(psutil.virtual_memory().total / (1024.0**3)),
                process.cpu_percent(interval=1.0),
                psutil.cpu_count(),
                f"{storage.used / (1024.0**3):.2f}",
                f"{storage.total / (1024.0**3):.2f}",
                sys.version.split()[0],
                __version__,
                pytgver,
            )

        result = rawtg.edit_message_caption(
            chat_id=sent.chat.id,
            message_id=sent.id,
            caption=_utext,
            parse_mode="HTML",
        )
        result = await _maybe_await(result)

        if isinstance(result, dict) and result.get("ok") is False:
            print(f"RAW STATS EDIT ERROR: {result}")
            await sent.edit_caption(
                _utext,
                parse_mode="HTML",
            )

    except Exception as e:
        print(f"STATS CMD ERROR: {e}")
        try:
            await sent.edit_caption(
                f"<b>Stats error:</b>\n<code>{e}</code>",
                parse_mode="HTML",
            )
        except Exception:
            await m.reply_text(
                f"Stats error:\n{e}",
            )
