"""استخراج محتوا از پیام کاربر و ارسال دوباره‌ی آن."""
from datetime import datetime, timedelta, timezone

from aiogram import Bot
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Content, DeleteJob
from app.texts import T, human_wait


def extract_content(m: Message) -> dict | None:
    """مشخصات واقعی محتوا را از پیام تلگرام بیرون می‌کشد. اگر نوع پیام پشتیبانی نشود None برمی‌گرداند."""
    text = m.html_text or None  # متن یا کپشن با حفظ فرمت

    if m.text:
        return {"kind": "text", "text": text}

    if m.photo:
        p = m.photo[-1]  # بزرگ‌ترین سایز
        return {"kind": "photo", "file_id": p.file_id, "file_unique_id": p.file_unique_id,
                "file_size": p.file_size, "width": p.width, "height": p.height, "text": text}

    if m.video:
        v = m.video
        return {"kind": "video", "file_id": v.file_id, "file_unique_id": v.file_unique_id,
                "file_name": v.file_name, "mime_type": v.mime_type, "file_size": v.file_size,
                "duration": v.duration, "width": v.width, "height": v.height, "text": text, "thumb_file_id": v.thumbnail.file_id if v.thumbnail else None}

    if m.animation:
        a = m.animation
        return {"kind": "animation", "file_id": a.file_id, "file_unique_id": a.file_unique_id,
                "file_name": a.file_name, "mime_type": a.mime_type, "file_size": a.file_size,
                "duration": a.duration, "width": a.width, "height": a.height, "text": text, "thumb_file_id": a.thumbnail.file_id if a.thumbnail else None}

    if m.document:
        d = m.document
        return {"kind": "document", "file_id": d.file_id, "file_unique_id": d.file_unique_id,
                "file_name": d.file_name, "mime_type": d.mime_type, "file_size": d.file_size, "text": text, "thumb_file_id": d.thumbnail.file_id if d.thumbnail else None}

    if m.audio:
        a = m.audio
        return {"kind": "audio", "file_id": a.file_id, "file_unique_id": a.file_unique_id,
                "file_name": a.file_name, "mime_type": a.mime_type, "file_size": a.file_size,
                "duration": a.duration, "text": text, "thumb_file_id": a.thumbnail.file_id if a.thumbnail else None}

    if m.voice:
        v = m.voice
        return {"kind": "voice", "file_id": v.file_id, "file_unique_id": v.file_unique_id,
                "mime_type": v.mime_type, "file_size": v.file_size, "duration": v.duration, "text": text}

    if m.video_note:
        v = m.video_note
        return {"kind": "video_note", "file_id": v.file_id, "file_unique_id": v.file_unique_id,
                "file_size": v.file_size, "duration": v.duration, "width": v.length, "height": v.length, "thumb_file_id": v.thumbnail.file_id if v.thumbnail else None}

    return None


def view_seconds(c: Content) -> int:
    """زمان نمایش محتوای حساس قبل از حذف خودکار، بسته به نوع و مدت محتوا."""
    if c.duration:  # ویدیو، موزیک، ویس، گیف، ویدیوی دایره‌ای: مدت کامل + ۲ دقیقه
        return min(c.duration + 120, 3 * 3600)
    return {"photo": 60, "text": 120, "document": 300}.get(c.kind, 120)


async def send_content(bot: Bot, chat_id: int, c: Content) -> int:
    """محتوا را با file_id ذخیره‌شده دوباره ارسال می‌کند (بدون محدودیت حجم).
    پیش‌فرض محافظت‌شده است (بدون فوروارد، ذخیره و کپی) مگر فروشنده اجازه داده باشد. شناسه‌ی پیام را برمی‌گرداند."""
    kw = {"chat_id": chat_id, "protect_content": c.is_sensitive or not c.allow_save}
    cap = c.text

    if c.kind == "text":
        m = await bot.send_message(text=c.text, **kw)
    elif c.kind == "photo":
        m = await bot.send_photo(photo=c.file_id, caption=cap, **kw)
    elif c.kind == "video":
        m = await bot.send_video(video=c.file_id, caption=cap, **kw)
    elif c.kind == "animation":
        m = await bot.send_animation(animation=c.file_id, caption=cap, **kw)
    elif c.kind == "document":
        m = await bot.send_document(document=c.file_id, caption=cap, **kw)
    elif c.kind == "audio":
        m = await bot.send_audio(audio=c.file_id, caption=cap, **kw)
    elif c.kind == "voice":
        m = await bot.send_voice(voice=c.file_id, caption=cap, **kw)
    else:  # video_note
        m = await bot.send_video_note(video_note=c.file_id, **kw)
    return m.message_id


async def deliver(bot: Bot, chat_id: int, c: Content, session: AsyncSession, lang: str, mark: str | None = None) -> int:
    """ارسال محتوا به کاربر. محتوای حساس بعد از زمان نمایش خودکار پاک می‌شود؛ کاربر با باز کردن لینک دوباره می‌بیند.
    mark: واترمارک (یوزرنیم خریدار) روی عکس، اگر سازنده روشنش کرده. شناسه‌ی پیام محتوا را برمی‌گرداند."""
    message_id = None
    if mark:
        from app.creator import send_watermarked
        message_id = await send_watermarked(bot, chat_id, c, mark)
    if message_id is None:
        message_id = await send_content(bot, chat_id, c)
    if not c.is_sensitive:
        return message_id
    seconds = view_seconds(c)
    notice = await bot.send_message(chat_id, T(lang)["auto_delete_notice"].format(time=human_wait(seconds, lang)),
                                    disable_notification=True)
    delete_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=seconds)
    for mid in (message_id, notice.message_id):
        session.add(DeleteJob(bot_id=bot.id, chat_id=chat_id, message_id=mid, delete_at=delete_at))
    await session.commit()
    return message_id
