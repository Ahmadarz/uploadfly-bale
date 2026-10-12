"""پیش‌نمایش خودکار قبل از خرید. سیستم می‌سازد، نه فروشنده؛ پس فروشنده نمی‌تواند چیز دیگری نشان دهد.

عکس ← تار | ویدیو ← ۳ فریم تصادفی، کمی تار | PDF ← صفحه‌ی اول تار + تعداد صفحات
موزیک/ویس ← ۱۵ ثانیه از وسط | متن ← چند خط اول | گیف/ویدیوی دایره‌ای ← یک فریم تار
محتوای حساس تارتر می‌شود. فایل بالای ۲۰MB (محدودیت Bot API) ← فقط thumbnail خود تلگرام، تار.
"""
import asyncio
import html
import io
import json
import logging
import random
import re
import tempfile
from pathlib import Path

from aiogram import Bot
from aiogram.types import BufferedInputFile, InputMediaPhoto
from PIL import Image, ImageFilter

from app.db import Content

log = logging.getLogger(__name__)

MAX_DOWNLOAD = 20 * 1024 * 1024  # سقف دانلود Bot API
FRAMES = 3
AUDIO_SNIPPET = 15  # ثانیه
TEXT_PREVIEW_RATIO = 0.2
TEXT_PREVIEW_MAX = 300  # کاراکتر

# شعاع تاری به نسبت ضلع بزرگ تصویر
BLUR = {"photo": 0.025, "frame": 0.012, "page": 0.012}
BLUR_SENSITIVE = 0.06


def blur(data: bytes, strength: float) -> bytes:
    img = Image.open(io.BytesIO(data)).convert("RGB")
    img.thumbnail((800, 800))
    img = img.filter(ImageFilter.GaussianBlur(radius=max(img.size) * strength))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=70)
    return out.getvalue()


async def run(*cmd: str, timeout: int = 60) -> None:
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.DEVNULL,
                                                stderr=asyncio.subprocess.DEVNULL)
    try:
        await asyncio.wait_for(proc.wait(), timeout)
    except asyncio.TimeoutError:
        proc.kill()
        raise
    if proc.returncode != 0:
        raise RuntimeError(f"{cmd[0]} exited with {proc.returncode}")


def plain_text(c: Content) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", c.text or ""))


def text_snippet(c: Content) -> str:
    """چند خط اول متن؛ بقیه پنهان. برش روی مرز کلمه."""
    text = plain_text(c)
    limit = min(TEXT_PREVIEW_MAX, max(40, int(len(text) * TEXT_PREVIEW_RATIO)))
    if len(text) <= limit:
        limit = len(text) // 2  # متن کوتاه: فقط نیمه‌ی اول
    cut = text[:limit].rsplit(" ", 1)[0] if " " in text[:limit] else text[:limit]
    return cut.rstrip() + " …"


