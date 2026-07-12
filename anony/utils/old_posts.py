"""Per-chat old-post cleanup policy with an environment default."""

from anony import config, db


async def old_post_clean_enabled(chat_id: int) -> bool:
    """
    Return the explicit per-chat setting when one exists.

    Chats that have never changed the setting inherit OLD_POST_CLEAN from .env,
    which is True by default. This keeps the existing Settings toggle useful:
    an admin can still explicitly turn cleanup OFF for one chat.
    """
    try:
        doc = await db.chatsdb.find_one({"_id": chat_id})
    except Exception:
        return bool(config.OLD_POST_CLEAN)

    if doc is not None and "auto_delete_play" in doc:
        return bool(doc.get("auto_delete_play"))
    return bool(config.OLD_POST_CLEAN)
