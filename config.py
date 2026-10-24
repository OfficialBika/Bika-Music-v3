from os import getenv
from dotenv import load_dotenv

load_dotenv()


def _env_bool(name: str, default: bool = False) -> bool:
    value = getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on", "enable", "enabled"}


def _env_int(name: str, default: int, minimum: int | None = None) -> int:
    try:
        value = int(getenv(name, str(default)).strip())
    except (TypeError, ValueError, AttributeError):
        value = default
    if minimum is not None:
        value = max(minimum, value)
    return value


class Config:
    def __init__(self):
        self.API_ID = _env_int("API_ID", 0, minimum=0)
        self.API_HASH = getenv("API_HASH")

        self.BOT_TOKEN = getenv("BOT_TOKEN")
        self.MONGO_URL = getenv("MONGO_URL")

        self.LOGGER_ID = _env_int("LOGGER_ID", 0)
        owner_ids = []
        for raw_id in getenv("OWNER_ID", "").split(","):
            raw_id = raw_id.strip()
            if not raw_id:
                continue
            try:
                owner_ids.append(int(raw_id))
            except ValueError:
                continue
        self.OWNER_ID = owner_ids

        self.DURATION_LIMIT = _env_int("DURATION_LIMIT", 120, minimum=1) * 60
        self.QUEUE_LIMIT = _env_int("QUEUE_LIMIT", 25, minimum=1)
        self.PLAYLIST_LIMIT = _env_int("PLAYLIST_LIMIT", 25, minimum=1)

        self.SESSION1 = getenv("SESSION", None)
        self.SESSION2 = getenv("SESSION2", None)
        self.SESSION3 = getenv("SESSION3", None)

        self.SUPPORT_CHANNEL = getenv(
            "SUPPORT_CHANNEL", "https://t.me/MyanmarBotCommunity"
        )
        self.SUPPORT_CHAT = getenv(
            "SUPPORT_CHAT", "https://t.me/Myanmarbotcommunitychat"
        )

        self.AUTO_LEAVE = _env_bool("AUTO_LEAVE", False)
        self.AUTO_END = _env_bool("AUTO_END", False)

        self.THUMB_GEN = _env_bool("THUMB_GEN", True)
        self.VIDEO_PLAY = _env_bool("VIDEO_PLAY", True)

        self.LANG_CODE = (getenv("LANG_CODE", "en") or "en").strip().lower()

        self.COOKIES_URL = [
            url
            for url in getenv("COOKIES_URL", "").split(" ")
            if url and "batbin.me" in url
        ]
        self.DEFAULT_THUMB = getenv(
            "DEFAULT_THUMB",
            "https://graph.org/file/57c13c2b739bc2443c4f3-6a4fa57e870d529794.jpg",
        )
        self.PING_IMG = getenv(
            "PING_IMG",
            "https://graph.org/file/f4d7fcd322e9b4ff71875-1bd81abda440766e3d.jpg",
        )
        self.START_IMG = getenv(
            "START_IMG",
            "https://graph.org/file/57c13c2b739bc2443c4f3-6a4fa57e870d529794.jpg",
        )
        self.HELP_IMG = getenv(
            "HELP_IMG",
            "https://graph.org/file/e78cfe5618234c9d3b553-0a5d4efe2c378f50c3.jpg",
        )

        # Queue notification branding.
        self.MUSIC_BRAND_TEXT = (
            getenv("MUSIC_BRAND_TEXT", "Ｂɪᴋᴀ ꭙ Ｍᴜsɪᴄ").strip()
            or "Ｂɪᴋᴀ ꭙ Ｍᴜsɪᴄ"
        )

        # Start-message owner button. OWNER_USERNAME may include or omit @.
        self.OWNER_USERNAME = getenv(
            "OWNER_USERNAME", "Official_Bika"
        ).strip().lstrip("@")
        self.OWNER_BUTTON_TEXT = getenv("OWNER_BUTTON_TEXT", "Owner").strip() or "Owner"
        self.OWNER_BUTTON_ENABLED = _env_bool("OWNER_BUTTON_ENABLED", True)

        # Automatically delete queued-song notification posts.
        self.OLD_POST_CLEAN = _env_bool("OLD_POST_CLEAN", True)
        self.OLD_POST_CLEAN_DELAY = _env_int(
            "OLD_POST_CLEAN_DELAY", 10, minimum=1
        )

    def check(self):
        missing = [
            var
            for var in [
                "API_ID",
                "API_HASH",
                "BOT_TOKEN",
                "MONGO_URL",
                "LOGGER_ID",
                "OWNER_ID",
                "SESSION1",
            ]
            if not getattr(self, var)
        ]
        if missing:
            raise SystemExit(
                f"Missing required environment variables: {', '.join(missing)}"
            )
