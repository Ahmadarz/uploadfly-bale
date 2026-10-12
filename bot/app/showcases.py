"""ویترین‌های اضافه‌ی هر فروشگاه: رایگان، یک‌بار پرداخت یا اشتراک ماهانه (صفحه‌ی سازنده).

ویترین اصلی همان Content.in_store است و همیشه رایگان. پرداخت ورودی هم مثل خرید محصول به ربات خود
فروشنده می‌رود. محتوای «رایگان برای اعضا» با یک Purchase صفر استارزی تحویل می‌شود تا همان مسیر
تحویل محافظت‌شده، «خریدهای من» و گزارش برایش کار کند.
"""
import html
import json
import logging
import secrets
from datetime import datetime, timedelta, timezone

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice, WebAppInfo
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Content, Membership, Purchase, Seller, SessionLocal, Showcase, ShowcaseItem, User, is_id
from app.texts import T

log = logging.getLogger(__name__)

ACCESS_TYPES = ("free", "once", "monthly")
TITLE_MAX = 60
DESCRIPTION_MAX = 300
MAX_SHOWCASES = 20                       # برای هر فروشگاه
SUBSCRIPTION_SECONDS = 30 * 24 * 3600    # تلگرام فعلاً فقط دوره‌ی ۳۰ روزه قبول می‌کند
REFUND_WINDOW = timedelta(hours=24)      # بازپرداخت ورودی: فقط تا قبل از باز کردن اولین محتوا
REMIND_BEFORE = timedelta(days=3)        # یادآوری تمدید اشتراک ماهانه
END_GRACE = timedelta(hours=2)           # تمدید تلگرام ممکن است کمی بعد از سررسید برسد
TRIAL_DAYS = (0, 3, 7, 14, 30)           # دوره‌ی آزمایشی رایگان اشتراک ماهانه (۰ = خاموش)
BUNDLE_MONTHS = (3, 6, 12)               # چند ماه یک‌جا با تخفیف (پرداخت یک‌باره، بدون تمدید خودکار)
BUNDLE_MAX_OFF = 50                      # بیشترین تخفیف بسته (درصد)


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def naive(dt: datetime | None) -> datetime | None:
    return dt.astimezone(timezone.utc).replace(tzinfo=None) if dt and dt.tzinfo else dt


async def new_code(session: AsyncSession) -> str:
    while True:
        code = secrets.token_urlsafe(6)
        if not await session.scalar(select(Showcase.id).where(Showcase.code == code)):
            return code


def showcase_link(sc: Showcase, bot_username: str) -> str:
    return f"https://t.me/{bot_username}?start=sc_{sc.code}"


async def active_membership(session: AsyncSession, showcase_id: int, user_id: int) -> Membership | None:
    now = utcnow()
    return await session.scalar(select(Membership).where(
        Membership.showcase_id == showcase_id, Membership.user_id == user_id, Membership.refunded.is_(False),
        (Membership.expires_at.is_(None)) | (Membership.expires_at > now)).order_by(Membership.id.desc()))


async def member_count(session: AsyncSession, showcase_id: int) -> int:
    now = utcnow()
    return await session.scalar(select(func.count(func.distinct(Membership.user_id))).where(
        Membership.showcase_id == showcase_id, Membership.refunded.is_(False),
        (Membership.expires_at.is_(None)) | (Membership.expires_at > now))) or 0


async def showcase_items(session: AsyncSession, sc: Showcase) -> list[tuple[Content, ShowcaseItem]]:
    """محتواهای فعال و منتشرشده‌ی ویترین، تازه‌ترین اول."""
    return list((await session.execute(
        select(Content, ShowcaseItem).join(ShowcaseItem, ShowcaseItem.content_id == Content.id)
        .where(ShowcaseItem.showcase_id == sc.id, Content.is_active.is_(True), Content.is_draft.is_(False))
        .order_by(ShowcaseItem.id.desc()))).all())


def bundle_discounts(sc: Showcase) -> dict[int, int]:
    """{ماه: درصد تخفیف} بسته‌های چندماهه؛ فقط برای اشتراک ماهانه."""
    if sc.access != "monthly" or not sc.bundles:
        return {}
    try:
        raw = json.loads(sc.bundles)
    except ValueError:
        return {}
    return {int(m): int(off) for m, off in raw.items()
            if str(m).isdigit() and int(m) in BUNDLE_MONTHS and isinstance(off, int) and 0 <= off <= BUNDLE_MAX_OFF}


