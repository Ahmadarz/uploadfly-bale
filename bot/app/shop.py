"""«فروشگاه من»: پنل دکمه‌ای فروشنده داخل ربات اصلی.
فروشنده برای دیدن موجودی، فروش‌ها، لینک‌ها و راهنمای برداشت لازم نیست ربات خودش یا BotFather را باز کند."""
import html
import logging
import time
from datetime import datetime, timedelta, timezone

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots import BotManager
from app.connect import Connect, active_seller, create_shop_markup
from app.db import Content, Membership, Purchase, Seller, Showcase, User
from app.middlewares import main_bot
from app.texts import T

log = logging.getLogger(__name__)

router = Router()
router.message.filter(F.chat.type == "private", main_bot)
router.callback_query.filter(main_bot)

# قانون فعلی تلگرام برای برداشت استارز ربات از Fragment؛ قبل از اعلام عمومی با مستندات رسمی چک شود
WITHDRAW_MIN = 1000


def btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def back_markup(t: dict) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[btn(t["btn_back"], "shop:home")]])


_balance_cache: dict[int, tuple[float, int]] = {}
BALANCE_TTL = 60  # ثانیه؛ باز شدن Mini App نباید هر بار منتظر تلگرام بماند


async def star_balance(manager: BotManager, seller: Seller, fresh: bool = False) -> int | None:
    cached = _balance_cache.get(seller.bot_id)
    if cached and not fresh and time.monotonic() - cached[0] < BALANCE_TTL:
        return cached[1]
    bot = manager.get(seller.bot_id)
    if bot is None:
        return cached[1] if cached else None
    try:
        amount = (await bot.get_my_star_balance()).amount
    except Exception:
        log.warning("Could not read balance of seller bot %s", seller.bot_id)
        return cached[1] if cached else None
    _balance_cache[seller.bot_id] = (time.monotonic(), amount)
    return amount


async def shop_stats(session: AsyncSession, seller: Seller, manager: BotManager, days: int = 0,
                     tz_offset: int | None = None) -> dict:
    """آمار واقعی فروشگاه؛ هم پنل ربات و هم Mini App از همین استفاده می‌کنند.
    «امروز» و نمودار به وقت محلی کاربر است (tz_offset دقیقه اختلاف با UTC؛ اگر نامعلوم، UTC).
    days > 0: فروش روزانه‌ی چند روز اخیر هم برای نمودار برمی‌گردد."""
    offset = timedelta(minutes=tz_offset or 0)
    local_now = datetime.now(timezone.utc).replace(tzinfo=None) + offset
    local_today = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    span = max(days, 1)
    since_utc = local_today - timedelta(days=span - 1) - offset

    # فروش = خرید محصول + ورودی/اشتراک ویترین (بازپرداخت‌شده و باز شدن ۰ استارزی با عضویت حساب نمی‌شوند)
    sold = Purchase.bot_id == seller.bot_id, Purchase.refunded.is_(False), Purchase.amount > 0
    joined = Membership.bot_id == seller.bot_id, Membership.refunded.is_(False), Membership.amount > 0
    total_n, total_sum = (await session.execute(
        select(func.count(Purchase.id), func.coalesce(func.sum(Purchase.amount), 0)).where(*sold))).one()
    m_n, m_sum = (await session.execute(
        select(func.count(Membership.id), func.coalesce(func.sum(Membership.amount), 0)).where(*joined))).one()
    total_n, total_sum = total_n + m_n, total_sum + m_sum
    since = since_utc.replace(tzinfo=timezone.utc)  # created_at «با منطقه‌ی زمانی» است؛ PostgreSQL زمانِ آگاه می‌خواهد
    recent = (await session.execute(
        select(Purchase.created_at, Purchase.amount).where(*sold, Purchase.created_at >= since))).all()
    recent += (await session.execute(
        select(Membership.created_at, Membership.amount).where(*joined, Membership.created_at >= since))).all()
    buckets: dict = {}
    for created, amount in recent:  # گروه‌بندی روزانه در پایتون تا روی SQLite و PostgreSQL یکسان باشد
        day = (naive(created) + offset).date()
        n, s_ = buckets.get(day, (0, 0))
        buckets[day] = (n + 1, s_ + amount)
    today_n, today_sum = buckets.get(local_today.date(), (0, 0))
    links = await session.scalar(select(func.count(Content.id)).where(
        Content.bot_id == seller.bot_id, Content.is_active.is_(True)))
    stats = {"balance": await star_balance(manager, seller), "today_n": today_n, "today_sum": today_sum,
             "total_n": total_n, "total_sum": total_sum, "links": links}
    if days:
        stats["chart"] = []
        for i in range(days):
            day = (local_today - timedelta(days=days - 1 - i)).date()
            n, s_ = buckets.get(day, (0, 0))
            stats["chart"].append({"date": day.isoformat(), "n": n, "sum": s_})
    return stats


