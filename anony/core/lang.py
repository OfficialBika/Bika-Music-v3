# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of AnonXMusic


import json
from functools import wraps
from pathlib import Path

from pyrogram import errors

from anony import db, logger

lang_codes = {
    "ar": "العربية",
    "de": "Deutsch",
    "en": "English",
    "es": "Español",
    "fr": "Français",
    "hi": "हिन्दी",
    "ja": "日本語",
    "my": "မြန်မာဘာသာ",
    "pa": "ਪੰਜਾਬੀ",
    "pt": "Português",
    "ru": "Русский",
    "tr": "Türkçe",
    "zh": "中文"
}


class Language:
    """
    Language class for managing multilingual support using JSON language files.
    """

    def __init__(self):
        self.lang_codes = lang_codes
        self.lang_dir = Path("anony/locales")
        self.languages = self.load_files()

    def load_files(self):
        languages = {}
        lang_files = {file.stem: file for file in self.lang_dir.glob("*.json")}
        for lang_code, lang_file in lang_files.items():
            with open(lang_file, "r", encoding="utf-8") as file:
                languages[lang_code] = json.load(file)
        logger.info(f"Loaded languages: {', '.join(languages.keys())}")
        return languages

    def _resolve(self, lang_code: str | None) -> str:
        code = str(lang_code or "").strip().lower()
        if code in self.languages:
            return code
        if "en" in self.languages:
            logger.warning("Unknown language code %r; falling back to en.", lang_code)
            return "en"
        if self.languages:
            fallback = next(iter(self.languages))
            logger.warning("Unknown language code %r; falling back to %s.", lang_code, fallback)
            return fallback
        raise RuntimeError("No language files were loaded from anony/locales.")

    async def get_lang(self, chat_id: int) -> dict:
        return self.languages[self._resolve(await db.get_lang(chat_id))]

    def get_languages(self) -> dict:
        files = {f.stem for f in self.lang_dir.glob("*.json")}
        return {code: self.lang_codes.get(code, code) for code in sorted(files)}

    def language(self):
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                fallen = next(
                    (
                        arg
                        for arg in args
                        if hasattr(arg, "chat") or hasattr(arg, "message")
                    ),
                    None,
                )

                if not fallen.from_user:
                    return

                if hasattr(fallen, "chat"):
                    chat = fallen.chat
                elif hasattr(fallen, "message"):
                    chat = fallen.message.chat

                if not chat: return

                if chat.id in db.blacklisted:
                    logger.info(f"Chat {chat.id} is blacklisted, leaving...")
                    return await chat.leave()

                lang_code = self._resolve(await db.get_lang(chat.id))
                lang_dict = self.languages[lang_code]

                setattr(fallen, "lang", lang_dict)
                try:
                    return await func(*args, **kwargs)
                except (errors.ChannelPrivate, errors.MessageIdInvalid, errors.MessageNotModified):
                    return
                except (
                    errors.Forbidden, errors.exceptions.Forbidden,
                    errors.ChatWriteForbidden, errors.exceptions.ChatWriteForbidden,
                ):
                    return

            return wrapper

        return decorator