def bundle_price(sc: Showcase, months: int) -> int | None:
    off = bundle_discounts(sc).get(months)
    if off is None:
        return None
    return max(1, round(sc.price * months * (100 - off) / 100))


def bundle_options(sc: Showcase) -> list[dict]:
    return [{"months": m, "off": off, "price": bundle_price(sc, m)} for m, off in sorted(bundle_discounts(sc).items())]


def clean_bundles(value) -> str | None | bool:
    """{"3": 10, "6": 15} از فرم → JSON تمیز؛ None = بدون بسته؛ False = نامعتبر."""
    if value in (None, {}):
        return None
    if not isinstance(value, dict):
        return False
    out = {}
    for m, off in value.items():
        if not str(m).isdigit() or int(m) not in BUNDLE_MONTHS or not isinstance(off, int) or isinstance(off, bool) \
                or not 0 <= off <= BUNDLE_MAX_OFF:
            return False
        out[str(int(m))] = off
    return json.dumps(out, sort_keys=True) if out else None


def invoice_args(sc: Showcase, lang: str, months: int | None = None) -> dict:
    """فاکتور ورود به ویترین؛ ماهانه = اشتراک تلگرام (تمدید خودکار از موجودی استارز خریدار).
    months: بسته‌ی چندماهه (یک‌باره، بدون تمدید خودکار)."""
    t = T(lang)
    args = {
        "title": sc.title[:32],
        "description": (sc.description or t["sc_invoice_desc"].format(title=sc.title))[:255],
        "payload": f"s:{sc.id}",
        "currency": "XTR",
        "prices": [LabeledPrice(label=t["sc_invoice_label"], amount=sc.price)],
    }
    if months:
        args["payload"] = f"s:{sc.id}:{months}"
        args["title"] = t["sc_bundle_title"].format(months=months)[:32]
        args["prices"] = [LabeledPrice(label=t["sc_bundle_title"].format(months=months), amount=bundle_price(sc, months))]
    elif sc.access == "monthly":
        args["subscription_period"] = SUBSCRIPTION_SECONDS
    return args


def parse_payload(payload: str) -> tuple[int, int | None] | None:
    """«s:<ویترین>» یا «s:<ویترین>:<ماه>»."""
    parts = payload.split(":")
    if len(parts) not in (2, 3) or parts[0] != "s" or not all(is_id(p) for p in parts[1:]):
        return None
    return int(parts[1]), (int(parts[2]) if len(parts) == 3 else None)


async def showcase_from_payload(session: AsyncSession, payload: str, bot_id: int) -> Showcase | None:
    parsed = parse_payload(payload)
    if parsed is None:
        return None
    sc = await session.get(Showcase, parsed[0])
    if sc is None or sc.bot_id != bot_id or not sc.is_active or sc.archived or sc.access == "free":
        return None
    if parsed[1] is not None and bundle_price(sc, parsed[1]) is None:
        return None
    return sc


def is_trial(m: Membership | None) -> bool:
    return bool(m and m.charge_id.startswith("trial:"))


async def start_trial(session: AsyncSession, sc: Showcase, user_id: int) -> Membership | str:
    """دوره‌ی آزمایشی رایگان؛ هر نفر فقط یک بار در هر ویترین (حتی اگر قبلاً عضو پولی بوده)."""
    if sc.access != "monthly" or not sc.trial_days or sc.archived:
        return "sc_no_trial"
    used = await session.scalar(select(Membership.id).where(
        Membership.showcase_id == sc.id, Membership.user_id == user_id).limit(1))
    if used:
        return "sc_trial_used"
    m = Membership(showcase_id=sc.id, user_id=user_id, bot_id=sc.bot_id, amount=0,
                   charge_id=f"trial:{sc.id}:{user_id}", expires_at=utcnow() + timedelta(days=sc.trial_days),
                   canceled=True)
    session.add(m)
    await session.commit()
    return m


async def unlock_item(session: AsyncSession, membership: Membership, content: Content, buyer_id: int) -> Purchase | None:
    """محتوای «رایگان برای اعضا»: یک خرید صفر استارزی (بدون بازپرداخت) تا مسیر تحویل همیشگی کار کند.
    None یعنی عضویت هم‌زمان بازپرداخت شد."""
    # از این لحظه ورودی ویترین قابل بازپرداخت نیست (شرطی: با بازپرداخت هم‌زمان فقط یکی برنده است)
    await session.execute(update(Membership).where(
        Membership.id == membership.id, Membership.opened_at.is_(None), Membership.refunded.is_(False))
        .values(opened_at=utcnow()))
    await session.commit()
    await session.refresh(membership)
    if membership.refunded:
        return None
    charge = f"m{membership.id}:{content.id}"
    purchase = await session.scalar(select(Purchase).where(Purchase.charge_id == charge))
    if purchase is None:
        purchase = Purchase(content_id=content.id, buyer_id=buyer_id, bot_id=content.bot_id, amount=0,
                            charge_id=charge)
        session.add(purchase)
        await session.commit()
    return purchase


