"""فروش با استارز در ربات فروشنده. پول مستقیم به موجودی ربات فروشنده می‌رود، نه UploadFly.

جریان خرید: پرداخت ← دکمه‌ی «نمایش» یا «بازپرداخت». بازپرداخت فقط تا قبل از دیدن محتواست، پس فروشنده
هیچ‌وقت محتوای دیده‌شده را مجانی از دست نمی‌دهد. بعد از دیدن، خریدار فقط می‌تواند «گزارش کلاهبرداری» بدهد؛
فروشنده‌ای که گزارش زیاد بگیرد خودکار تعلیق می‌شود."""
import html
import logging
from datetime import datetime, timedelta, timezone

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import (CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo,
                           PreCheckoutQuery)
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots import BotManager
from app.config import settings
from app import creator, preview, showcases
from app.content import deliver
from app.products import invoice_args, rate
from app.db import Content, Purchase, Seller, User, cb_id, is_id
from app.middlewares import seller_bot
from app.texts import T, format_specs
from app.trust import is_blacklisted

log = logging.getLogger(__name__)

router = Router()
router.message.filter(seller_bot)
router.pre_checkout_query.filter(seller_bot)
router.callback_query.filter(seller_bot)

# قوانین (تأییدشده توسط صاحب پروژه)
REFUND_WINDOW = timedelta(hours=24)  # فقط تا قبل از باز کردن محتوا
MAX_REFUNDS_30_DAYS = 3              # هر خریدار در کل UploadFly (جلوگیری از اسپم خرید/بازپرداخت)
REPORT_WINDOW = timedelta(days=7)    # گزارش کلاهبرداری بعد از دیدن محتوا
# گزارش‌ها هیچ کار خودکاری نمی‌کنند (تصمیم مالک 2026-10-08): چند حساب با خرید ارزان می‌توانستند فروشگاهی را ببندند.
# مدیر با /reports می‌بیند و خودش با /suspend یا /takedown تصمیم می‌گیرد. «محتوای ممنوع» فوری به مدیر خبر داده می‌شود
REPORT_REASONS = ("mismatch", "broken", "forbidden", "other")


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def naive_utc(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc).replace(tzinfo=None) if dt.tzinfo else dt


async def get_purchase(session: AsyncSession, user: User, content: Content) -> Purchase | None:
    return await session.scalar(select(Purchase).where(
        Purchase.content_id == content.id, Purchase.buyer_id == user.id, Purchase.refunded.is_(False)))


def remember_message(purchase: Purchase, message_id: int) -> None:
    purchase.message_ids = f"{purchase.message_ids},{message_id}".strip(",")


def pending_markup(purchase: Purchase, lang: str) -> InlineKeyboardMarkup:
    t = T(lang)
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t["btn_open"], callback_data=f"open:{purchase.id}")],
        [InlineKeyboardButton(text=t["btn_refund"], callback_data=f"refund:{purchase.id}")],
    ])


async def send_pending(bot: Bot, chat_id: int, purchase: Purchase, lang: str) -> None:
    """خرید انجام شده ولی محتوا هنوز باز نشده: انتخاب بین نمایش و بازپرداخت."""
    await bot.send_message(chat_id, T(lang)["paid_pending"], reply_markup=pending_markup(purchase, lang))


