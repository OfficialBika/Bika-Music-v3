import requests
from anony import config

API = f"https://api.telegram.org/bot{config.BOT_TOKEN}"


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
    r = requests.post(f"{API}/{method}", json=payload, timeout=30)
    try:
        data = r.json()
    except Exception:
        data = {"ok": False, "raw": r.text}
    print(f"RAWTG {method}:", data, flush=True)
    return data


def send_message(
    chat_id: int,
    text: str,
    reply_markup=None,
    parse_mode: str = "HTML",
    disable_web_page_preview: bool = False,
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
