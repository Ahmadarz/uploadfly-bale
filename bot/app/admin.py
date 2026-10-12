"""دستورهای اضطراری مدیر UploadFly (فقط در ربات اصلی و فقط برای ADMIN_IDS). در منوی دستورها نیستند.

/takedown <لینک یا کد>   حذف محصول + لیست سیاه فایل (در همه‌ی ربات‌ها)
/ban <آیدی یا @یوزرنیم>  مسدود کردن کاربر و قطع فروشگاهش
/unban <آیدی یا @یوزرنیم>
/reports                  فروشگاه‌هایی با بیشترین گزارش در ۳۰ روز اخیر + دلیل‌ها
/suspend <@ربات فروشگاه>  تعلیق فروش یک فروشگاه (گزارش‌ها خودکار تعلیق نمی‌کنند)
/unsuspend <@ربات فروشگاه>
/stats                    آمار کلی
"""
import html
import logging
import re
from collections import Counter
from datetime import datetime, timedelta, timezone

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots import BotManager
from app.config import settings
from app.db import Blacklist, Content, Membership, Purchase, Seller, User
from app.middlewares import main_bot
from app.texts import T
from app.trust import ban_user, set_shop_suspended, takedown

log = logging.getLogger(__name__)


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


router = Router()
router.message.filter(F.chat.type == "private", main_bot, F.from_user.id.in_(settings.admin_ids))


async def find_user(session: AsyncSession, arg: str) -> User | None:
    arg = arg.strip().lstrip("@")
    if arg.isdigit():
        return await session.get(User, int(arg))
    return await session.scalar(select(User).where(func.lower(User.username) == arg.lower())) if arg else None


@router.message(Command("takedown"))
async def takedown_cmd(message: Message, command: CommandObject, session: AsyncSession, manager: BotManager):
    arg = (command.args or "").strip()
    code = m.group(1) if (m := re.search(r"start=([\w-]+)", arg)) else arg
    content = await session.scalar(select(Content).where(Content.code == code)) if code else None
    if content is None:
        await message.answer("محصول پیدا نشد. استفاده: /takedown &lt;لینک یا کد&gt;")
        return
    await takedown(session, content, "admin", manager.get(content.bot_id))
    await message.answer(f"✅ محصول {content.id} حذف شد و فایلش در لیست سیاه رفت (مالک: {content.owner_id}).")


@router.message(Command("ban"))
async def ban_cmd(message: Message, command: CommandObject, session: AsyncSession, manager: BotManager):
    user = await find_user(session, command.args or "")
    if user is None:
        await message.answer("کاربر پیدا نشد. استفاده: /ban &lt;آیدی عددی یا @یوزرنیم&gt;")
        return
    if user.id in settings.admin_ids:
        await message.answer("مدیر قابل مسدود شدن نیست.")
        return
    seller = await ban_user(session, user, manager)
    shop = f" و فروشگاه @{seller.bot_username} قطع شد" if seller else ""
    await message.answer(f"⛔️ کاربر {user.id} مسدود شد{shop}.")


@router.message(Command("unban"))
async def unban_cmd(message: Message, command: CommandObject, session: AsyncSession):
    user = await find_user(session, command.args or "")
    if user is None:
        await message.answer("کاربر پیدا نشد. استفاده: /unban &lt;آیدی عددی یا @یوزرنیم&gt;")
        return
    user.is_banned = False
    await session.commit()
    await message.answer(f"✅ کاربر {user.id} آزاد شد. فروشگاهش خودکار وصل نمی‌شود؛ خودش باید دوباره وصل کند.")