async def open_purchase(bot: Bot, chat_id: int, purchase: Purchase, content: Content, session: AsyncSession,
                        lang: str) -> None:
    """نمایش محتوای خریده‌شده. اولین بار، بازپرداخت را می‌بندد و دکمه‌ی گزارش را می‌دهد."""
    first_time = False
    if purchase.opened_at is None:
        # یک UPDATE شرطی: اگر هم‌زمان «بازپرداخت» زده شود، فقط یکی از این دو برنده است (نه هم پول هم محتوا)
        claimed = await session.execute(update(Purchase).where(
            Purchase.id == purchase.id, Purchase.opened_at.is_(None), Purchase.refunded.is_(False))
            .values(opened_at=utcnow()))
        await session.commit()
        await session.refresh(purchase)
        first_time = claimed.rowcount == 1
    if purchase.refunded:
        return
    mark = None
    seller = await session.scalar(select(Seller).where(Seller.bot_id == content.bot_id))
    if seller is not None and seller.watermark and purchase.buyer_id != seller.owner_id:
        buyer = await session.get(User, purchase.buyer_id)
        mark = creator.mark_for(buyer) if buyer else None
    remember_message(purchase, await deliver(bot, chat_id, content, session, lang, mark=mark))
    if first_time:  # یک پیام بی‌صدا: امتیاز (۱ تا ۵) و گزارش مشکل
        await bot.send_message(chat_id, T(lang)["rate_hint"] + "\n\n" + T(lang)["report_offer"],
                               reply_markup=rating_markup(purchase.id, lang), disable_notification=True)
    await session.commit()


async def send_offer(bot: Bot, chat_id: int, content: Content, lang: str, store_url: str | None = None) -> None:
    """مشخصات تأییدشده‌ی سیستم + فاکتور استارز. خود محتوا تا قبل از پرداخت فرستاده نمی‌شود."""
    t = T(lang)
    specs = format_specs(content, lang)
    await preview.show(bot, content, chat_id, t["preview_caption_buyer"])
    protection = t["offer_saveable"] if content.allow_save and not content.is_sensitive else t["offer_protected"]
    text = t["offer"].format(specs=specs, price=content.price_stars) + "\n" + protection + "\n\n" + t["stars_offer_hint"]
    if content.title:
        text = f"<b>{html.escape(content.title)}</b>\n\n" + text
    if content.description:  # ادعای فروشنده؛ جدا از مشخصات تأییدشده‌ی سیستم
        text += "\n\n" + t["seller_says"].format(text=html.escape(content.description))
    if snippet := preview.stored(content).get("text"):
        text += "\n\n" + t["preview_text"].format(snippet=html.escape(snippet))
    await bot.send_message(chat_id, text)
    # دکمه‌ی ویترین زیر خود فاکتور (اولین دکمه‌ی فاکتور باید دکمه‌ی پرداخت باشد)
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t["btn_pay"].format(price=content.price_stars), pay=True)],
        [InlineKeyboardButton(text=t["btn_more_from_shop"], web_app=WebAppInfo(url=store_url))],
    ]) if store_url else None
    await bot.send_invoice(chat_id=chat_id, reply_markup=markup, **invoice_args(content, lang))


async def content_from_payload(session: AsyncSession, payload: str, bot_id: int) -> Content | None:
    if not payload.startswith("c:") or not is_id(payload[2:]):
        return None
    content = await session.get(Content, int(payload[2:]))
    if content is None or content.bot_id != bot_id or not content.is_active:
        return None
    return content


