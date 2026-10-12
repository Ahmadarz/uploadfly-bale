"""منطق مشترک محصول برای چت و Mini App: لینک، انتشار، پیش‌نمایش و آمار هر محصول."""
import html
from urllib.parse import quote

from aiogram import Bot
from aiogram.types import CopyTextButton, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import preview
from app.money import MAX_PRICE, MIN_PRICE, PRICE_PRESETS, toman  # noqa: F401  (بقیه‌ی ماژول‌ها از همین‌جا می‌گیرند)
from app.db import Content, Purchase, Review
from app.texts import T, format_specs

# قیمت‌ها به تومان (app/money.py). قبلاً: سقف تلگرام برای یک فاکتور استارز؛ سقف اعتماد فروشنده‌ی جدید در مرحله‌ی ۳ می‌آید
# دسته‌های ثابت (نه متن آزاد) تا جست‌وجو و Explore آینده تمیز کار کند. برچسب‌ها در Mini App ترجمه می‌شوند
CATEGORIES = ("education", "movies", "music", "books", "ai", "photos", "software", "other")
TITLE_MAX, DESCRIPTION_MAX = 80, 500


def display_title(content: Content, lang: str) -> str:
    return content.title or content.file_name or T(lang)["kinds"].get(content.kind, content.kind)


def invoice_args(content: Content, lang: str) -> dict:
    """فاکتور استارز؛ هم در چت (send_invoice) و هم در Mini App (create_invoice_link) استفاده می‌شود."""
    t = T(lang)
    return {
        "title": display_title(content, lang)[:32],
        "description": (content.description or html.unescape(format_specs(content, lang)))[:255],
        "payload": f"c:{content.id}",
        "currency": "XTR",  # Telegram Stars
        "prices": [LabeledPrice(label=t["invoice_label"], amount=content.price_stars)],
    }


async def build_link(bot: Bot, code: str) -> str:
    me = await bot.me()
    return f"https://ble.ir/{me.username}?start={code}"


def link_keyboard(link: str, lang: str) -> InlineKeyboardMarkup:
    t = T(lang)
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t["btn_copy"], copy_text=CopyTextButton(text=link)),
        InlineKeyboardButton(text=t["btn_share"], url="https://ble.ir/share/url?url=" + quote(link, safe="")),
    ]])


async def link_created(bot: Bot, chat_id: int, content: Content, lang: str) -> None:
    t = T(lang)
    link = await build_link(bot, content.code)
    price = t["price_free"] if content.price_stars == 0 else toman(content.price_stars)
    await bot.send_message(
        chat_id,
        t["link_created"].format(specs=format_specs(content, lang), link=link) + f"\n💰 {t['price']}: {price}"
        + (f"\n{t['sensitive_label']}" if content.is_sensitive else "")
        + (f"\n{t['save_label']}" if content.allow_save else ""),
        reply_markup=link_keyboard(link, lang),
        disable_notification=True,  # تأیید کاری که خود کاربر کرده؛ صدا لازم نیست
    )


async def build_preview(bot: Bot, chat_id: int, content: Content, lang: str) -> None:
    """پیش‌نمایش خودکار را می‌سازد و همان چیزی که خریدار می‌بیند برای فروشنده می‌فرستد."""
    t = T(lang)
    wait = await bot.send_message(chat_id, t["preview_building"], disable_notification=True)
    await preview.create(bot, content, chat_id, t["preview_caption_seller"])
    p = preview.stored(content)
    if p.get("text"):
        await bot.send_message(chat_id, t["preview_text"].format(snippet=html.escape(p["text"])), disable_notification=True)
    if p.get("thumb_only"):
        await bot.send_message(chat_id, t["preview_thumb_only"], disable_notification=True)
    await wait.delete()


async def publish(bot: Bot, chat_id: int, content: Content, price: int, lang: str) -> None:
    """قیمت را ثبت می‌کند، برای محتوای پولی پیش‌نمایش می‌سازد، منتشر می‌کند و لینک فروش را می‌فرستد."""
    content.price_stars = price
    if price > 0 and not content.preview:
        await build_preview(bot, chat_id, content, lang)
    content.is_draft, content.is_active = False, True
    await link_created(bot, chat_id, content, lang)


async def sales_by_content(session: AsyncSession, content_ids: list[int]) -> dict[int, dict]:
    """فروش، درآمد و گزارش کلاهبرداری هر محصول (خریدهای بازپرداخت‌شده حساب نمی‌شوند)."""
    if not content_ids:
        return {}
    rows = (await session.execute(
        # باز شدن با عضویت ویترین (خرید ۰ استارزی) فروش حساب نمی‌شود؛ ولی گزارشش حساب می‌شود
        select(Purchase.content_id, func.count(Purchase.id).filter(Purchase.amount > 0),
               func.coalesce(func.sum(Purchase.amount), 0),
               func.count(Purchase.reported_at))
        .where(Purchase.content_id.in_(content_ids), Purchase.refunded.is_(False))
        .group_by(Purchase.content_id))).all()
    return {cid: {"sales": n, "revenue": s, "reports": r} for cid, n, s, r in rows}


async def ratings_by_content(session: AsyncSession, content_ids: list[int]) -> dict[int, dict]:
    """میانگین و تعداد امتیاز هر محتوا."""
    if not content_ids:
        return {}
    rows = (await session.execute(select(Review.content_id, func.avg(Review.stars), func.count(Review.id))
                                  .where(Review.content_id.in_(content_ids)).group_by(Review.content_id))).all()
    return {cid: {"avg": round(float(avg), 1), "count": n} for cid, avg, n in rows}


async def shop_rating(session: AsyncSession, bot_id: int) -> dict | None:
    avg, n = (await session.execute(select(func.avg(Review.stars), func.count(Review.id))
                                    .where(Review.bot_id == bot_id))).one()
    return {"avg": round(float(avg), 1), "count": n} if n else None


async def rate(session: AsyncSession, purchase: Purchase, stars: int) -> bool:
    """امتیاز خریدار؛ فقط بعد از باز کردن محتوا. دوباره زدن، امتیاز قبلی را عوض می‌کند."""
    if purchase.refunded or purchase.opened_at is None or not 1 <= stars <= 5:
        return False
    review = await session.scalar(select(Review).where(
        Review.content_id == purchase.content_id, Review.buyer_id == purchase.buyer_id))
    if review is None:
        session.add(Review(content_id=purchase.content_id, buyer_id=purchase.buyer_id, bot_id=purchase.bot_id,
                           stars=stars))
    else:
        review.stars = stars
    await session.commit()
    return True