async def build(bot: Bot, c: Content, workdir: Path) -> dict:
    """فایل‌های پیش‌نمایش را می‌سازد: {"photos": [bytes], "voice": bytes, "text": str, "pages": int}."""
    if c.kind == "text":
        return {"text": text_snippet(c)}

    strength = BLUR_SENSITIVE if c.is_sensitive else None
    too_big = (c.file_size or 0) > MAX_DOWNLOAD
    if too_big:
        if not c.thumb_file_id:
            return {}
        thumb = await bot.download(c.thumb_file_id)
        return {"photos": [blur(thumb.read(), strength or BLUR["frame"])], "thumb_only": True}

    src = workdir / "src"
    await bot.download(c.file_id, destination=src)

    if c.kind == "photo":
        return {"photos": [blur(src.read_bytes(), strength or BLUR["photo"])]}

    if c.kind in ("video", "animation", "video_note"):
        count = FRAMES if c.kind == "video" else 1
        duration = max(c.duration or 1, 1)
        times = sorted(random.uniform(duration * 0.1, duration * 0.9) for _ in range(count))
        photos = []
        for i, t in enumerate(times):
            frame = workdir / f"f{i}.jpg"
            await run("ffmpeg", "-y", "-ss", f"{t:.2f}", "-i", str(src), "-frames:v", "1",
                      "-vf", "scale=640:-2", str(frame))
            photos.append(blur(frame.read_bytes(), strength or BLUR["frame"]))
        return {"photos": photos}

    if c.kind in ("audio", "voice"):
        duration = c.duration or 0
        start = random.uniform(duration * 0.3, max(duration * 0.3, duration * 0.7 - AUDIO_SNIPPET)) \
            if duration > AUDIO_SNIPPET * 2 else 0
        out = workdir / "snippet.ogg"
        await run("ffmpeg", "-y", "-ss", f"{start:.2f}", "-t", str(AUDIO_SNIPPET), "-i", str(src),
                  "-vn", "-ac", "1", "-c:a", "libopus", "-b:a", "48k", str(out))
        return {"voice": out.read_bytes()}

    if c.kind == "document" and (c.mime_type == "application/pdf" or (c.file_name or "").lower().endswith(".pdf")):
        import pymupdf
        doc = pymupdf.open(src)
        pages = doc.page_count
        png = doc[0].get_pixmap(dpi=80).tobytes("png")
        doc.close()
        return {"photos": [blur(png, strength or BLUR["page"])], "pages": pages}

    # بقیه‌ی فایل‌ها (zip، apk و ...): اگر thumbnail دارد همان، وگرنه فقط مشخصات
    if c.thumb_file_id:
        thumb = await bot.download(c.thumb_file_id)
        return {"photos": [blur(thumb.read(), strength or BLUR["frame"])], "thumb_only": True}
    return {}


async def create(bot: Bot, c: Content, chat_id: int, caption: str) -> None:
    """پیش‌نمایش را می‌سازد، یک بار برای فروشنده می‌فرستد (تا ببیند خریدار چه می‌بیند) و file_id ها را ذخیره می‌کند.
    خطا در ساخت پیش‌نمایش نباید جلوی فروش را بگیرد؛ در آن صورت فقط مشخصات نمایش داده می‌شود."""
    try:
        with tempfile.TemporaryDirectory() as tmp:
            built = await build(bot, c, Path(tmp))
    except Exception:
        log.exception("Preview failed for content %s", c.id)
        built = {}

    stored: dict = {k: built[k] for k in ("text", "pages", "thumb_only") if k in built}
    photos = built.get("photos") or []
    if len(photos) == 1:
        m = await bot.send_photo(chat_id, BufferedInputFile(photos[0], "preview.jpg"), caption=caption,
                                 protect_content=True, disable_notification=True)
        stored["photos"] = [m.photo[-1].file_id]
    elif photos:
        msgs = await bot.send_media_group(chat_id, [
            InputMediaPhoto(media=BufferedInputFile(p, f"preview{i}.jpg"), caption=caption if i == 0 else None)
            for i, p in enumerate(photos)], protect_content=True, disable_notification=True)
        stored["photos"] = [m.photo[-1].file_id for m in msgs]
    if built.get("voice"):
        m = await bot.send_voice(chat_id, BufferedInputFile(built["voice"], "preview.ogg"), caption=caption,
                                 protect_content=True, disable_notification=True)
        stored["voice"] = m.voice.file_id
    c.preview = json.dumps(stored) if stored else None


async def show(bot: Bot, c: Content, chat_id: int, caption: str) -> None:
    """پیش‌نمایش ذخیره‌شده را برای خریدار می‌فرستد (متن پیش‌نمایش داخل پیام پیشنهاد نمایش داده می‌شود)."""
    if not c.preview:
        return
    p = json.loads(c.preview)
    photos = p.get("photos") or []
    if len(photos) == 1:
        await bot.send_photo(chat_id, photos[0], caption=caption, protect_content=True)
    elif photos:
        await bot.send_media_group(chat_id, [InputMediaPhoto(media=f, caption=caption if i == 0 else None)
                                             for i, f in enumerate(photos)], protect_content=True)
    if p.get("voice"):
        await bot.send_voice(chat_id, p["voice"], caption=caption, protect_content=True)


def stored(c: Content) -> dict:
    return json.loads(c.preview) if c.preview else {}