@router.message(Command("balance"))
async def balance(message: Message, session: AsyncSession, db_user: User, bot: Bot, seller: Seller):
    """موجودی استارز ربات فروشنده، مستقیم از خود تلگرام (فقط برای صاحب ربات)."""
    t = T(db_user.language)
    if seller.owner_id != db_user.id:
        await message.answer(t["owner_only"])
        return
    stars = await bot.get_my_star_balance()
    sales, total = (await session.execute(
        select(func.count(Purchase.id), func.coalesce(func.sum(Purchase.amount), 0))
        .where(Purchase.bot_id == bot.id, Purchase.refunded.is_(False))
    )).one()
    await message.answer(t["balance"].format(stars=stars.amount, sales=sales, total=total))


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery, session: AsyncSession, db_user: User, bot: Bot, seller: Seller):
    """آخرین بررسی قبل از کم شدن استارز: فروشگاه فعال است، محتوا هنوز فعال است و قیمت عوض نشده."""
    t = T(db_user.language)
    if seller.is_suspended:
        await query.answer(ok=False, error_message=t["shop_suspended_buyer"])
        return
    if query.invoice_payload.startswith("t:"):  # دونیت
        tip = creator.parse_tip(query.invoice_payload)
        ok = tip is not None and query.currency == "XTR" and query.total_amount == tip[0] \
            and db_user.id != seller.owner_id
        await query.answer(ok=ok, error_message=None if ok else t["pay_unavailable"])
        return
    if query.invoice_payload.startswith("s:"):  # ورود به ویترین پولی (یا بسته‌ی چندماهه)
        sc = await showcases.showcase_from_payload(session, query.invoice_payload, bot.id)
        months = (showcases.parse_payload(query.invoice_payload) or (0, None))[1]
        active = sc and await showcases.active_membership(session, sc.id, db_user.id)
        if months:   # بسته: عضویت را تمدید می‌کند؛ فقط نباید هم‌زمان اشتراک با تمدید خودکار داشته باشد
            blocked = bool(active and active.sub_charge_id and not active.canceled)
            expected = showcases.bundle_price(sc, months) if sc else None
        else:        # عضو آزمایشی می‌تواند وسط دوره‌ی آزمایشی مشترک شود
            blocked = bool(active) and not showcases.is_trial(active)
            expected = sc.price if sc else None
        ok = sc is not None and not blocked and query.currency == "XTR" and query.total_amount == expected
        await query.answer(ok=ok, error_message=None if ok else t["pay_unavailable"])
        return
    content = await content_from_payload(session, query.invoice_payload, bot.id)
    ok = (content is not None and query.currency == "XTR" and query.total_amount == content.price_stars
          and content.price_stars > 0 and not content.is_draft
          and not await is_blacklisted(session, content.file_unique_id)
          and not await get_purchase(session, db_user, content))  # دو بار پول دادن برای یک محتوا نه
    await query.answer(ok=ok, error_message=None if ok else t["pay_unavailable"])


async def joined_showcase(message: Message, session: AsyncSession, db_user: User, bot: Bot, seller: Seller,
                          webapp_url: str | None) -> None:
    """پرداخت ورودی ویترین (یک‌بار یا اولین/تمدید ماهانه) ثبت می‌شود."""
    p = message.successful_payment
    t = T(db_user.language)
    sc_id, months = showcases.parse_payload(p.invoice_payload) or (0, None)
    sc = await session.get(showcases.Showcase, sc_id)
    if sc is None or not sc.is_active or sc.archived or sc.bot_id != bot.id:
        # تمدید خودکار برای ویترینی که حذف/آرشیو شده: پول برمی‌گردد و تمدید خاموش می‌شود
        try:
            await bot.refund_star_payment(user_id=db_user.id, telegram_payment_charge_id=p.telegram_payment_charge_id)
            if p.is_recurring:
                await bot.edit_user_star_subscription(user_id=db_user.id, is_canceled=True,
                                                      telegram_payment_charge_id=p.telegram_payment_charge_id)
        except Exception:
            log.exception("Refund for closed showcase failed")
        await message.answer(t["sc_closed_refunded"].format(title=html.escape(sc.title if sc else "?"),
                                                            price=p.total_amount))
        return
    expires = (datetime.fromtimestamp(p.subscription_expiration_date, timezone.utc).replace(tzinfo=None)
               if p.subscription_expiration_date else None)
    first_time = not await session.scalar(select(showcases.Membership.id).where(
        showcases.Membership.showcase_id == sc.id, showcases.Membership.user_id == db_user.id,
        showcases.Membership.amount > 0).limit(1))
    if months:   # بسته‌ی چندماهه: از پایان عضویت فعلی (یا الان) چند ماه جلو
        active = await showcases.active_membership(session, sc.id, db_user.id)
        start = max(showcases.utcnow(), active.expires_at) if active and active.expires_at else showcases.utcnow()
        expires = start + timedelta(days=30 * months)
    sub_charge = None
    if p.is_recurring:  # اشتراک: شناسه‌ی پرداخت اول برای لغو/فعال کردن تمدید نگه داشته می‌شود
        prev = await session.scalar(select(showcases.Membership).where(
            showcases.Membership.showcase_id == sc.id, showcases.Membership.user_id == db_user.id,
            showcases.Membership.sub_charge_id.is_not(None)).order_by(showcases.Membership.id.desc()))
        sub_charge = (prev.sub_charge_id if prev and not p.is_first_recurring else p.telegram_payment_charge_id)
    session.add(showcases.Membership(showcase_id=sc.id, user_id=db_user.id, bot_id=bot.id, amount=p.total_amount,
                                     charge_id=p.telegram_payment_charge_id, expires_at=expires,
                                     sub_charge_id=sub_charge))
    await session.commit()
    url = f"{webapp_url}/?store={bot.id}&bot={bot.id}&sc={sc.code}" if webapp_url else None
    markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
        text=t["btn_open_showcase"], web_app=WebAppInfo(url=url))]]) if url else None
    renewal = bool(p.is_recurring) and not p.is_first_recurring
    await message.answer(t["sc_renewed" if renewal else "sc_joined"].format(title=html.escape(sc.title)),
                         reply_markup=markup)
    if first_time and not renewal and seller.welcome:   # پیام خوش‌آمد سازنده (بی‌صدا، بعد از تأیید عضویت)
        try:
            await bot.send_message(db_user.id, html.escape(seller.welcome), disable_notification=True)
        except Exception:
            pass
    owner = await session.get(User, seller.owner_id)
    ot = T(owner.language if owner else "fa")
    try:
        await bot.send_message(seller.owner_id, ot["sc_member_renewed" if renewal else "sc_new_member"].format(
            title=html.escape(sc.title), price=p.total_amount))
    except Exception:
        pass