@router.message(Command("stats"))
async def stats_cmd(message: Message, session: AsyncSession):
    users = await session.scalar(select(func.count(User.id)))
    shops = await session.scalar(select(func.count(Seller.id)).where(Seller.is_active.is_(True)))
    products = await session.scalar(select(func.count(Content.id)).where(Content.is_active.is_(True)))
    sales, stars = (await session.execute(select(func.count(Purchase.id), func.coalesce(func.sum(Purchase.amount), 0))
                                          .where(Purchase.refunded.is_(False)))).one()
    blocked = await session.scalar(select(func.count(Blacklist.file_unique_id)))
    banned = await session.scalar(select(func.count(User.id)).where(User.is_banned.is_(True)))
    week = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=7)
    lines = [f"📊 <b>آمار UploadFly</b>\n\n👥 کاربران: {users} (مسدود: {banned})\n🏪 فروشگاه فعال: {shops}\n"
             f"📦 محصول/لینک فعال: {products}\n🛒 فروش: {sales} ({stars} ⭐)\n⛔️ فایل در لیست سیاه: {blocked}"]
    for title, since in (("🧭 <b>مسیر کاربران</b> (همه)", None), ("🆕 <b>کاربران ۷ روز اخیر</b>", week)):
        lines.append(f"\n{title}")
        steps = await funnel(session, since)
        for label, n, base in steps:
            total = steps[base][1] if base is not None else 0
            lines.append(f"{label}: {n}" + (f" ({round(100 * n / total)}٪)" if total else ""))
    lines.append("\nدرصد لینک، فروشگاه و خریدار از کل کاربران است؛ بقیه از قدم قبلی. بزرگ‌ترین افت = جایی که باید بهترش کنیم.")
    lines.append("\n📣 <b>منبع کاربران</b> (۳۰ روز اخیر: کاربر · فروشگاه · فروش · خریدار)")
    rows = await sources(session, datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=30))
    name = lambda src: SOURCE_FA.get(src) or f"🔗 {src[4:]}"  # noqa: E731  لینک‌های تبلیغ با نام خودشان
    lines += [f"{name(src)}: {u} · {sh} · {sold} · {buy}" for src, u, sh, sold, buy in rows] or ["هنوز کسی نیامده."]
    lines.append("لینک تبلیغ تازه: /srclink نام (مثلاً /srclink insta_ali)")
    await message.answer("\n".join(lines))


SOURCE_FA = {"direct": "مستقیم", "link": "لینک رایگان", "shop": "از ویترین فروشنده‌ها", "miniapp": "مینی‌اپ",
             "src_made": "پانویس «ساخته‌شده با UploadFly»", None: "قدیمی (قبل از ردیابی)"}


async def sources(session: AsyncSession, since: datetime, limit: int = 12) -> list[tuple]:
    """هر منبع: چند کاربر آمد، چندتا فروشگاه ساختند، چند فروشگاه فروش داشتند، چند نفر خریدند."""
    users = (await session.execute(select(User.source, func.count(User.id)).where(User.created_at >= since)
                                   .group_by(User.source).order_by(func.count(User.id).desc()).limit(limit))).all()
    out = []
    for src, n in users:
        cohort = select(User.id).where(User.created_at >= since,
                                       User.source.is_(None) if src is None else User.source == src)
        shops = select(Seller.owner_id, Seller.bot_id).where(Seller.owner_id.in_(cohort)).subquery()
        paid = (Purchase.amount > 0, Purchase.refunded.is_(False))
        n_shops = await session.scalar(select(func.count(func.distinct(shops.c.owner_id)))) or 0
        n_sold = await session.scalar(select(func.count(func.distinct(shops.c.owner_id))).join(
            Purchase, Purchase.bot_id == shops.c.bot_id).where(*paid)) or 0
        n_buy = await session.scalar(select(func.count(func.distinct(Purchase.buyer_id))).where(
            Purchase.buyer_id.in_(cohort), *paid)) or 0
        out.append((src, n, n_shops, n_sold, n_buy))
    return out


@router.message(Command("srclink"))
async def srclink_cmd(message: Message, command: CommandObject, main_username: str):
    """لینک تبلیغ با برچسب منبع؛ هر کانال تبلیغ یک لینک جدا تا معلوم شود کدام جواب می‌دهد."""
    from app.handlers import clean_source
    tag = (command.args or "").strip()
    if not tag:
        await message.answer("بعد از دستور یک نام بنویسید، مثلاً:\n/srclink insta_ali\n(فقط حروف انگلیسی کوچک، عدد و _)")
        return
    src = clean_source(tag)
    await message.answer(f"🔗 لینک تبلیغ «{src[4:]}»:\n<code>https://ble.ir/{main_username}?start={src}</code>\n\n"
                         "هر کس اولین بار با این لینک بیاید، در /stats زیر همین نام شمرده می‌شود.")


