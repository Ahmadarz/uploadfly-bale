"""ظاهر ویترین (مثل Linktree): تم، بنر و لوگو.

لوگو مال کل فروشگاه است (Seller.logo). تم و بنر برای هر ویترین جداست؛ ویترین اصلی روی خود Seller.
عکس آپلودی هرگز همان‌طور که آمده نگه داشته نمی‌شود: با Pillow باز، کوچک و دوباره JPEG می‌شود
(متادیتا مثل مکان GPS پاک می‌شود و فایل‌های جعلی/خراب رد می‌شوند).
"""
import io
import json
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit, urlunsplit

import segno
from PIL import Image as PILImage
from PIL import ImageOps
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Image, Seller, Showcase

THEMES = ("soft", "sunset", "aurora", "noir")  # soft = پیش‌فرض (روشن/تیره‌ی خود تلگرام)

# استایل: فقط گزینه‌های آماده (هر ترکیبی خوب و خوانا درمی‌آید؛ کد/رنگ دلخواه پذیرفته نمی‌شود)
STYLE_CHOICES = {
    "card": ("round", "sharp", "pill", "polaroid"),
    "layout": ("feed", "grid2", "grid3", "list"),
    "accent": ("auto", "violet", "rose", "orange", "green", "blue", "gold"),
    "buttons": ("fill", "solid", "outline"),
    "header": ("cover", "center"),            # با بنر / بدون بنر، لوگوی بزرگ وسط (مثل Linktree)
    "font": ("classic", "bold", "light", "plex"),  # فقط فونت‌هایی که روی سرور خودمان هست (گوگل‌فونت در ایران بسته است)
}
STYLE_SWITCHES = ("stats", "others", "cats", "links")  # بخش‌هایی که فروشنده روشن/خاموش می‌کند
STYLE_DEFAULT = {"card": "round", "layout": "feed", "accent": "auto", "buttons": "fill", "header": "cover",
                 "font": "classic", "pinned": None,
                 **{k: True for k in STYLE_SWITCHES}}

# لینک شبکه‌های اجتماعی (مثل Linktree): فقط https و فقط دامنه‌ی همان شبکه
SOCIAL_HOSTS = {
    "instagram": ("instagram.com",), "telegram": ("t.me", "telegram.me"), "youtube": ("youtube.com", "youtu.be"),
    "x": ("x.com", "twitter.com"), "tiktok": ("tiktok.com",), "website": None,
}
SOCIAL_MAX_URL = 200
IMAGE_MAX_BYTES = 6 * 1024 * 1024
# بنر پهن (۳:۱ روی گوشی) و لوگوی مربع
SIZES = {"cover": (1500, 600), "logo": (512, 512), "background": (1080, 1920)}
PILImage.MAX_IMAGE_PIXELS = 40_000_000  # جلوی «بمب تصویری» (عکس کوچک با ابعاد غول‌آسا)


def process_image(raw: bytes, kind: str) -> bytes | None:
    """عکس معتبر → JPEG تمیز در اندازه‌ی مناسب؛ هر چیز دیگر → None."""
    if kind not in SIZES or not raw or len(raw) > IMAGE_MAX_BYTES:
        return None
    try:
        with PILImage.open(io.BytesIO(raw)) as im:
            if im.format not in ("JPEG", "PNG", "WEBP", "HEIF", "MPO"):
                return None
            im = ImageOps.exif_transpose(im).convert("RGB")
            w, h = SIZES[kind]
            im = _cover(im, w, h) if kind == "cover" else ImageOps.fit(im, (w, h), PILImage.LANCZOS)
            out = io.BytesIO()
            im.save(out, "JPEG", quality=84, optimize=True, progressive=True)
            return out.getvalue()
    except (OSError, ValueError, PILImage.DecompressionBombError, SyntaxError):
        return None


def process_story(raw: bytes) -> bytes | None:
    """کارت استوری: فقط JPEG/PNG واقعی با اندازه‌ی استوری؛ دوباره ساخته می‌شود."""
    if not raw or len(raw) > IMAGE_MAX_BYTES:
        return None
    try:
        with PILImage.open(io.BytesIO(raw)) as im:
            if im.format not in ("JPEG", "PNG") or im.size != (1080, 1920):
                return None
            out = io.BytesIO()
            im.convert("RGB").save(out, "JPEG", quality=92)
            return out.getvalue()
    except (OSError, ValueError, PILImage.DecompressionBombError, SyntaxError):
        return None


def _cover(im: PILImage.Image, w: int, h: int) -> PILImage.Image:
    """بنر: نسبت ۵:۲ از وسط عکس، بدون بزرگ کردن عکس کوچک."""
    fitted = ImageOps.fit(im, (w, h), PILImage.LANCZOS)
    if im.width < w:
        scale = im.width / w
        fitted = fitted.resize((max(1, int(w * scale)), max(1, int(h * scale))), PILImage.LANCZOS)
    return fitted


UPLOADS_PER_DAY = 40  # سقف آپلود عکس هر فروشنده در ۲۴ ساعت (جلوی پر کردن دیتابیس)


async def upload_allowed(session: AsyncSession, owner_id: int) -> bool:
    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1)
    n = await session.scalar(select(func.count(Image.id)).where(Image.owner_id == owner_id, Image.created_at >= since))
    return (n or 0) < UPLOADS_PER_DAY