@router.message(F.successful_payment)
async def paid(message: Message, session: AsyncSession, db_user: User, bot: Bot, seller: Seller,
               main_username: str, webapp_url: str | None = None):
    p = message.successful_payment
    t = T(db_user.language)
    cid = p.telegram_payment_charge_id
    if await session.scalar(select(Purchase.id).where(Purchase.charge_id == cid)) or await session.scalar(
            select(showcases.Membership.id).where(showcases.Membership.charge_id == cid)) or await session.scalar(
            select(creator.Tip.id).where(creator.Tip.charge_id == cid)):
        log.info("Duplicate payment update ignored")  # تلگرام بعد از ری‌استارت ممکن است دوباره بفرستد
        return
    if p.invoice_payload.startswith("s:"):
        await joined_showcase(message, session, db_user, bot, seller, webapp_url)
        return
    if p.invoice_payload.startswith("t:"):
        await creator.tip_paid(message, session, db_user, bot, seller)
        return
    content = await content_from_payload(session, p.invoice_payload, bot.id)
    if content is None:
        content = await session.get(Content, int(p.invoice_payload[2:]))
    purchase = Purchase(content_id=content.id, buyer_id=db_user.id, bot_id=bot.id,
                        amount=p.total_amount, charge_id=p.telegram_payment_charge_id)
    session.add(purchase)
    await session.commit()  # خرید قبل از ارسال ثبت شود تا اگر ارسال خطا داد، خریدار دوباره پول ندهد

    await send_pending(bot, message.chat.id, purchase, db_user.language)
    await message.answer(t["powered_by"].format(main=main_username), disable_notification=True)

    owner = await session.get(User, seller.owner_id)
    ot = T(owner.language)
    # اولین فروش: لحظه‌ای که فروشنده باید ببیند پول واقعاً در ربات خودش است (اعتماد)
    sales = await session.scalar(select(func.count(Purchase.id)).where(
        Purchase.bot_id == bot.id, Purchase.refunded.is_(False), Purchase.amount > 0))
    try:
        await bot.send_message(seller.owner_id, ot["first_sale" if sales == 1 else "sold"].format(
            kind=ot["kinds"].get(content.kind, content.kind), price=p.total_amount))
    except Exception:
        pass  # اگر فروشنده ربات خودش را بلاک کرده باشد