async def funnel(session: AsyncSession, since: datetime | None = None) -> list[tuple[str, int, int | None]]:
    """قیف رشد بین کاربرانی که از `since` به بعد آمده‌اند (None = همه).
    هر ردیف: (عنوان، تعداد، ردیفِ پایه‌ی درصد). ساختن فروشگاه بدون لینک رایگان هم ممکن است، پس پایه‌اش کل کاربران است."""
    cohort = select(User.id).where(User.created_at >= since) if since else select(User.id)
    paid = Purchase.amount > 0

    async def count(stmt) -> int:
        return await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    shop_of = select(Seller.owner_id, Seller.bot_id).where(Seller.owner_id.in_(cohort)).subquery()
    return [
        ("۱. وارد ربات شدند", await count(cohort), None),
        ("۲. لینک ساختند", await count(select(Content.owner_id).where(Content.owner_id.in_(cohort)).distinct()), 0),
        ("۳. فروشگاه ساختند", await count(select(shop_of.c.owner_id).distinct()), 0),
        ("۴. محصول منتشر کردند", await count(select(shop_of.c.owner_id).join(
            Content, Content.bot_id == shop_of.c.bot_id).where(Content.is_draft.is_(False)).distinct()), 2),
        ("۵. اولین فروش را داشتند", await count(select(shop_of.c.owner_id).join(
            Purchase, Purchase.bot_id == shop_of.c.bot_id).where(paid, Purchase.refunded.is_(False)).distinct()), 3),
        ("🛍 خریدار شدند", await count(select(Purchase.buyer_id).where(
            Purchase.buyer_id.in_(cohort), paid, Purchase.refunded.is_(False)).distinct()), 0),
    ]


REASON_FA = {"mismatch": "فرق با توضیحات", "broken": "فایل خراب", "forbidden": "ممنوع", "other": "دیگر", None: "قدیمی"}


@router.message(Command("reports"))
async def reports_cmd(message: Message, session: AsyncSession):
    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=30)
    rows = (await session.execute(
        select(Purchase.bot_id, Purchase.content_id, Purchase.report_reason)
        .where(Purchase.reported_at.is_not(None), Purchase.reported_at >= since))).all()
    if not rows:
        await message.answer("در ۳۰ روز اخیر گزارشی ثبت نشده.")
        return
    by_shop: dict[int, list] = {}
    for bot_id, content_id, reason in rows:
        by_shop.setdefault(bot_id, []).append((content_id, reason))
    lines = ["🚩 <b>گزارش‌های ۳۰ روز اخیر</b> (بیشترین اول)\n"]
    for bot_id, items in sorted(by_shop.items(), key=lambda kv: -len(kv[1]))[:10]:
        seller = await session.scalar(select(Seller).where(Seller.bot_id == bot_id))
        sales = await session.scalar(select(func.count(Purchase.id)).where(
            Purchase.bot_id == bot_id, Purchase.refunded.is_(False), Purchase.created_at >= since))
        reasons = "، ".join(f"{REASON_FA.get(r, r)} {n}" for r, n in Counter(r for _, r in items).most_common())
        name = f"@{seller.bot_username}" if seller else str(bot_id)
        state = " ⛔️ تعلیق" if seller and seller.is_suspended else ""
        lines.append(f"<b>{name}</b>{state} — {len(items)} گزارش از {sales} فروش (مالک {seller.owner_id if seller else '?'})\n"
                     f"   دلیل‌ها: {reasons}")
        for content_id, n in Counter(c for c, _ in items).most_common(3):
            content = await session.get(Content, content_id)
            if content and seller:
                lines.append(f"   • {n}× https://ble.ir/{seller.bot_username}?start={content.code}")
    lines.append("\nتصمیم با توست: /suspend @ربات · /takedown لینک · /ban @کاربر")
    await message.answer("\n".join(lines), disable_web_page_preview=True)


async def find_shop(session: AsyncSession, arg: str) -> Seller | None:
    arg = arg.strip().lstrip("@")
    if not arg:
        return None
    return await session.scalar(select(Seller).where(
        func.lower(Seller.bot_username) == arg.lower(), Seller.is_active.is_(True)))


async def set_suspended(message: Message, command: CommandObject, session: AsyncSession, value: bool) -> None:
    seller = await find_shop(session, command.args or "")
    if seller is None:
        await message.answer(f"فروشگاه پیدا نشد. استفاده: /{'suspend' if value else 'unsuspend'} &lt;@ربات فروشگاه&gt;")
        return
    await set_shop_suspended(session, seller, value, message.bot)
    await message.answer(f"{'⛔️ تعلیق شد' if value else '✅ تعلیق برداشته شد'}: @{seller.bot_username}")


@router.message(Command("suspend"))
async def suspend_cmd(message: Message, command: CommandObject, session: AsyncSession):
    await set_suspended(message, command, session, True)


@router.message(Command("unsuspend"))
async def unsuspend_cmd(message: Message, command: CommandObject, session: AsyncSession):
    await set_suspended(message, command, session, False)