async def cleanup_orphans(session: AsyncSession) -> int:
    """عکس‌هایی که آپلود شده‌اند ولی بیش از یک روز است به هیچ ویترینی وصل نیستند، پاک می‌شوند."""
    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1)
    used = set()
    for col in (Seller.logo, Seller.cover, Seller.background, Showcase.cover, Showcase.background):
        used |= {x for x in (await session.scalars(select(col).where(col.is_not(None)))).all()}
    old = (await session.scalars(select(Image.id).where(Image.created_at < since))).all()
    gone = [i for i in old if i not in used]
    if gone:
        await session.execute(delete(Image).where(Image.id.in_(gone)))
        await session.commit()
    return len(gone)


async def save_image(session: AsyncSession, owner_id: int, data: bytes) -> str:
    image = Image(id=secrets.token_urlsafe(12)[:16], owner_id=owner_id, data=data)
    session.add(image)
    await session.flush()
    return image.id


async def drop_if_unused(session: AsyncSession, image_id: str | None) -> None:
    """عکس قبلی بعد از عوض شدن، اگر جای دیگری استفاده نشده، پاک می‌شود."""
    if not image_id:
        return
    used = await session.scalar(select(Seller.id).where(or_(
        Seller.logo == image_id, Seller.cover == image_id, Seller.background == image_id)))
    used = used or await session.scalar(select(Showcase.id).where(or_(
        Showcase.cover == image_id, Showcase.background == image_id)))
    if not used:
        image = await session.get(Image, image_id)
        if image is not None:
            await session.delete(image)


async def owned_image(session: AsyncSession, owner_id: int, image_id) -> Image | None:
    if not isinstance(image_id, str) or not image_id:
        return None
    image = await session.get(Image, image_id)
    return image if image is not None and image.owner_id == owner_id else None


def load_json(text: str | None, default):
    try:
        value = json.loads(text) if text else default
    except ValueError:
        return default
    return value if isinstance(value, type(default)) else default


def style_of(holder) -> dict:
    """استایل ذخیره‌شده + پیش‌فرض‌ها (کلیدهای ناشناخته یا قدیمی دور ریخته می‌شوند)."""
    saved = load_json(holder.style, {})
    out = dict(STYLE_DEFAULT)
    for key, choices in STYLE_CHOICES.items():
        if saved.get(key) in choices:
            out[key] = saved[key]
    for key in STYLE_SWITCHES:
        if isinstance(saved.get(key), bool):
            out[key] = saved[key]
    if isinstance(saved.get("pinned"), int) and not isinstance(saved.get("pinned"), bool):
        out["pinned"] = saved["pinned"]
    return out


def merge_style(holder, patch) -> dict | str:
    """تغییر بخشی از استایل؛ خروجی استایل کامل، یا کد خطا. pinned جدا در web بررسی می‌شود."""
    if not isinstance(patch, dict):
        return "bad_style"
    out = style_of(holder)
    for key, value in patch.items():
        if key in STYLE_CHOICES and value in STYLE_CHOICES[key]:
            out[key] = value
        elif key in STYLE_SWITCHES and isinstance(value, bool):
            out[key] = value
        elif key == "pinned" and (value is None or (isinstance(value, int) and not isinstance(value, bool))):
            out[key] = value
        else:
            return "bad_style"
    return out


def clean_links(value) -> list[dict] | str:
    """[{"kind": "instagram", "url": "https://instagram.com/x"}, ...] → فهرست تمیز، یا کد خطا."""
    if not isinstance(value, list) or len(value) > len(SOCIAL_HOSTS):
        return "bad_links"
    out, seen = [], set()
    for item in value:
        if not isinstance(item, dict) or item.get("kind") not in SOCIAL_HOSTS or item["kind"] in seen:
            return "bad_links"
        url = str(item.get("url") or "").strip()
        if not url:
            continue
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        parts = urlsplit(url)
        host = (parts.hostname or "").lower().removeprefix("www.").removeprefix("m.")
        allowed = SOCIAL_HOSTS[item["kind"]]
        if (len(url) > SOCIAL_MAX_URL or parts.scheme != "https" or not host or "." not in host or parts.username
                or any(c in url for c in '"<> \\') or (allowed and host not in allowed)):
            return "bad_link_" + item["kind"]
        seen.add(item["kind"])
        out.append({"kind": item["kind"], "url": urlunsplit(("https", parts.netloc, parts.path, parts.query, ""))})
    return out


def look_json(seller: Seller, sc: Showcase | None = None) -> dict:
    holder = sc if sc is not None else seller
    return {"theme": holder.theme if holder.theme in THEMES else "soft", "cover": holder.cover, "logo": seller.logo,
            "background": holder.background,
            "style": style_of(holder), "links": load_json(seller.links, [])}


def qr_matrix(text: str) -> list[str]:
    """QR برای کارت استوری؛ هر ردیف رشته‌ای از 0 و 1 (Mini App خودش روی canvas می‌کشد)."""
    qr = segno.make(text, error="m", micro=False)
    return ["".join("1" if cell else "0" for cell in row) for row in qr.matrix]
