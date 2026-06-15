# Stable raw Telegram Bot API helper.
#
# This module intentionally keeps sync function signatures because existing
# code and rawsafe.py call these functions directly. Call these through
# asyncio.to_thread(...) inside async loops when high frequency is expected.

from __future__ import annotations

import requests

from anony import config

API = f"https://api.telegram.org/bot{config.BOT_TOKEN}"
REQUEST_TIMEOUT = 12


IGNORABLE_EDIT_ERRORS = (
    "message to edit not found",
    "there is no caption in the message to edit",
    "there is no text in the message to edit",
    "message content and reply markup are exactly the same",
    "message is not modified",
    "message id invalid",
    "message can't be edited",
    "specified new message content and reply markup are exactly the same",
)


def _is_ignorable_edit_error(method: str, data: dict) -> bool:
    if not isinstance(data, dict):
        return False

    if data.get("ok") is not False:
        return False

    if not method.startswith("editMessage"):
        return False

    desc = str(data.get("description", "")).lower()
    return any(err in desc for err in IGNORABLE_EDIT_ERRORS)


def _to_plain(obj):
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, list):
        return [_to_plain(x) for x in obj]
    if isinstance(obj, tuple):
        return [_to_plain(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _to_plain(v) for k, v in obj.items() if v is not None}

    if hasattr(obj, "inline_keyboard"):
        return {"inline_keyboard": _to_plain(obj.inline_keyboard)}

    if hasattr(obj, "text") and (
        hasattr(obj, "callback_data")
        or hasattr(obj, "url")
        or hasattr(obj, "copy_text")
    ):
        data = {}
        for key in [
            "text",
            "callback_data",
            "url",
            "web_app",
            "login_url",
            "user_id",
            "switch_inline_query",
            "switch_inline_query_current_chat",
            "switch_inline_query_chosen_chat",
            "copy_text",
            "callback_game",
            "pay",
            "style",
            "icon_custom_emoji_id",
        ]:
            if hasattr(obj, key):
                val = getattr(obj, key)
                if val is not None:
                    data[key] = _to_plain(val)
        return data

    if hasattr(obj, "__dict__"):
        return {
            k: _to_plain(v)
            for k, v in obj.__dict__.items()
            if not k.startswith("_") and v is not None
        }

    return obj


def _post(method: str, payload: dict):
    try:
        response = requests.post(
            f"{API}/{method}",
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )
        try:
            data = response.json()
        except Exception:
            data = {
                "ok": False,
                "description": "Non-JSON response from Telegram Bot API",
                "status_code": response.status_code,
                "raw": response.text[:500],
            }
    except requests.RequestException as e:
        data = {
            "ok": False,
            "description": f"Request failed: {type(e).__name__}: {e}",
        }

    if _is_ignorable_edit_error(method, data):
        print(
            f"RAWTG {method}: ignored harmless edit error: {data.get('description')}",
            flush=True,
        )
        return {"ok": True, "ignored": True, "raw": data}

    # Avoid noisy logs for successful high-frequency timer edits.
    if data.get("ok") is False:
        print(f"RAWTG {method} ERROR:", data, flush=True)

    return data


def send_message(
    chat_id: int,
    text: str,
    reply_markup=None,
    parse_mode: str = "HTML",
    disable_web_page_preview: bool = True,
):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": disable_web_page_preview,
    }
    if parse_mode is not None:
        payload["parse_mode"] = parse_mode
    if reply_markup is not None:
        payload["reply_markup"] = _to_plain(reply_markup)
    return _post("sendMessage", payload)


def send_photo(
    chat_id: int,
    photo,
    caption: str | None = None,
    reply_markup=None,
    parse_mode: str = "HTML",
    has_spoiler: bool | None = None,
):
    payload = {
        "chat_id": chat_id,
        "photo": photo,
    }
    if caption is not None:
        payload["caption"] = caption
    if parse_mode is not None:
        payload["parse_mode"] = parse_mode
    if reply_markup is not None:
        payload["reply_markup"] = _to_plain(reply_markup)
    if has_spoiler is not None:
        payload["has_spoiler"] = has_spoiler
    return _post("sendPhoto", payload)


def edit_message_text(
    chat_id: int,
    message_id: int,
    text: str,
    reply_markup=None,
    parse_mode: str = "HTML",
    disable_web_page_preview: bool = False,
):
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "disable_web_page_preview": disable_web_page_preview,
    }
    if parse_mode is not None:
        payload["parse_mode"] = parse_mode
    if reply_markup is not None:
        payload["reply_markup"] = _to_plain(reply_markup)
    return _post("editMessageText", payload)


def edit_message_caption(
    chat_id: int,
    message_id: int,
    caption: str,
    reply_markup=None,
    parse_mode: str = "HTML",
):
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "caption": caption,
    }
    if parse_mode is not None:
        payload["parse_mode"] = parse_mode
    if reply_markup is not None:
        payload["reply_markup"] = _to_plain(reply_markup)
    return _post("editMessageCaption", payload)


def edit_message_reply_markup(chat_id: int, message_id: int, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
    }
    if reply_markup is not None:
        payload["reply_markup"] = _to_plain(reply_markup)
    return _post("editMessageReplyMarkup", payload)
