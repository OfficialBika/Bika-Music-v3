import io
import os
import re
import sys
import time
import uuid
import traceback
from html import escape
from typing import Any

from pyrogram import filters, types

from anony import anon, app, config, db, lang, logger, userbot
from anony.helpers import format_exception, meval


@app.on_message(filters.command(["eval", "exec"]) & filters.user(app.owner))
@app.on_edited_message(filters.command(["eval", "exec"]) & filters.user(app.owner))
@lang.language()
async def eval_handler(_, message: types.Message):
    if not config.ENABLE_EVAL:
        return await message.reply_text(
            "Eval/exec is disabled. Set ENABLE_EVAL=True to enable it."
        )
    if len(message.command) < 2:
        return await message.reply_text(message.lang["eval_inp"])

    code = message.text.split(None, 1)[1]
    out_buf = io.StringIO()

    async def send(*args: Any, **kwargs: Any) -> types.Message:
        return await message.reply_text(*args, **kwargs)

    def _print(*args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("file", out_buf)
        print(*args, **kwargs)

    eval_vars = {
        "m": message, "r": message.reply_to_message, "chat": message.chat,
        "user": message.from_user, "app": app, "anon": anon, "db": db,
        "client": app, "ub": userbot, "ikb": types.InlineKeyboardButton,
        "ikm": types.InlineKeyboardMarkup, "send": send, "config": config,
        "print": _print, "os": os, "re": re, "sys": sys, "tb": traceback,
    }
    started = time.monotonic()
    error = None
    try:
        result = await meval(code, globals(), **eval_vars)
    except Exception as exc:
        tb = traceback.extract_tb(exc.__traceback__)
        index = next((i for i, frame in enumerate(tb) if frame.filename == "<string>"), -1)
        error = format_exception(exc, tb[index:] if index != -1 else tb)
        result = None

    if config.EVAL_AUDIT:
        logger.warning(
            "Owner eval executed: owner_id=%s message_id=%s duration=%.3fs error=%s",
            message.from_user.id if message.from_user else 0,
            message.id,
            time.monotonic() - started,
            bool(error),
        )

    output = error or out_buf.getvalue().strip()
    if not output and result is not None:
        output = str(result)
    response = message.lang["eval_out"].format(escape(output or "None"))
    if len(response) > 4096:
        with io.BytesIO(output.encode()) as out_file:
            out_file.name = f"{uuid.uuid4().hex[:8].lower()}.txt"
            return await message.reply_document(document=out_file, disable_notification=True)
    await message.reply_text(response)
