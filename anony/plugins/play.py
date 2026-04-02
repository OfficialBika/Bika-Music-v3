# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of AnonXMusic


from pathlib import Path
import html
import inspect

from pyrogram import enums, filters, types

from anony import anon, app, config, db, lang, queue, tg, yt
from anony.helpers import buttons, utils, rawtg
from anony.helpers._play import checkUB


async def _maybe_await(result):
    if inspect.isawaitable(result):
        return await result
    return result


async def _send_raw_text_with_buttons(
    chat_id: int,
    text: str,
    reply_markup,
):
    result = rawtg.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=reply_markup,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
    return await _maybe_await(result)


def playlist_to_queue(chat_id: int, tracks: list) -> str:
    text = "<blockquote expandable>"
    for track in tracks:
        pos = queue.add(chat_id, track)
        text += f"<b>{pos}.</b> {html.escape(track.title)}\n"
    text = text[:1948] + "</blockquote>"
    return text


@app.on_message(
    filters.command(["play", "playforce", "vplay", "vplayforce"])
    & filters.group
    & ~app.bl_users
)
@lang.language()
@checkUB
async def play_hndlr(
    _,
    m: types.Message,
    force: bool = False,
    m3u8: bool = False,
    video: bool = False,
    url: str = None,
) -> None:
    sent = await m.reply_text(m.lang["play_searching"])
    file = None
    media = tg.get_media(m.reply_to_message) if m.reply_to_message else None
    tracks = []

    requester_name = html.escape(m.from_user.first_name or "User")
    requester_link = f'tg://user?id={m.from_user.id}'
    requester_mention = f'<a href="{requester_link}">{requester_name}</a>'

    if media:
        setattr(sent, "lang", m.lang)
        file = await tg.download(m.reply_to_message, sent)

    elif m3u8:
        file = await tg.process_m3u8(url, sent.id, video)

    elif url:
        if "playlist" in url:
            await sent.edit_text(m.lang["playlist_fetch"])
            tracks = await yt.playlist(
                config.PLAYLIST_LIMIT, requester_mention, url, video
            )

            if not tracks:
                return await sent.edit_text(m.lang["playlist_error"])

            file = tracks[0]
            tracks.remove(file)
            file.message_id = sent.id
        else:
            file = await yt.search(url, sent.id, video=video)

        if not file:
            return await sent.edit_text(
                m.lang["play_not_found"].format(config.SUPPORT_CHAT)
            )

    elif len(m.command) >= 2:
        query = " ".join(m.command[1:])
        file = await yt.search(query, sent.id, video=video)
        if not file:
            return await sent.edit_text(
                m.lang["play_not_found"].format(config.SUPPORT_CHAT)
            )

    if not file:
        return await sent.edit_text(m.lang["play_usage"])

    if file.duration_sec > config.DURATION_LIMIT:
        return await sent.edit_text(
            m.lang["play_duration_limit"].format(config.DURATION_LIMIT // 60)
        )

    if await db.is_logger():
        await utils.play_log(m, sent.link, file.title, file.duration)

    file.user = requester_mention

    if force:
        queue.force_add(m.chat.id, file)
    else:
        position = queue.add(m.chat.id, file)

        if position != 0 or await db.get_call(m.chat.id):
            try:
                await sent.delete()
            except Exception:
                pass

            song_link = html.escape(
                getattr(file, "url", None) or url or "https://t.me/Official_Bika"
            )
            song_title = html.escape(file.title or "Unknown")

            text = (
                f'<b><tg-emoji emoji-id="5361979846845014099">💃</tg-emoji> Ｂɪᴋᴀ ꭙ Ｍᴜsɪᴄ</b>\n\n'
                f'<blockquote><b>{position}</b> ခုမြောက် <b>queue</b> ထဲသို့ ထည့်ပြီးပါပြီ</blockquote>\n\n'
                f'<b><tg-emoji emoji-id="5990337934526517811">🎶</tg-emoji> သီချင်း</b> : '
                f'<a href="{song_link}">{song_title}</a>\n\n'
                f'<b><tg-emoji emoji-id="5316615057939897832">⏰</tg-emoji> ကြာချိန်</b> : {file.duration}\n\n'
                f'<b><tg-emoji emoji-id="6154522383790114334">😅</tg-emoji> တောင်းဆိုသူ</b> : '
                f'{requester_mention}'
            )

            result = await _send_raw_text_with_buttons(
                chat_id=m.chat.id,
                text=text,
                reply_markup=buttons.play_queued(
                    m.chat.id, file.id, m.lang["play_now"]
                ),
            )

            if isinstance(result, dict) and result.get("ok") is False:
                print(f"RAW PLAY QUEUE SEND ERROR: {result}")
                await m.reply_text(
                    text=text,
                    reply_markup=buttons.play_queued(
                        m.chat.id, file.id, m.lang["play_now"]
                    ),
                    parse_mode=enums.ParseMode.HTML,
                    disable_web_page_preview=True,
                )

            if tracks:
                added = playlist_to_queue(m.chat.id, tracks)
                await app.send_message(
                    chat_id=m.chat.id,
                    text=m.lang["playlist_queued"].format(len(tracks)) + added,
                    parse_mode=enums.ParseMode.HTML,
                    disable_web_page_preview=True,
                )
            return

    if not file.file_path:
        fname = f"downloads/{file.id}.{'mp4' if video else 'webm'}"
        if Path(fname).exists():
            file.file_path = fname
        else:
            await sent.edit_text(m.lang["play_downloading"])
            file.file_path = await yt.download(file.id, video=video)

    await anon.play_media(chat_id=m.chat.id, message=sent, media=file)

    if not tracks:
        return

    added = playlist_to_queue(m.chat.id, tracks)
    await app.send_message(
        chat_id=m.chat.id,
        text=m.lang["playlist_queued"].format(len(tracks)) + added,
        parse_mode=enums.ParseMode.HTML,
        disable_web_page_preview=True,
    )