async def refund_block_reason(session: AsyncSession, purchase: Purchase, user: User) -> str | None:
    """دلیل رد بازپرداخت (کلید متن)، یا None اگر مجاز است."""
    if purchase.refunded:
        return "refund_already"
    if purchase.opened_at is not None:
        return "refund_opened"
    if utcnow() - naive_utc(purchase.created_at) > REFUND_WINDOW:
        return "refund_expired"
    recent = await session.scalar(select(func.count(Purchase.id)).where(
        Purchase.buyer_id == user.id, Purchase.refunded.is_(True),
        Purchase.refunded_at >= utcnow() - timedelta(days=30)))
    if recent >= MAX_REFUNDS_30_DAYS:
        return "refund_limit"
    return None


@router.callback_query(F.data.startswith("refund:"))
async def refund(callback: CallbackQuery, session: AsyncSession, db_user: User, bot: Bot, seller: Seller):
    t = T(db_user.language)
    purchase = await session.get(Purchase, cb_id(callback.data))
    if purchase is None or purchase.buyer_id != db_user.id or purchase.bot_id != bot.id:
        await callback.answer()
        return
    reason = await refund_purchase(bot, session, purchase, db_user, seller)
    if reason:
        await callback.answer(t[reason], show_alert=True)
        return
    await callback.message.edit_text(t["refund_done"].format(amount=purchase.amount))
    await callback.answer()


async def refund_purchase(bot: Bot, session: AsyncSession, purchase: Purchase, user: User, seller: Seller) -> str | None:
    """بازپرداخت کامل استارز (فقط قبل از دیدن محتوا). خروجی: کلید متن خطا، یا None اگر انجام شد.
    هم دکمه‌ی چت و هم Mini App از همین استفاده می‌کنند."""
    reason = await refund_block_reason(session, purchase, user)
    if reason:
        return reason
    if purchase.amount <= 0:  # باز شدن رایگانِ اعضای ویترین؛ پولی پرداخت نشده
        return "refund_failed"
    # اول در دیتابیس «برداشته» می‌شود (شرطی)، بعد پول برمی‌گردد؛ هم‌زمان با «نمایش» فقط یکی موفق است
    claimed = await session.execute(update(Purchase).where(
        Purchase.id == purchase.id, Purchase.opened_at.is_(None), Purchase.refunded.is_(False))
        .values(refunded=True, refunded_at=utcnow()))
    await session.commit()
    if claimed.rowcount != 1:
        await session.refresh(purchase)
        return "refund_already" if purchase.refunded else "refund_opened"
    try:
        await bot.refund_star_payment(user_id=user.id, telegram_payment_charge_id=purchase.charge_id)
    except TelegramBadRequest as e:
        log.warning("Refund failed for purchase %s: %s", purchase.id, e.message)
        await session.execute(update(Purchase).where(Purchase.id == purchase.id).values(refunded=False, refunded_at=None))
        await session.commit()
        await session.refresh(purchase)
        return "refund_failed"
    await session.refresh(purchase)
    log.info("Purchase %s refunded", purchase.id)
    owner = await session.get(User, seller.owner_id)
    try:
        await bot.send_message(seller.owner_id, T(owner.language)["refund_seller"].format(amount=purchase.amount))
    except Exception:
        pass
    return None


@router.callback_query(F.data.startswith("open:"))
async def open_cb(callback: CallbackQuery, session: AsyncSession, db_user: User, bot: Bot):
    purchase = await session.get(Purchase, cb_id(callback.data))
    if purchase is None or purchase.buyer_id != db_user.id or purchase.bot_id != bot.id or purchase.refunded:
        await callback.answer()
        return
    await callback.message.edit_text(T(db_user.language)["paid_opened"])
    await callback.answer()
    content = await session.get(Content, purchase.content_id)
    await open_purchase(bot, callback.message.chat.id, purchase, content, session, db_user.language)


