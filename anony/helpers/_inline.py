from pyrogram import types

from anony import app, config, lang
from anony.core.lang import lang_codes


class Inline:
    def __init__(self):
        self.ikm = types.InlineKeyboardMarkup
        self.ikb = types.InlineKeyboardButton

    def _clean_btn_text(self, text: str) -> str:
        if not isinstance(text, str):
            return str(text)
        for tag in [
            "<b>", "</b>",
            "<u>", "</u>",
            "<i>", "</i>",
            "<code>", "</code>",
            "<blockquote>", "</blockquote>",
            "<blockquote expandable>", "</blockquote expandable>",
        ]:
            text = text.replace(tag, "")
        return text.strip()

    def cancel_dl(self, text) -> types.InlineKeyboardMarkup:
        return self.ikm([
            [self.ikb(text=self._clean_btn_text(text), callback_data="cancel_dl", style="danger")]
        ])

    def controls(
        self,
        chat_id: int,
        status: str = None,
        timer: str = None,
        remove: bool = False,
    ) -> types.InlineKeyboardMarkup:
        keyboard = []

        if status:
            keyboard.append(
                [
                    self.ikb(
                        text=self._clean_btn_text(status),
                        callback_data=f"controls status {chat_id}",
                        style="primary",
                    )
                ]
            )
        elif timer:
            keyboard.append(
                [
                    self.ikb(
                        text=self._clean_btn_text(timer),
                        callback_data=f"controls status {chat_id}",
                        style="primary",
                    )
                ]
            )

        if not remove:
            keyboard.append(
                [
                    self.ikb(text="▷", callback_data=f"controls resume {chat_id}", style="success"),
                    self.ikb(text="II", callback_data=f"controls pause {chat_id}", style="danger"),
                    self.ikb(text="⥁", callback_data=f"controls replay {chat_id}", style="primary"),
                    self.ikb(text="‣‣I", callback_data=f"controls skip {chat_id}", style="primary"),
                    self.ikb(text="▢", callback_data=f"controls stop {chat_id}", style="danger"),
                ]
            )
            keyboard.append(
                [
                    self.ikb(
                        text="✖ Close",
                        callback_data=f"controls close {chat_id}",
                        style="danger",
                    )
                ]
            )

        return self.ikm(keyboard)

    def help_markup(
        self, _lang: dict, back: bool = False
    ) -> types.InlineKeyboardMarkup:
        if back:
            rows = [
                [
                    self.ikb(text="◁ Back", callback_data="help back", style="primary"),
                    self.ikb(text="Close", callback_data="help close", style="danger"),
                ]
            ]
        else:
            items = [
                ("Admins", "admins"),
                ("Auth", "auth"),
                ("Blacklist", "blist"),
                ("Language", "lang"),
                ("Ping", "ping"),
                ("Play", "play"),
                ("Queue", "queue"),
                ("Stats", "stats"),
                ("Sudoers", "sudo"),
            ]
            buttons = [
                self.ikb(
                    text=label,
                    callback_data=f"help {cb}",
                    style="primary",
                )
                for label, cb in items
            ]
            rows = [buttons[i:i + 3] for i in range(0, len(buttons), 3)]

        return self.ikm(rows)

    def lang_markup(self, _lang: str) -> types.InlineKeyboardMarkup:
        langs = lang.get_languages()

        buttons = [
            self.ikb(
                text=self._clean_btn_text(f"{name} ({code}) {'✔️' if code == _lang else ''}"),
                callback_data=f"lang_change {code}",
                style="primary" if code == _lang else "success",
            )
            for code, name in langs.items()
        ]
        rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
        return self.ikm(rows)

    def ping_markup(self, text: str) -> types.InlineKeyboardMarkup:
        return self.ikm([
            [self.ikb(text=self._clean_btn_text(text), url=config.SUPPORT_CHAT, style="primary")]
        ])

    def play_queued(
        self, chat_id: int, item_id: str, _text: str
    ) -> types.InlineKeyboardMarkup:
        return self.ikm(
            [
                [
                    self.ikb(
                        text=self._clean_btn_text(_text),
                        callback_data=f"controls force {chat_id} {item_id}",
                        style="success",
                    )
                ],
                [
                    self.ikb(
                        text="📋 Queue List",
                        callback_data=f"queue {chat_id}",
                        style="primary",
                    ),
                    self.ikb(
                        text="✖ Close",
                        callback_data=f"controls close {chat_id}",
                        style="danger",
                    ),
                ],
            ]
        )

    def queue_markup(
        self, chat_id: int, _text: str, playing: bool
    ) -> types.InlineKeyboardMarkup:
        _action = "pause" if playing else "resume"
        _style = "success" if playing else "primary"
        return self.ikm(
            [[
                self.ikb(
                    text=self._clean_btn_text(_text),
                    callback_data=f"controls {_action} {chat_id} q",
                    style=_style,
                )
            ]]
        )

    def settings_markup(
        self,
        lang: dict,
        admin_only: bool,
        cmd_delete: bool,
        language: str,
        chat_id: int,
        auto_delete_old_posts: bool = False,
    ) -> types.InlineKeyboardMarkup:
        auto_delete_label = self._clean_btn_text(
            str(lang.get("auto_delete_old_posts", "Auto Delete Old Posts")) + " ➜"
        )
        auto_delete_status = "ON" if auto_delete_old_posts else "OFF"

        return self.ikm(
            [
                [
                    self.ikb(
                        text=self._clean_btn_text(lang["play_mode"] + " ➜"),
                        callback_data="settings",
                        style="primary",
                    ),
                    self.ikb(
                        text="ON" if admin_only else "OFF",
                        callback_data="settings play",
                        style="success" if admin_only else "danger",
                    ),
                ],
                [
                    self.ikb(
                        text=self._clean_btn_text(lang["cmd_delete"] + " ➜"),
                        callback_data="settings",
                        style="primary",
                    ),
                    self.ikb(
                        text="ON" if cmd_delete else "OFF",
                        callback_data="settings delete",
                        style="success" if cmd_delete else "danger",
                    ),
                ],
                [
                    self.ikb(
                        text=auto_delete_label,
                        callback_data="settings",
                        style="primary",
                    ),
                    self.ikb(
                        text=auto_delete_status,
                        callback_data="settings autodel",
                        style="success" if auto_delete_old_posts else "danger",
                    ),
                ],
                [
                    self.ikb(
                        text=self._clean_btn_text(lang["language"] + " ➜"),
                        callback_data="settings",
                        style="primary",
                    ),
                    self.ikb(
                        text=self._clean_btn_text(lang_codes[language]),
                        callback_data="language",
                        style="success",
                    ),
                ],
            ]
        )

    def start_key(
        self, lang: dict, private: bool = False
    ) -> types.InlineKeyboardMarkup:
        rows = [
            [
                self.ikb(
                    text=self._clean_btn_text(lang["add_me"]),
                    url=f"https://t.me/{app.username}?startgroup=true",
                    style="primary",
                )
            ],
            [
                self.ikb(
                    text=self._clean_btn_text(lang["help"]),
                    callback_data="help",
                    style="success",
                )
            ],
            [
                self.ikb(
                    text=self._clean_btn_text(lang["support"]),
                    url=config.SUPPORT_CHAT,
                    style="primary",
                ),
                self.ikb(
                    text=self._clean_btn_text(lang["channel"]),
                    url=config.SUPPORT_CHANNEL,
                    style="primary",
                ),
            ],
        ]

        if private:
            if config.OWNER_BUTTON_ENABLED and config.OWNER_USERNAME:
                rows.append(
                    [
                        self.ikb(
                            text=self._clean_btn_text(config.OWNER_BUTTON_TEXT),
                            url=f"https://t.me/{config.OWNER_USERNAME}",
                            style="success",
                        )
                    ]
                )
        else:
            rows += [
                [
                    self.ikb(
                        text=self._clean_btn_text(lang["language"]),
                        callback_data="language",
                        style="success",
                    )
                ]
            ]

        return self.ikm(rows)

    def yt_key(self, link: str) -> types.InlineKeyboardMarkup:
        return self.ikm(
            [
                [
                    self.ikb(text="❐", copy_text=link, style="success"),
                    self.ikb(text="Youtube", url=link, style="primary"),
                ],
            ]
        )