async def refund_membership(bot: Bot, session: AsyncSession, m: Membership) -> str | None:
    """بازپرداخت ورودی ویترین: فقط ۲۴ ساعت و فقط اگر هنوز هیچ محتوایی باز نشده."""
    if m.refunded:
        return "refund_already"
    if m.opened_at is not None:
        return "sc_refund_opened"
    if utcnow() - naive(m.created_at) > REFUND_WINDOW:
        return "refund_expired"
    if m.sub_charge_id or not m.amount:  # اشتراک ماهانه با «لغو تمدید» مدیریت می‌شود، نه بازپرداخت
        return "refund_failed"
    claimed = await session.execute(update(Membership).where(
        Membership.id == m.id, Membership.opened_at.is_(None), Membership.refunded.is_(False))
        .values(refunded=True, refunded_at=utcnow()))
    await session.commit()
    if claimed.rowcount != 1:
        await session.refresh(m)
        return "refund_already" if m.refunded else "sc_refund_opened"
    try:
        await bot.refund_star_payment(user_id=m.user_id, telegram_payment_charge_id=m.charge_id)
    except TelegramBadRequest as e:
        log.warning("Membership refund failed %s: %s", m.id, e.message)
        await session.execute(update(Membership).where(Membership.id == m.id).values(refunded=False, refunded_at=None))
        await session.commit()
        await session.refresh(m)
        return "refund_failed"
    await session.refresh(m)
    log.info("Membership %s refunded", m.id)
    return None


async def shop_showcase(session: AsyncSession, seller: Seller, showcase_id: str) -> Showcase | None:
    """ویترینی از همین فروشگاه (برای صفحه‌ی مدیریت فروشنده)."""
    if not is_id(showcase_id):
        return None
    sc = await session.get(Showcase, int(showcase_id))
    return sc if sc and sc.bot_id == seller.bot_id and sc.is_active else None


async def by_code(session: AsyncSession, code: str) -> Showcase | None:
    sc = await session.scalar(select(Showcase).where(Showcase.code == code))
    return sc if sc and sc.is_active else None


# --- اشتراک ماهانه: یادآوری تمدید، پیام پایان، لغو/فعال کردن تمدید ---
def open_button(sc: Showcase, webapp_url: str | None, text: str) -> InlineKeyboardMarkup | None:
    if not webapp_url:
        return None
    url = f"{webapp_url}/?store={sc.bot_id}&bot={sc.bot_id}&sc={sc.code}"
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=text, web_app=WebAppInfo(url=url))]])


async def subscription_tick(manager, webapp_url: str | None) -> int:
    """۳ روز قبل از سررسید: یادآوری؛ بعد از سررسید بدون تمدید: پیام پایان. خروجی: تعداد پیام‌ها."""
    now, sent = utcnow(), 0
    async with SessionLocal() as session:
        rows = (await session.scalars(select(Membership).where(
            Membership.expires_at.is_not(None), Membership.refunded.is_(False),
            Membership.expires_at > now - timedelta(days=3)).order_by(Membership.id))).all()
        latest: dict[tuple[int, int], Membership] = {}
        for m in rows:   # فقط آخرین دوره‌ی هر عضو در هر ویترین مهم است
            latest[(m.showcase_id, m.user_id)] = m
        for m in latest.values():
            due_remind = not m.reminded and timedelta(0) < m.expires_at - now <= REMIND_BEFORE
            due_end = not m.end_notified and now >= m.expires_at + END_GRACE
            if not (due_remind or due_end):
                continue
            bot = manager.get(m.bot_id)
            sc = await session.get(Showcase, m.showcase_id)
            user = await session.get(User, m.user_id)
            if bot is None or sc is None:
                continue
            t = T(user.language if user else "fa")
            day = m.expires_at.strftime("%Y-%m-%d")
            if due_end:
                text, button = t["sc_sub_ended"].format(title=html.escape(sc.title)), t["btn_rejoin"]
                m.end_notified = m.reminded = True
            else:
                key = "sc_sub_ending" if m.canceled else "sc_sub_renews"
                text, button = t[key].format(title=html.escape(sc.title), date=day, price=sc.price), t["btn_open_showcase"]
                m.reminded = True
            try:
                await bot.send_message(m.user_id, text, reply_markup=open_button(sc, webapp_url, button))
                sent += 1
            except Exception:
                log.warning("Subscription message failed for membership %s", m.id)
        await session.commit()
    return sent


