"""اعتماد و ضدکلاهبرداری: سقف قیمت تدریجی، لیست سیاه فایل‌ها، حذف و مسدودسازی (به تصمیم مدیر)."""
import logging

from aiogram import Bot
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.money import MAX_PRICE, PRICE_TIERS
from app.db import Blacklist, Content, Purchase, Seller, User
from app.texts import T

log = logging.getLogger(__name__)

# سقف قیمت بر اساس تعداد فروش موفق (بازپرداخت‌نشده). فروشنده‌ی تازه نمی‌تواند روز اول مبلغ بزرگی بگیرد و برود
# سقف‌ها به تومان در app/money.py  # (کمتر از این تعداد فروش، سقف)
TOP_CAP = MAX_PRICE  # قبلاً:                                   # سقف خود تلگرام برای یک فاکتور


async def price_cap(session: AsyncSession, bot_id: int) -> int:
    # گزارش‌ها روی سقف اثر ندارند (با خرید ارزان از چند حساب قابل سوءاستفاده بود)؛ مدیر بررسی می‌کند
    sales = await session.scalar(select(func.count(Purchase.id)).where(
        Purchase.bot_id == bot_id, Purchase.refunded.is_(False)))
    for below, cap in PRICE_TIERS:
        if sales < below:
            return cap
    return TOP_CAP


async def is_blacklisted(session: AsyncSession, file_unique_id: str | None) -> bool:
    return bool(file_unique_id) and await session.get(Blacklist, file_unique_id) is not None


async def takedown(session: AsyncSession, content: Content, reason: str, bot: Bot | None) -> None:
    """محصول غیرفعال می‌شود، فایلش در لیست سیاه می‌رود و به فروشنده خبر داده می‌شود."""
    content.is_active, content.is_draft = False, False
    if content.file_unique_id and not await is_blacklisted(session, content.file_unique_id):
        session.add(Blacklist(file_unique_id=content.file_unique_id, reason=reason))
    # همان فایل در هر جای دیگر (هر ربات) هم غیرفعال می‌شود
    if content.file_unique_id:
        for other in (await session.scalars(select(Content).where(
                Content.file_unique_id == content.file_unique_id, Content.is_active.is_(True)))).all():
            other.is_active = False
    await session.commit()
    log.warning("Content %s taken down (%s)", content.id, reason)
    if bot is not None:
        owner = await session.get(User, content.owner_id)
        try:
            await bot.send_message(content.owner_id, T(owner.language if owner else "fa")[f"takedown_{reason}"])
        except Exception:
            pass


async def ban_user(session: AsyncSession, user: User, manager) -> Seller | None:
    """کاربر مسدود می‌شود؛ اگر فروشگاه دارد، فروشگاهش هم قطع می‌شود."""
    user.is_banned = True
    seller = await session.scalar(select(Seller).where(Seller.owner_id == user.id, Seller.is_active.is_(True)))
    if seller:
        seller.is_active = False
    await session.commit()
    if seller:
        await manager.stop(seller.bot_id)
    log.warning("User %s banned", user.id)
    return seller


async def set_shop_suspended(session: AsyncSession, seller: Seller, value: bool, bot: Bot | None) -> None:
    """تعلیق/رفع تعلیق فروش یک فروشگاه (دستور مدیر یا پنل) + خبر به صاحبش از ربات اصلی."""
    seller.is_suspended = value
    await session.commit()
    log.warning("Shop %s %s by admin", seller.bot_id, "suspended" if value else "unsuspended")
    owner = await session.get(User, seller.owner_id)
    if bot is not None:
        try:
            await bot.send_message(seller.owner_id, T(owner.language if owner else "fa")[
                "shop_suspended_owner" if value else "shop_unsuspended"].format(bot=seller.bot_username))
        except Exception:
            pass