# --- کیف پول: استارزهای ربات فروشگاه مال خود فروشنده است ---
HOLD_DAYS = 21  # قانون تلگرام: هر استارز درآمد ربات حدود ۲۱ روز بعد قابل برداشت می‌شود
# خرید Premium برای صاحب فروشگاه از موجودی ربات (giftPremiumSubscription؛ قیمت‌ها را خود تلگرام تعیین کرده)
PREMIUM_OPTIONS = ((3, 1000), (6, 1500), (12, 2500))


async def wallet_view(session: AsyncSession, seller: Seller, manager: BotManager) -> dict:
    """موجودی، سهم «در انتظار ۲۱ روزه» (تخمین از فروش‌های خودمان) و تاریخچه‌ی فروش."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    hold_since = now - timedelta(days=HOLD_DAYS)
    rows = [(p, title or file_name, kind) for p, title, file_name, kind in (await session.execute(
        select(Purchase, Content.title, Content.file_name, Content.kind)
        .join(Content, Content.id == Purchase.content_id)
        .where(Purchase.bot_id == seller.bot_id, Purchase.amount > 0).order_by(Purchase.id.desc()))).all()]
    # ورودی و اشتراک ویترین‌ها هم درآمد همین ربات است
    rows += [(m, f"🔑 {title}", "showcase") for m, title in (await session.execute(
        select(Membership, Showcase.title).join(Showcase, Showcase.id == Membership.showcase_id)
        .where(Membership.bot_id == seller.bot_id, Membership.amount > 0).order_by(Membership.id.desc()))).all()]
    rows.sort(key=lambda r: naive(r[0].created_at) or datetime.min, reverse=True)  # پایدار: هم‌زمان‌ها به ترتیب شناسه
    held = [naive(p.created_at) for p, *_ in rows if not p.refunded and p.created_at and naive(p.created_at) > hold_since]
    pending = sum(p.amount for p, *_ in rows if not p.refunded and p.created_at and naive(p.created_at) > hold_since)
    balance = await star_balance(manager, seller, fresh=True)
    if balance is not None:
        pending = min(pending, balance)  # موجودی واقعی از تلگرام؛ سهم در انتظار از آن بیشتر نمی‌شود
    return {
        "balance": balance,
        "pending": pending,
        "available": None if balance is None else max(0, balance - pending),
        "next_unlock": (min(held) + timedelta(days=HOLD_DAYS)).date().isoformat() if held else None,
        "min": WITHDRAW_MIN, "hold_days": HOLD_DAYS, "bot": seller.bot_username,
        "premium": [{"months": m, "stars": s} for m, s in PREMIUM_OPTIONS],
        "sales": [{"title": title, "kind": kind, "amount": p.amount, "refunded": p.refunded,
                   "date": naive(p.created_at).date().isoformat() if p.created_at else None,
                   "unlocked": bool(p.created_at) and naive(p.created_at) <= hold_since}
                  for p, title, kind in rows[:30]],
    }


async def buy_premium(manager: BotManager, seller: Seller, months: int, text: str) -> str | None:
    """Premium برای صاحب فروشگاه، پرداخت از موجودی ربات خودش. خطا: کد خطا، موفق: None."""
    stars = dict(PREMIUM_OPTIONS).get(months)
    if stars is None:
        return "bad_months"
    bot = manager.get(seller.bot_id)
    if bot is None:
        return "shop_offline"
    balance = await star_balance(manager, seller, fresh=True)
    if balance is not None and balance < stars:
        return "not_enough"
    try:
        await bot.gift_premium_subscription(user_id=seller.owner_id, month_count=months, star_count=stars, text=text)
    except Exception:
        log.warning("Premium gift failed for seller bot %s", seller.bot_id, exc_info=True)
        return "premium_failed"
    _balance_cache.pop(seller.bot_id, None)
    log.info("Seller bot %s bought %s months of Premium for its owner", seller.bot_id, months)
    return None


def naive(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc).replace(tzinfo=None) if dt.tzinfo else dt


async def home_view(session: AsyncSession, user: User, manager: BotManager) -> tuple[str, InlineKeyboardMarkup]:
    t = T(user.language)
    seller = await active_seller(session, user)
    if seller is None:
        return t["shop_none"], InlineKeyboardMarkup(inline_keyboard=[[btn(t["btn_create_shop"], "shop:create")]])

    st = await shop_stats(session, seller, manager, tz_offset=user.tz_offset)
    text = t["shop_home"].format(
        bot=seller.bot_username, balance="?" if st["balance"] is None else st["balance"],
        today_n=st["today_n"], today_sum=st["today_sum"], total_n=st["total_n"], total_sum=st["total_sum"],
        links=st["links"])
    if seller.is_suspended:
        text = t["shop_suspended_line"] + "\n\n" + text
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t["btn_upload"], url=f"https://ble.ir/{seller.bot_username}?start=upload")],
        [btn(t["btn_sales"], "shop:sales"), btn(t["btn_links"], "shop:links")],
        [btn(t["btn_withdraw"], "shop:withdraw"), btn(t["btn_refresh"], "shop:home")],
        [btn(t["btn_disconnect"], "shop:disconnect")],
    ])
    return text, markup


async def show(target: Message | CallbackQuery, text: str, markup: InlineKeyboardMarkup) -> None:
    """پیام جدید برای دستور، ویرایش همان پیام برای دکمه (تا چت شلوغ نشود)."""
    if isinstance(target, Message):
        await target.answer(text, reply_markup=markup, disable_web_page_preview=True)
        return
    try:
        await target.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)
    except Exception:
        pass  # «message is not modified» وقتی چیزی عوض نشده
    await target.answer()


@router.message(Command("shop"))
async def shop_cmd(message: Message, session: AsyncSession, db_user: User, manager: BotManager):
    await show(message, *await home_view(session, db_user, manager))


@router.callback_query(F.data == "shop:home")
async def shop_home(callback: CallbackQuery, session: AsyncSession, db_user: User, manager: BotManager):
    await show(callback, *await home_view(session, db_user, manager))


@router.callback_query(F.data == "shop:create")
async def shop_create(callback: CallbackQuery, db_user: User, state: FSMContext, main_username: str):
    t = T(db_user.language)
    await state.set_state(Connect.waiting_token)  # روش دستی (توکن) هم همچنان کار می‌کند
    await callback.message.answer(t["connect_quick"], reply_markup=create_shop_markup(t, main_username, db_user))
    await callback.answer()


@router.callback_query(F.data == "shop:sales")
async def shop_sales(callback: CallbackQuery, session: AsyncSession, db_user: User):
    t = T(db_user.language)
    seller = await active_seller(session, db_user)
    if seller is None:
        await callback.answer()
        return
    rows = (await session.execute(
        select(Purchase, Content).join(Content, Content.id == Purchase.content_id)
        .where(Purchase.bot_id == seller.bot_id).order_by(Purchase.id.desc()).limit(10))).all()
    if not rows:
        text = t["sales_empty"]
    else:
        lines = [t["sales_header"]]
        for p, c in rows:
            label = t["kinds"].get(c.kind, c.kind)
            if c.file_name:
                label += f" · {html.escape(c.file_name[:25])}"
            refunded = f" ({t['refunded']})" if p.refunded else " 🚩" if p.reported_at else ""
            lines.append(f"• {p.created_at:%Y-%m-%d %H:%M} — {label} — {p.amount} ⭐{refunded}")
        text = "\n".join(lines)
    await show(callback, text, back_markup(t))


@router.callback_query(F.data == "shop:links")
async def shop_links(callback: CallbackQuery, session: AsyncSession, db_user: User):
    t = T(db_user.language)
    seller = await active_seller(session, db_user)
    if seller is None:
        await callback.answer()
        return
    rows = (await session.scalars(
        select(Content).where(Content.bot_id == seller.bot_id, Content.is_active.is_(True))
        .order_by(Content.id.desc()).limit(10))).all()
    if not rows:
        text = t["shop_links_empty"].format(bot=seller.bot_username)
    else:
        lines = [t["mylinks_header"]]
        for c in rows:
            label = t["kinds"].get(c.kind, c.kind)
            if c.file_name:
                label += f" · {html.escape(c.file_name[:25])}"
            label += f" · {c.price_stars} ⭐" if c.price_stars else f" · {t['price_free']}"
            if c.is_sensitive:
                label += " · ⏳"
            link = f"https://ble.ir/{seller.bot_username}?start={c.code}"
            lines.append(f"• {label}\n   <code>{link}</code>  ({c.views} {t['views']})")
        text = "\n".join(lines)
    await show(callback, text, back_markup(t))


@router.callback_query(F.data == "shop:withdraw")
async def shop_withdraw(callback: CallbackQuery, session: AsyncSession, db_user: User, manager: BotManager):
    t = T(db_user.language)
    seller = await active_seller(session, db_user)
    if seller is None:
        await callback.answer()
        return
    balance = await star_balance(manager, seller)
    if balance is not None and balance < WITHDRAW_MIN:
        text = t["withdraw_not_yet"].format(balance=balance, min=WITHDRAW_MIN, left=WITHDRAW_MIN - balance)
    else:
        text = t["withdraw_steps"].format(bot=seller.bot_username, min=WITHDRAW_MIN)
    await show(callback, text, back_markup(t))


@router.callback_query(F.data == "shop:disconnect")
async def shop_disconnect_ask(callback: CallbackQuery, session: AsyncSession, db_user: User):
    t = T(db_user.language)
    seller = await active_seller(session, db_user)
    if seller is None:
        await callback.answer()
        return
    await show(callback, t["disconnect_confirm"].format(bot=seller.bot_username), InlineKeyboardMarkup(
        inline_keyboard=[[btn(t["btn_disconnect_yes"], "shop:disconnect_yes"), btn(t["btn_back"], "shop:home")]]))


@router.callback_query(F.data == "shop:disconnect_yes")
async def shop_disconnect(callback: CallbackQuery, session: AsyncSession, db_user: User, manager: BotManager):
    t = T(db_user.language)
    seller = await active_seller(session, db_user)
    if seller is None:
        await callback.answer()
        return
    seller.is_active = False
    await session.commit()
    await manager.stop(seller.bot_id)
    await show(callback, t["disconnected"].format(bot=seller.bot_username),
               InlineKeyboardMarkup(inline_keyboard=[[btn(t["btn_back"], "shop:home")]]))
