# anony/utils/rawsafe.py

from __future__ import annotations

import asyncio
import inspect
from typing import Any

from pyrogram.errors import BadRequest, FloodWait, MessageIdInvalid, MessageNotModified


def _is_message_to_edit_not_found(error: Exception) -> bool:
    text = str(error).lower()
    return (
        "message to edit not found" in text
        or "message_id_invalid" in text
        or "message id invalid" in text
    )


def _is_message_not_modified(error: Exception) -> bool:
    text = str(error).lower()
    return "message is not modified" in text or "message not modified" in text


async def _handle_flood_wait(error: Exception) -> None:
    if isinstance(error, FloodWait):
        await asyncio.sleep(int(error.value) + 1)


async def _maybe_await(result: Any) -> Any:
    if inspect.isawaitable(result):
        return await result
    return result


async def safe_edit_text(
    rawtg: Any,
    query: Any,
    text: str,
    reply_markup: Any = None,
    disable_web_page_preview: bool = True,
    parse_mode: Any = None,
) -> Any:
    for _ in range(2):
        try:
            result = rawtg.edit_message_text(
                chat_id=query.message.chat.id,
                message_id=query.message.id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
            )
            return await _maybe_await(result)

        except MessageNotModified:
            return None

        except FloodWait as e:
            await _handle_flood_wait(e)
            continue

        except (BadRequest, MessageIdInvalid) as e:
            err = str(e).lower()

            if _is_message_not_modified(e):
                return None

            if "there is no text in the message to edit" in err:
                try:
                    result = rawtg.edit_message_caption(
                        chat_id=query.message.chat.id,
                        message_id=query.message.id,
                        caption=text,
                        reply_markup=reply_markup,
                        parse_mode=parse_mode,
                    )
                    return await _maybe_await(result)
                except MessageNotModified:
                    return None
                except FloodWait as fw:
                    await _handle_flood_wait(fw)
                    continue
                except Exception:
                    try:
                        return await query.message.reply_text(
                            text=text,
                            reply_markup=reply_markup,
                            disable_web_page_preview=disable_web_page_preview,
                            parse_mode=parse_mode,
                        )
                    except FloodWait as fw:
                        await _handle_flood_wait(fw)
                        return await query.message.reply_text(
                            text=text,
                            reply_markup=reply_markup,
                            disable_web_page_preview=disable_web_page_preview,
                            parse_mode=parse_mode,
                        )

            if _is_message_to_edit_not_found(e):
                try:
                    return await query.message.reply_text(
                        text=text,
                        reply_markup=reply_markup,
                        disable_web_page_preview=disable_web_page_preview,
                        parse_mode=parse_mode,
                    )
                except FloodWait as fw:
                    await _handle_flood_wait(fw)
                    return await query.message.reply_text(
                        text=text,
                        reply_markup=reply_markup,
                        disable_web_page_preview=disable_web_page_preview,
                        parse_mode=parse_mode,
                    )
            raise

        except Exception:
            raise


async def safe_edit_caption(
    rawtg: Any,
    query: Any,
    caption: str,
    reply_markup: Any = None,
    parse_mode: Any = None,
) -> Any:
    for _ in range(2):
        try:
            result = rawtg.edit_message_caption(
                chat_id=query.message.chat.id,
                message_id=query.message.id,
                caption=caption,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
            )
            return await _maybe_await(result)
        except MessageNotModified:
            return None
        except FloodWait as e:
            await _handle_flood_wait(e)
            continue
        except (BadRequest, MessageIdInvalid) as e:
            if _is_message_not_modified(e):
                return None
            if _is_message_to_edit_not_found(e):
                try:
                    return await query.message.reply_text(
                        text=caption,
                        reply_markup=reply_markup,
                        parse_mode=parse_mode,
                    )
                except FloodWait as fw:
                    await _handle_flood_wait(fw)
                    return await query.message.reply_text(
                        text=caption,
                        reply_markup=reply_markup,
                        parse_mode=parse_mode,
                    )
            raise
        except Exception:
            raise


async def safe_edit_reply_markup(
    rawtg: Any,
    query: Any,
    reply_markup: Any = None,
) -> Any:
    for _ in range(2):
        try:
            result = rawtg.edit_message_reply_markup(
                chat_id=query.message.chat.id,
                message_id=query.message.id,
                reply_markup=reply_markup,
            )
            return await _maybe_await(result)
        except MessageNotModified:
            return None
        except FloodWait as e:
            await _handle_flood_wait(e)
            continue
        except (BadRequest, MessageIdInvalid) as e:
            if _is_message_not_modified(e):
                return None
            if _is_message_to_edit_not_found(e):
                return None
            raise
        except Exception:
            raise


async def safe_send_text(
    rawtg: Any,
    message: Any,
    text: str,
    reply_markup: Any = None,
    disable_web_page_preview: bool = True,
    parse_mode: Any = None,
) -> Any:
    for _ in range(2):
        try:
            result = rawtg.send_message(
                chat_id=message.chat.id,
                text=text,
                reply_markup=reply_markup,
                disable_web_page_preview=disable_web_page_preview,
                parse_mode=parse_mode,
            )
            return await _maybe_await(result)
        except FloodWait as e:
            await _handle_flood_wait(e)
            continue
        except Exception:
            try:
                return await message.reply_text(
                    text=text,
                    reply_markup=reply_markup,
                    disable_web_page_preview=disable_web_page_preview,
                    parse_mode=parse_mode,
                )
            except FloodWait as fw:
                await _handle_flood_wait(fw)
                return await message.reply_text(
                    text=text,
                    reply_markup=reply_markup,
                    disable_web_page_preview=disable_web_page_preview,
                    parse_mode=parse_mode,
                )


async def safe_reply_text(
    message: Any,
    text: str,
    reply_markup: Any = None,
    disable_web_page_preview: bool = True,
    parse_mode: Any = None,
) -> Any:
    for _ in range(2):
        try:
            return await message.reply_text(
                text=text,
                reply_markup=reply_markup,
                disable_web_page_preview=disable_web_page_preview,
                parse_mode=parse_mode,
            )
        except FloodWait as e:
            await _handle_flood_wait(e)
            continue
    return None


async def safe_delete(message: Any) -> bool:
    for _ in range(2):
        try:
            result = message.delete()
            await _maybe_await(result)
            return True
        except FloodWait as e:
            await _handle_flood_wait(e)
            continue
        except Exception:
            return False
    return False


async def safe_answer_callback(
    query: Any,
    text: str | None = None,
    show_alert: bool = False,
    cache_time: int = 0,
) -> bool:
    for _ in range(2):
        try:
            result = query.answer(
                text=text,
                show_alert=show_alert,
                cache_time=cache_time,
            )
            await _maybe_await(result)
            return True
        except FloodWait as e:
            await _handle_flood_wait(e)
            continue
        except Exception:
            return False
