import asyncio
import os
from collections import Counter

from pyrogram import errors, filters, types

from anony import app, config, db, lang, logger


broadcasting = asyncio.Lock()


@app.on_message(filters.command(["broadcast"]) & app.sudoers)
@lang.language()
async def _broadcast(_, message: types.Message):
    if not message.reply_to_message:
        return await message.reply_text(message.lang["gcast_usage"])
    if broadcasting.locked():
        return await message.reply_text(message.lang["gcast_active"])

    msg = message.reply_to_message
    copy = "-copy" in message.command
    groups = set() if "-nochat" in message.command else set(await db.get_chats())
    users = set(await db.get_users()) if "-user" in message.command else set()
    chats = sorted(groups | users)
    counts = Counter()
    failures = []
    sent = await message.reply_text(message.lang["gcast_start"])

    async with broadcasting:
        total = len(chats)
        for index, chat in enumerate(chats, start=1):
            delivered = False
            for attempt in range(max(0, config.BROADCAST_RETRY_LIMIT) + 1):
                try:
                    if copy:
                        await msg.copy(chat, reply_markup=msg.reply_markup)
                    else:
                        await msg.forward(chat)
                    counts["group" if chat in groups else "user"] += 1
                    delivered = True
                    break
                except errors.FloodWait as fw:
                    if attempt >= config.BROADCAST_RETRY_LIMIT:
                        failures.append((chat, f"FloodWait exhausted after {fw.value}s"))
                        break
                    await asyncio.sleep(fw.value + 1)
                except (
                    errors.ChatWriteForbidden,
                    errors.UserIsBlocked,
                    errors.PeerIdInvalid,
                    errors.ChatForbidden,
                ) as exc:
                    failures.append((chat, type(exc).__name__))
                    if config.BROADCAST_AUTO_LEAVE and chat in groups:
                        try:
                            await app.leave_chat(chat)
                            counts["auto_left"] += 1
                        except Exception:
                            logger.warning("Could not leave blocked group %s", chat)
                    break
                except Exception as exc:
                    failures.append((chat, type(exc).__name__))
                    logger.warning("Broadcast failed for %s: %s", chat, type(exc).__name__)
                    break

            if not delivered:
                counts["failed"] += 1
            if index % config.BROADCAST_PROGRESS_EVERY == 0 or index == total:
                try:
                    await sent.edit_text(
                        f"{message.lang['gcast_start']}\nProgress: {index}/{total}\n"
                        f"Groups: {counts['group']} | Users: {counts['user']}\n"
                        f"Failed: {counts['failed']}"
                    )
                except Exception:
                    pass
            await asyncio.sleep(0.2)

    report_lines = [f"chat_id={chat} error={reason}" for chat, reason in failures]
    if report_lines:
        report_path = "broadcast_errors.txt"
        try:
            with open(report_path, "w", encoding="utf-8") as fp:
                fp.write("\n".join(report_lines))
            await message.reply_document(
                report_path, caption=f"Failed destinations: {len(failures)}"
            )
        finally:
            try:
                os.remove(report_path)
            except OSError:
                pass

    final = message.lang["gcast_end"].format(counts["group"], counts["user"])
    final += f"\nFailed: {counts['failed']} | Auto-left: {counts['auto_left']}"
    await sent.edit_text(final)