# --- برگرداندن استارزهای خرید آزمایشی ---
async def own_unrefunded(session: AsyncSession, owner_id: int) -> tuple[list, list, dict[int, str]]:
    """پرداخت‌های بازپرداخت‌نشده در فروشگاه‌هایی که صاحبش خود همین مدیر است (فقط پول خودش)."""
    shops = {s.bot_id: s.bot_username for s in (await session.scalars(
        select(Seller).where(Seller.owner_id == owner_id, Seller.is_active.is_(True)))).all()}
    if not shops:
        return [], [], shops
    purchases = (await session.scalars(select(Purchase).where(
        Purchase.bot_id.in_(shops), Purchase.amount > 0, Purchase.refunded.is_(False)))).all()
    members = (await session.scalars(select(Membership).where(
        Membership.bot_id.in_(shops), Membership.amount > 0, Membership.refunded.is_(False)))).all()
    return purchases, members, shops


@router.message(Command("refundtests"))
async def refundtests_cmd(message: Message, session: AsyncSession):
    """همه‌ی پرداخت‌های فروشگاه‌های خودت را به خریدارها برمی‌گرداند (برای پاک کردن خریدهای آزمایشی)."""
    purchases, members, shops = await own_unrefunded(session, message.from_user.id)
    if not purchases and not members:
        await message.answer("در فروشگاه‌های تو پرداخت بازپرداخت‌نشده‌ای نیست ✅")
        return
    total = sum(p.amount for p in purchases) + sum(m.amount for m in members)
    buyers = sorted({p.buyer_id for p in purchases} | {m.user_id for m in members})
    await message.answer(
        "↩️ <b>برگرداندن استارزهای خرید</b>\n\n"
        f"فروشگاه: {', '.join('@' + b for b in shops.values())}\n"
        f"{len(purchases)} خرید + {len(members)} عضویت = <b>{total} ⭐</b>\n"
        f"به این حساب‌ها برمی‌گردد: {', '.join(f'<code>{b}</code>' for b in buyers)}\n\n"
        "⚠️ این کار برگشت‌پذیر نیست: استارز از موجودی ربات فروشگاهت کم و به خریدار برگردانده می‌شود، "
        "دسترسی خریدار به آن محتواها بسته می‌شود و تمدید اشتراک‌ها خاموش می‌شود. "
        "فقط وقتی بزن که این خریدها آزمایشی بوده‌اند.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=f"✅ برگرداندن {total} ⭐", callback_data="rft:yes"),
            InlineKeyboardButton(text="انصراف", callback_data="rft:no")]]))


@router.callback_query(F.data.in_({"rft:yes", "rft:no"}), main_bot, F.from_user.id.in_(settings.admin_ids))
async def refundtests_cb(callback: CallbackQuery, session: AsyncSession, manager: BotManager):
    if callback.data == "rft:no":
        await callback.message.edit_text("انصراف داده شد؛ چیزی برنگشت.")
        await callback.answer()
        return
    await callback.answer("در حال برگرداندن…")
    purchases, members, _ = await own_unrefunded(session, callback.from_user.id)
    done, stars, failed = 0, 0, []

    async def refund(bot, user_id: int, charge_id: str) -> bool:
        try:
            await bot.refund_star_payment(user_id=user_id, telegram_payment_charge_id=charge_id)
            return True
        except TelegramBadRequest as e:
            if "ALREADY_REFUNDED" in e.message.upper():  # قبلاً از جای دیگری برگشته
                return True
            failed.append(e.message[:60])
            return False

    for p in purchases:
        bot = manager.get(p.bot_id)
        if bot is None:
            failed.append("ربات فروشگاه خاموش است")
            continue
        if await refund(bot, p.buyer_id, p.charge_id):
            p.refunded, p.refunded_at = True, utcnow()
            done, stars = done + 1, stars + p.amount
    for m in members:
        bot = manager.get(m.bot_id)
        if bot is None:
            failed.append("ربات فروشگاه خاموش است")
            continue
        if m.sub_charge_id and not m.canceled:   # اشتراک ماهانه: اول تمدید خاموش
            try:
                await bot.edit_user_star_subscription(user_id=m.user_id, telegram_payment_charge_id=m.sub_charge_id,
                                                      is_canceled=True)
                m.canceled = True
            except TelegramBadRequest:
                pass
        if await refund(bot, m.user_id, m.charge_id):
            m.refunded, m.refunded_at = True, utcnow()
            done, stars = done + 1, stars + m.amount
    await session.commit()
    log.warning("Admin %s refunded %s test payments (%s stars)", callback.from_user.id, done, stars)
    text = f"✅ {done} پرداخت برگشت داده شد: <b>{stars} ⭐</b> به حساب خریدار(ها) برگشت."
    if failed:
        text += f"\n\n⚠️ {len(failed)} مورد برنگشت:\n" + "\n".join(f"• {html.escape(f)}" for f in failed[:10])
        text += "\nبعداً دوباره /refundtests را بزن."
    await callback.message.edit_text(text)
