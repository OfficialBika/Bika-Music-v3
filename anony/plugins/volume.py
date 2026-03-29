from pyrogram import filters, types

from anony import anon, app, db, lang
from anony.helpers import buttons, can_manage_vc


@app.on_message(filters.command(["volume", "vol"]) & filters.group & ~app.bl_users)
@lang.language()
@can_manage_vc
async def volume_cmd(_, m: types.Message):
    if not await db.get_call(m.chat.id):
        return await m.reply_text(m.lang["not_playing"])

    if len(m.command) < 2:
        return await m.reply_text("Usage:\n/volume 1-200")

    try:
        vol = int(m.command[1])
    except ValueError:
        return await m.reply_text("Please give a number.\nExample: /volume 100")

    if vol < 1 or vol > 200:
        return await m.reply_text("Volume must be between 1 and 200.")

    ok = await anon.volume(m.chat.id, vol)
    if not ok:
        return await m.reply_text("Failed to change volume.")

    await m.reply_text(f"🔊 Volume set to {vol}%")