def rating_markup(purchase_id: int, lang: str, chosen: int = 0) -> InlineKeyboardMarkup:
    stars = [InlineKeyboardButton(text=("⭐" if n <= chosen else "☆") + str(n), callback_data=f"rate:{purchase_id}:{n}")
             for n in range(1, 6)]
    return InlineKeyboardMarkup(inline_keyboard=[stars, [InlineKeyboardButton(
        text=T(lang)["btn_report"], callback_data=f"report:{purchase_id}")]])


@router.callback_query(F.data.startswith("rate:"))
async def rate_cb(callback: CallbackQuery, session: AsyncSession, db_user: User, bot: Bot):
    t = T(db_user.language)
    _, pid, n = (callback.data.split(":") + ["", ""])[:3]
    purchase = await session.get(Purchase, int(pid)) if is_id(pid) else None
    if not reportable(purchase, db_user, bot) or not n.isdigit() or not await rate(session, purchase, int(n)):
        await callback.answer(t["rate_not_allowed"], show_alert=True)
        return
    await callback.answer(t["rate_thanks"].format(n=n))
    try:
        await callback.message.edit_reply_markup(reply_markup=rating_markup(purchase.id, db_user.language, int(n)))
    except TelegramBadRequest:
        pass  # همان امتیاز دوباره زده شد


def reportable(purchase: Purchase | None, db_user: User, bot: Bot) -> bool:
    return purchase is not None and purchase.buyer_id == db_user.id and purchase.bot_id == bot.id


@router.callback_query(F.data.startswith("report:"))
async def report_cb(callback: CallbackQuery, session: AsyncSession, db_user: User, bot: Bot):
    """اول دلیل گزارش را می‌پرسد."""
    t = T(db_user.language)
    purchase = await session.get(Purchase, cb_id(callback.data))
    if not reportable(purchase, db_user, bot):
        await callback.answer()
        return
    if purchase.reported_at is not None:
        await callback.answer(t["report_already"], show_alert=True)
        return
    if purchase.opened_at is None or utcnow() - naive_utc(purchase.opened_at) > REPORT_WINDOW:
        await callback.answer(t["report_expired"], show_alert=True)
        return
    await callback.message.edit_text(t["report_choose"], reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t[f"reason_{r}"], callback_data=f"reportr:{purchase.id}:{r}")]
        for r in REPORT_REASONS]))
    await callback.answer()


@router.callback_query(F.data.startswith("reportr:"))
async def report_reason_cb(callback: CallbackQuery, session: AsyncSession, db_user: User, bot: Bot,
                           seller: Seller, manager: BotManager, main_bot_id: int):
    t = T(db_user.language)
    _, pid, reason = (callback.data.split(":") + ["", ""])[:3]
    purchase = await session.get(Purchase, int(pid)) if is_id(pid) else None
    if not reportable(purchase, db_user, bot) or reason not in REPORT_REASONS or purchase.reported_at is not None \
            or purchase.opened_at is None or utcnow() - naive_utc(purchase.opened_at) > REPORT_WINDOW:
        await callback.answer()
        return
    purchase.reported_at, purchase.report_reason = utcnow(), reason
    await session.commit()
    log.info("Purchase %s reported (%s)", purchase.id, reason)
    await callback.message.edit_text(t["report_done"])
    await callback.answer()

    owner = await session.get(User, seller.owner_id)
    ot = T(owner.language if owner else "fa")
    try:
        await bot.send_message(seller.owner_id, ot["report_seller"].format(reason=ot[f"reason_{reason}"]))
    except Exception:
        pass
    if reason == "forbidden":  # محتوای ممنوع (مثلاً سوءاستفاده از کودکان) منتظر مرور مدیر نمی‌ماند
        content = await session.get(Content, purchase.content_id)
        link = f"https://t.me/{seller.bot_username}?start={content.code}"
        main_bot = manager.get(main_bot_id)
        for admin_id in settings.admin_ids if main_bot else ():
            try:
                await main_bot.send_message(admin_id, T("fa")["admin_forbidden_report"].format(
                    bot=seller.bot_username, owner=seller.owner_id, link=link), disable_web_page_preview=True)
            except Exception:
                pass