async def set_renewal(bot: Bot, session: AsyncSession, m: Membership, cancel: bool) -> str | None:
    """خریدار تمدید خودکار را خاموش/روشن می‌کند (تا آخر دوره‌ی فعلی عضو می‌ماند)."""
    if not m.sub_charge_id:
        return "sc_not_subscription"
    try:
        await bot.edit_user_star_subscription(user_id=m.user_id, telegram_payment_charge_id=m.sub_charge_id,
                                              is_canceled=cancel)
    except TelegramBadRequest as e:
        log.warning("Renewal change failed for membership %s: %s", m.id, e.message)
        return "renewal_failed"
    m.canceled, m.reminded = cancel, False   # یادآوری دوباره با متن درست فرستاده شود
    await session.commit()
    return None


async def showcase_stats(session: AsyncSession, sc: Showcase) -> dict:
    """آمار اعضا برای فروشنده: عضو فعال، درآمد کل و ۳۰ روز اخیر، تعداد لغو تمدید."""
    now = utcnow()
    paid = Membership.showcase_id == sc.id, Membership.refunded.is_(False)
    total = await session.scalar(select(func.coalesce(func.sum(Membership.amount), 0)).where(*paid)) or 0
    month = await session.scalar(select(func.coalesce(func.sum(Membership.amount), 0)).where(
        *paid, Membership.created_at >= (now - timedelta(days=30)).replace(tzinfo=timezone.utc))) or 0
    canceled = await session.scalar(select(func.count(Membership.id)).where(
        *paid, Membership.canceled.is_(True), Membership.expires_at > now)) or 0
    return {"members": await member_count(session, sc.id), "revenue": total, "month_revenue": month,
            "canceled": canceled}


# --- تاریخ پایان: فایل‌ها و ویترین‌ها خودکار آرشیو می‌شوند ---
async def stop_renewals(manager, session: AsyncSession, sc: Showcase) -> int:
    """ویترین آرشیو شد: تمدید خودکار همه‌ی اشتراک‌هایش خاموش می‌شود تا کسی برای ویترین تمام‌شده پول ندهد."""
    bot, done = manager.get(sc.bot_id) if manager else None, 0
    rows = (await session.scalars(select(Membership).where(
        Membership.showcase_id == sc.id, Membership.sub_charge_id.is_not(None), Membership.canceled.is_(False),
        Membership.refunded.is_(False), Membership.expires_at > utcnow()))).all()
    for m in rows:
        if bot is None:
            break
        try:
            await bot.edit_user_star_subscription(user_id=m.user_id, telegram_payment_charge_id=m.sub_charge_id,
                                                  is_canceled=True)
            m.canceled, done = True, done + 1
        except Exception:
            log.warning("Could not stop renewal for membership %s", m.id)
    return done


async def expire_tick(manager=None) -> int:
    """محصول منقضی → آرشیو (لینکش برای تازه‌واردها بسته؛ خریدارها دسترسی دارند).
    ویترین منقضی → آرشیو (عضو تازه نه؛ اعضای قبلی می‌مانند). خروجی: تعداد موارد آرشیوشده."""
    now = utcnow()
    async with SessionLocal() as session:
        contents = (await session.scalars(select(Content).where(
            Content.expires_at.is_not(None), Content.expires_at <= now, Content.is_active.is_(True)))).all()
        for c in contents:
            c.is_active = False
        shows = (await session.scalars(select(Showcase).where(
            Showcase.expires_at.is_not(None), Showcase.expires_at <= now, Showcase.archived.is_(False),
            Showcase.is_active.is_(True)))).all()
        for sc in shows:
            sc.archived = True
            await stop_renewals(manager, session, sc)
        await session.commit()
    if contents or shows:
        log.info("Expired: %s products, %s showcases archived", len(contents), len(shows))
    return len(contents) + len(shows)


def parse_expiry(value) -> datetime | None | str:
    """تاریخ پایان از Mini App (ISO، به UTC). None = بدون تاریخ؛ رشته‌ی «bad_expiry» = نامعتبر یا گذشته."""
    if value in (None, ""):
        return None
    try:
        dt = naive(datetime.fromisoformat(str(value).replace("Z", "+00:00")))
    except ValueError:
        return "bad_expiry"
    return dt if dt > utcnow() else "bad_expiry"
