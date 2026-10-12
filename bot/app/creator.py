"""امکانات «صفحه‌ی سازنده» در ربات خود سازنده: دونیت، پیام خصوصی با فن‌ها (بدون لو رفتن اکانت
شخصی سازنده)، پیام پولی، پیام گروهی، پیام خوش‌آمد، فهرست فن‌ها، لایک، خبر «پست تازه» و پست زمان‌بندی‌شده.

همه‌ی پول‌ها مثل قبل مستقیم به موجودی ربات خود سازنده می‌رود. پیام گروهی و خبر پست تازه بی‌صدا فرستاده می‌شوند
(قانون اعلان‌ها) و سقف روزانه دارند تا ربات سازنده به‌خاطر اسپم گزارش نشود.
"""
import asyncio
import html
import io
import logging
import time
from datetime import datetime, timedelta, timezone

from aiogram import Bot, F, Router
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (BufferedInputFile, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice,
                           Message, ReplyParameters, WebAppInfo)
from PIL import Image as PILImage
from PIL import ImageDraw, ImageFont
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.content import deliver, extract_content
from app.db import (Broadcast, Content, DmBlock, DmLink, Follower, Membership, Purchase, Seller, SessionLocal, Showcase,
                    ShowcaseItem, Tip, User, cb_id, is_id)
from app.middlewares import seller_bot
from app.products import PRICE_PRESETS, publish
from app.texts import T
from app.trust import is_blacklisted, price_cap

log = logging.getLogger(__name__)

router = Router()
router.message.filter(F.chat.type == "private", seller_bot)
router.callback_query.filter(seller_bot)

CREATOR_CATEGORIES = ("fitness", "education", "art", "music", "photo", "cooking", "gaming", "lifestyle", "beauty",
                      "tech", "business", "other")
DM_MODES = ("all", "fans", "off")
SEGMENTS = ("all", "subscribers", "expired", "buyers")
from app.money import TIP_MAX, TIP_MIN, TIP_PRESETS  # noqa: E402  تومان
BIO_MAX, WELCOME_MAX = 300, 1000
BROADCASTS_PER_DAY = 3        # پیام گروهی: سقف روزانه‌ی هر سازنده
DM_PER_HOUR = 30              # پیام هر فن به هر سازنده در یک ساعت
HEADER_GAP = timedelta(minutes=30)  # سربرگ «پیام از …» فقط وقتی گفت‌وگو عوض شده یا مدتی گذشته
SEND_GAP = 0.05               # فاصله‌ی ارسال‌های گروهی (زیر سقف ۳۰ پیام در ثانیه‌ی تلگرام)

TASKS: set[asyncio.Task] = set()  # ارسال‌های گروهی در پس‌زمینه (تست‌ها منتظرشان می‌مانند)


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def spawn(coro) -> None:
    task = asyncio.create_task(coro)
    TASKS.add(task)
    task.add_done_callback(TASKS.discard)


async def drain() -> None:
    """منتظر همه‌ی ارسال‌های پس‌زمینه (برای تست‌ها)."""
    while TASKS:
        await asyncio.gather(*list(TASKS), return_exceptions=True)


_dm_rates: dict[tuple[int, int], list[float]] = {}


def dm_rate_ok(bot_id: int, user_id: int) -> bool:
    now = time.time()
    recent = [x for x in _dm_rates.get((bot_id, user_id), []) if now - x < 3600]
    if len(recent) >= DM_PER_HOUR:
        _dm_rates[(bot_id, user_id)] = recent
        return False
    _dm_rates[(bot_id, user_id)] = recent + [now]
    return True


def store_url(webapp_url: str | None, bot_id: int, sc_code: str | None = None) -> str | None:
    if not webapp_url:
        return None
    return f"{webapp_url}/?store={bot_id}&bot={bot_id}" + (f"&sc={sc_code}" if sc_code else "")


# ---------------- فن‌ها ----------------
async def record_follower(session: AsyncSession, seller: Seller, user_id: int) -> None:
    """هر کسی غیر از صاحب ربات که با ربات سازنده کار کند «فالوور» است (برای پیام گروهی و آمار)."""
    if user_id == seller.owner_id:
        return
    now = utcnow()
    f = await session.scalar(select(Follower).where(Follower.bot_id == seller.bot_id, Follower.user_id == user_id))
    if f is None:
        session.add(Follower(bot_id=seller.bot_id, user_id=user_id, last_seen=now))
    elif f.last_seen is None or now - f.last_seen > timedelta(hours=1):
        f.last_seen = now


async def fan_numbers(session: AsyncSession, bot_id: int) -> dict[int, int]:
    """شماره‌ی ثابت هر فن در این ربات (به ترتیب اولین آشنایی). چت ناشناس است: سازنده اسم و آیدی فن را نمی‌بیند،
    فقط «فن شماره‌ی ۳» را، تا آدم‌ها را از هم تشخیص بدهد."""
    ids = (await session.scalars(select(Follower.user_id).where(Follower.bot_id == bot_id).order_by(Follower.id))).all()
    return {uid: n for n, uid in enumerate(ids, start=1)}


async def fan_number(session: AsyncSession, seller: Seller, user_id: int) -> int:
    numbers = await fan_numbers(session, seller.bot_id)
    if user_id not in numbers:   # کسی که هنوز فالوور ثبت نشده (نباید پیش بیاید)
        await record_follower(session, seller, user_id)
        await session.flush()
        numbers = await fan_numbers(session, seller.bot_id)
    return numbers.get(user_id, 0)


async def _ids(session: AsyncSession, q) -> set[int]:
    return set((await session.scalars(q)).all())


async def fan_sets(session: AsyncSession, bot_id: int) -> dict[str, set[int]]:
    now = utcnow()
    active = await _ids(session, select(Membership.user_id).where(
        Membership.bot_id == bot_id, Membership.refunded.is_(False),
        or_(Membership.expires_at.is_(None), Membership.expires_at > now)))
    members = await _ids(session, select(Membership.user_id).where(
        Membership.bot_id == bot_id, Membership.refunded.is_(False)))
    buyers = await _ids(session, select(Purchase.buyer_id).where(
        Purchase.bot_id == bot_id, Purchase.refunded.is_(False), Purchase.amount > 0))
    buyers |= await _ids(session, select(Tip.user_id).where(Tip.bot_id == bot_id))
    followers = await _ids(session, select(Follower.user_id).where(Follower.bot_id == bot_id))
    return {"subscribers": active, "expired": members - active, "buyers": buyers,
            "all": followers | members | buyers}


async def excluded(session: AsyncSession, seller: Seller) -> set[int]:
    blocked = await _ids(session, select(DmBlock.user_id).where(DmBlock.bot_id == seller.bot_id))
    banned = await _ids(session, select(User.id).where(User.is_banned.is_(True)))
    return blocked | banned | {seller.owner_id}


async def segment_ids(session: AsyncSession, seller: Seller, segment: str) -> list[int]:
    sets = await fan_sets(session, seller.bot_id)
    return sorted(sets.get(segment, set()) - await excluded(session, seller))


async def is_fan(session: AsyncSession, bot_id: int, user_id: int) -> bool:
    """خریدار، عضو (حتی قدیمی) یا دونیت‌دهنده‌ی این سازنده."""
    for q in (select(Purchase.id).where(Purchase.bot_id == bot_id, Purchase.buyer_id == user_id,
                                        Purchase.refunded.is_(False)),
              select(Membership.id).where(Membership.bot_id == bot_id, Membership.user_id == user_id,
                                          Membership.refunded.is_(False)),
              select(Tip.id).where(Tip.bot_id == bot_id, Tip.user_id == user_id)):
        if await session.scalar(q.limit(1)):
            return True
    return False


async def fans_view(session: AsyncSession, seller: Seller) -> dict:
    """فهرست فن‌ها برای سازنده: خرج کل، وضعیت اشتراک، آخرین فعالیت. + تعداد هر گروه."""
    bot_id = seller.bot_id
    spent: dict[int, int] = {}
    last: dict[int, datetime] = {}

    def add(uid, amount, created):
        spent[uid] = spent.get(uid, 0) + (amount or 0)
        if created is not None:
            c = created.astimezone(timezone.utc).replace(tzinfo=None) if created.tzinfo else created
            last[uid] = max(last.get(uid, c), c)

    for uid, amount, created in (await session.execute(select(Purchase.buyer_id, Purchase.amount, Purchase.created_at)
                                                       .where(Purchase.bot_id == bot_id, Purchase.refunded.is_(False)))).all():
        add(uid, amount, created)
    for uid, amount, created in (await session.execute(select(Membership.user_id, Membership.amount, Membership.created_at)
                                                       .where(Membership.bot_id == bot_id, Membership.refunded.is_(False)))).all():
        add(uid, amount, created)
    for uid, amount, created in (await session.execute(select(Tip.user_id, Tip.amount, Tip.created_at)
                                                       .where(Tip.bot_id == bot_id))).all():
        add(uid, amount, created)
    sets = await fan_sets(session, bot_id)
    skip = await excluded(session, seller)
    blocked = await _ids(session, select(DmBlock.user_id).where(DmBlock.bot_id == bot_id))
    ids = [u for u in spent if u != seller.owner_id]
    ids.sort(key=lambda u: (spent[u], last.get(u, datetime.min)), reverse=True)
    numbers = await fan_numbers(session, bot_id)
    rows = []
    for uid in ids[:300]:
        status = "subscriber" if uid in sets["subscribers"] else "expired" if uid in sets["expired"] else "buyer"
        # ناشناس: به سازنده فقط شماره‌ی فن نشان داده می‌شود (id فقط داخل سرور؛ API آن را حذف می‌کند)
        rows.append({"id": uid, "number": numbers.get(uid, 0),
                     "spent": spent[uid], "status": status, "blocked": uid in blocked,
                     "last": last[uid].date().isoformat() if uid in last else None})
    return {"fans": rows, "counts": {k: len(v - skip) for k, v in sets.items()},
            "followers": len(sets["all"] - skip)}


async def earnings(session: AsyncSession, bot_id: int) -> dict:
    """درآمد به تفکیک: فروش پست، اشتراک/ورودی، دونیت (کل و ۳۰ روز اخیر)."""
    since = (utcnow() - timedelta(days=30)).replace(tzinfo=timezone.utc)

    async def total(col, *where):
        return int(await session.scalar(select(func.coalesce(func.sum(col), 0)).where(*where)) or 0)

    sales = (Purchase.bot_id == bot_id, Purchase.refunded.is_(False), Purchase.amount > 0)
    subs = (Membership.bot_id == bot_id, Membership.refunded.is_(False), Membership.amount > 0)
    tips = (Tip.bot_id == bot_id,)
    return {
        "sales": await total(Purchase.amount, *sales), "subs": await total(Membership.amount, *subs),
        "tips": await total(Tip.amount, *tips),
        "month": {"sales": await total(Purchase.amount, *sales, Purchase.created_at >= since),
                  "subs": await total(Membership.amount, *subs, Membership.created_at >= since),
                  "tips": await total(Tip.amount, *tips, Tip.created_at >= since)},
    }


# ---------------- دونیت ----------------
def tip_invoice_args(amount: int, lang: str, content_id: int | None = None) -> dict:
    t = T(lang)
    return {"title": t["tip_title"][:32], "description": t["tip_desc"][:255],
            "payload": f"t:{amount}" + (f":{content_id}" if content_id else ""), "currency": "XTR",
            "prices": [LabeledPrice(label=t["tip_title"], amount=amount)]}


def parse_tip(payload: str) -> tuple[int, int | None] | None:
    parts = payload.split(":")
    if len(parts) not in (2, 3) or parts[0] != "t" or not all(is_id(p) for p in parts[1:]):
        return None
    amount = int(parts[1])
    if not TIP_MIN <= amount <= TIP_MAX:
        return None
    return amount, (int(parts[2]) if len(parts) == 3 else None)


def tip_markup(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"{a:,}", callback_data=f"tip:{a}")
                                                  for a in TIP_PRESETS]])


@router.message(Command("donate", "tip"))
async def tip_cmd(message: Message, db_user: User, seller: Seller):
    t = T(db_user.language)
    if seller.owner_id == db_user.id:
        await message.answer(t["tip_owner_self"])
        return
    await message.answer(t["tip_choose"], reply_markup=tip_markup(db_user.language))


@router.callback_query(F.data.startswith("tip:"))
async def tip_chosen(callback: CallbackQuery, db_user: User, bot: Bot, seller: Seller):
    amount = cb_id(callback.data)
    await callback.answer()
    if amount not in TIP_PRESETS or seller.is_suspended or seller.owner_id == db_user.id:
        return
    await bot.send_invoice(chat_id=callback.from_user.id, **tip_invoice_args(amount, db_user.language))


async def tip_paid(message: Message, session: AsyncSession, db_user: User, bot: Bot, seller: Seller) -> None:
    p = message.successful_payment
    parsed = parse_tip(p.invoice_payload)
    amount, content_id = parsed if parsed else (p.total_amount, None)
    session.add(Tip(bot_id=bot.id, user_id=db_user.id, content_id=content_id, amount=p.total_amount,
                    charge_id=p.telegram_payment_charge_id))
    await session.commit()
    await message.answer(T(db_user.language)["tip_thanks"].format(amount=p.total_amount))
    owner = await session.get(User, seller.owner_id)
    ot = T(owner.language if owner else "fa")
    try:  # پول تازه: اعلان با صدا
        await bot.send_message(seller.owner_id, ot["tip_owner"].format(
            amount=p.total_amount, name=ot["fan_alias"].format(n=await fan_number(session, seller, db_user.id))))
    except Exception:
        pass


# ---------------- پیام خصوصی ----------------
def reply_to(message_id: int | None) -> ReplyParameters | None:
    """Reply به پیام قبلی همان گفت‌وگو؛ اگر پاک شده باشد، پیام بدون Reply می‌رود."""
    return ReplyParameters(message_id=message_id, allow_sending_without_reply=True) if message_id else None


async def dm_block_reason(session: AsyncSession, seller: Seller, user_id: int) -> str | None:
    """چرا این کاربر نمی‌تواند به سازنده پیام بدهد (کلید متن)، یا None."""
    blocked = await session.scalar(select(DmBlock.id).where(DmBlock.bot_id == seller.bot_id, DmBlock.user_id == user_id))
    if seller.dm_mode == "off" or blocked:
        return "dm_off"
    if seller.dm_mode == "fans" and not await is_fan(session, seller.bot_id, user_id):
        return "dm_fans_only"
    return None


async def fan_message(message: Message, session: AsyncSession, db_user: User, bot: Bot, seller: Seller,
                      webapp_url: str | None) -> None:
    """پیام فن به سازنده: از ربات به سازنده می‌رسد؛ سازنده با «پاسخ» (Reply) جواب می‌دهد.
    اگر فن روی جواب سازنده Reply بزند، پیامش هم برای سازنده Reply روی همان پیام می‌آید (گفت‌وگوی رشته‌ای)."""
    t = T(db_user.language)
    reason = await dm_block_reason(session, seller, db_user.id)
    if reason == "dm_off":
        await message.reply(t["dm_off"])
        return
    if reason == "dm_fans_only":
        url = store_url(webapp_url, bot.id)
        markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
            text=t["btn_open_store"], web_app=WebAppInfo(url=url))]]) if url else None
        await message.reply(t["dm_fans_only"], reply_markup=markup)
        return
    if not dm_rate_ok(bot.id, db_user.id):
        await message.reply(t["dm_slow"])
        return
    owner = await session.get(User, seller.owner_id)
    ot = T(owner.language if owner else "fa")
    last = await session.scalar(select(DmLink).where(DmLink.bot_id == bot.id).order_by(DmLink.id.desc()).limit(1))
    created = last.created_at if last else None
    if created is not None and created.tzinfo:
        created = created.astimezone(timezone.utc).replace(tzinfo=None)
    fresh = last is None or last.fan_id != db_user.id or created is None or utcnow() - created > HEADER_GAP
    try:
        if fresh:
            spent = sum(r["spent"] for r in (await fans_view(session, seller))["fans"] if r["id"] == db_user.id)
            who = ot["fan_alias"].format(n=await fan_number(session, seller, db_user.id))   # ناشناس: نه اسم، نه آیدی
            header = await bot.send_message(seller.owner_id, ot["dm_from"].format(name=who, spent=spent),
                                            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
                                                text=ot["btn_dm_block"], callback_data=f"dmblock:{db_user.id}")]]))
            session.add(DmLink(bot_id=bot.id, owner_message_id=header.message_id, fan_id=db_user.id))
        target = None
        if message.reply_to_message:   # فن روی جواب سازنده Reply زده
            target = await session.scalar(select(DmLink.owner_message_id).where(
                DmLink.bot_id == bot.id, DmLink.fan_id == db_user.id,
                DmLink.fan_message_id == message.reply_to_message.message_id).order_by(DmLink.id.desc()).limit(1))
        copied = await bot.copy_message(chat_id=seller.owner_id, from_chat_id=message.chat.id,
                                        message_id=message.message_id, reply_parameters=reply_to(target))
    except Exception:
        log.warning("DM relay failed for bot %s", bot.id)
        await message.reply(t["dm_failed"])
        return
    session.add(DmLink(bot_id=bot.id, owner_message_id=copied.message_id, fan_id=db_user.id,
                       fan_message_id=message.message_id))
    await session.commit()
    if fresh:
        await message.reply(t["dm_sent"], disable_notification=True)


@router.callback_query(F.data.startswith("dmblock:"))
async def dm_block(callback: CallbackQuery, session: AsyncSession, db_user: User, bot: Bot, seller: Seller):
    t = T(db_user.language)
    fan = cb_id(callback.data)
    if seller.owner_id != db_user.id or not fan:
        await callback.answer()
        return
    row = await session.scalar(select(DmBlock).where(DmBlock.bot_id == bot.id, DmBlock.user_id == fan))
    if row is None:
        session.add(DmBlock(bot_id=bot.id, user_id=fan))
        text, button = t["dm_blocked"], t["btn_dm_unblock"]
    else:
        await session.delete(row)
        text, button = t["dm_unblocked"], t["btn_dm_block"]
    await session.commit()
    await callback.answer(text, show_alert=True)
    try:
        await callback.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=button, callback_data=f"dmblock:{fan}")]]))
    except Exception:
        pass


def ppv_markup(content_id: int, target: str, cap: int, lang: str) -> InlineKeyboardMarkup:
    """قیمت پیام پولی: رایگان یا یکی از قیمت‌های زیر سقف اعتماد. target: شناسه‌ی فن یا «b» (پیام گروهی)."""
    t = T(lang)
    prices = [p for p in PRICE_PRESETS if p <= cap]
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t["btn_ppv_free"], callback_data=f"ppv:{content_id}:{target}:0")],
        [InlineKeyboardButton(text=f"🔒 {p:,}", callback_data=f"ppv:{content_id}:{target}:{p}") for p in prices[:3]],
        *([[InlineKeyboardButton(text=f"🔒 {p:,}", callback_data=f"ppv:{content_id}:{target}:{p}") for p in prices[3:]]]
          if prices[3:] else []),
        [InlineKeyboardButton(text=t["btn_cancel"], callback_data=f"ppv:{content_id}:{target}:x")],
    ])


async def new_draft(session: AsyncSession, message: Message, bot: Bot, owner_id: int) -> Content | str:
    from app.handlers import new_code
    data = extract_content(message)
    if data is None:
        return "unsupported"
    if await is_blacklisted(session, data.get("file_unique_id")):
        return "file_blacklisted"
    c = Content(code=await new_code(session), bot_id=bot.id, owner_id=owner_id, is_active=False, is_draft=True,
                in_store=False, **data)
    session.add(c)
    await session.commit()
    return c


@router.message(F.reply_to_message)
async def owner_reply(message: Message, session: AsyncSession, db_user: User, bot: Bot, seller: Seller,
                      state: FSMContext):
    """سازنده روی پیام یک فن «پاسخ» زده: متن مستقیم می‌رود؛ عکس/ویدیو/فایل اول قیمت می‌پرسد (پیام پولی)."""
    if seller.owner_id != db_user.id:
        raise SkipHandler()
    link = await session.scalar(select(DmLink).where(
        DmLink.bot_id == bot.id, DmLink.owner_message_id == message.reply_to_message.message_id)
        .order_by(DmLink.id.desc()).limit(1))
    if link is None:
        raise SkipHandler()
    if await state.get_state() is not None:   # Reply روی پیام فن یعنی جواب؛ کار نیمه‌کاره‌ی قبلی (مثلاً قیمت) کنار می‌رود
        await state.clear()
    t = T(db_user.language)
    if message.text or message.sticker or message.voice or message.video_note:   # جواب معمولی، مثل چت ناشناس
        try:
            sent = await bot.copy_message(chat_id=link.fan_id, from_chat_id=message.chat.id, message_id=message.message_id,
                                          protect_content=True, reply_parameters=reply_to(link.fan_message_id))
        except Exception:
            await message.reply(t["dm_reply_failed"])
            return
        # پیام خود سازنده هم ثبت می‌شود: فن روی آن Reply بزند → برای سازنده Reply روی همین پیام می‌آید
        session.add(DmLink(bot_id=bot.id, owner_message_id=message.message_id, fan_id=link.fan_id,
                           fan_message_id=sent.message_id))
        await session.commit()
        return
    draft = await new_draft(session, message, bot, db_user.id)
    if isinstance(draft, str):
        await message.reply(t[draft])
        return
    await message.reply(t["ppv_choose"], reply_markup=ppv_markup(
        draft.id, str(link.fan_id), await price_cap(session, bot.id), db_user.language))


@router.callback_query(F.data.startswith("ppv:"))
async def ppv_chosen(callback: CallbackQuery, session: AsyncSession, db_user: User, bot: Bot, seller: Seller,
                     state: FSMContext, webapp_url: str | None = None):
    t = T(db_user.language)
    _, cid, target, value = (callback.data.split(":") + ["", "", ""])[:4]
    c = await session.get(Content, int(cid)) if is_id(cid) else None
    if seller.owner_id != db_user.id or c is None or c.bot_id != bot.id or not c.is_draft:
        await callback.answer()
        return
    await callback.answer()
    if value == "x":
        await session.delete(c)
        await session.commit()
        await callback.message.edit_text(t["canceled"])
        return
    if not value.isdigit() or int(value) > await price_cap(session, bot.id):
        return
    price = int(value)
    await callback.message.edit_reply_markup(reply_markup=None)
    if target == "b":   # پیام گروهی
        data = await state.get_data()
        segment = data.get("segment")
        await state.clear()
        if segment not in SEGMENTS:
            return
        await start_broadcast(callback.message, session, db_user, bot, seller, segment, content=c, price=price,
                              webapp_url=webapp_url)
        return
    if not is_id(target, big=True):
        return
    fan = await session.get(User, int(target))
    if fan is None:
        return
    if price == 0:
        c.is_draft, c.is_active, c.price_stars = False, True, 0
        await session.commit()
        try:
            await deliver(bot, fan.id, c, session, fan.language)
        except Exception:
            await callback.message.answer(t["dm_reply_failed"])
            return
    else:
        await publish(bot, callback.message.chat.id, c, price, db_user.language)
        await session.commit()
        from app.payments import send_offer
        try:
            await bot.send_message(fan.id, T(fan.language)["ppv_intro"])
            await send_offer(bot, fan.id, c, fan.language, store_url(webapp_url, bot.id))
        except Exception:
            await callback.message.answer(t["dm_reply_failed"])
            return
    await callback.message.answer(t["ppv_sent"], disable_notification=True)


# ---------------- پیام گروهی ----------------
class Broadcasting(StatesGroup):
    waiting = State()


async def broadcasts_today(session: AsyncSession, bot_id: int) -> int:
    since = (utcnow() - timedelta(days=1)).replace(tzinfo=timezone.utc)
    return await session.scalar(select(func.count(Broadcast.id)).where(
        Broadcast.bot_id == bot_id, Broadcast.created_at >= since)) or 0


async def broadcast_menu(message: Message, session: AsyncSession, db_user: User, bot: Bot, seller: Seller) -> None:
    t = T(db_user.language)
    if seller.owner_id != db_user.id:
        await message.answer(t["owner_only"])
        return
    if await broadcasts_today(session, bot.id) >= BROADCASTS_PER_DAY:
        await message.answer(t["bc_limit"].format(n=BROADCASTS_PER_DAY))
        return
    counts = {s: len(await segment_ids(session, seller, s)) for s in SEGMENTS}
    await message.answer(t["bc_choose"], reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t[f"seg_{s}"].format(n=counts[s]), callback_data=f"bc:{s}")] for s in SEGMENTS]))


@router.message(Command("broadcast"))
async def broadcast_cmd(message: Message, session: AsyncSession, db_user: User, bot: Bot, seller: Seller):
    await broadcast_menu(message, session, db_user, bot, seller)


@router.callback_query(F.data.startswith("bc:"))
async def broadcast_segment(callback: CallbackQuery, session: AsyncSession, db_user: User, bot: Bot, seller: Seller,
                            state: FSMContext):
    t = T(db_user.language)
    segment = callback.data[3:]
    if seller.owner_id != db_user.id or segment not in SEGMENTS:
        await callback.answer()
        return
    n = len(await segment_ids(session, seller, segment))
    await callback.answer()
    if not n:
        await callback.message.edit_text(t["bc_empty"])
        return
    await state.set_state(Broadcasting.waiting)
    await state.update_data(segment=segment)
    await callback.message.edit_text(t["bc_send_now"].format(n=n))


@router.message(StateFilter(Broadcasting.waiting), Command("cancel"))
async def broadcast_cancel(message: Message, db_user: User, state: FSMContext):
    await state.clear()
    await message.answer(T(db_user.language)["canceled"])


@router.message(StateFilter(Broadcasting.waiting))
async def broadcast_message(message: Message, session: AsyncSession, db_user: User, bot: Bot, seller: Seller,
                            state: FSMContext):
    t = T(db_user.language)
    if seller.owner_id != db_user.id:
        raise SkipHandler()
    segment = (await state.get_data()).get("segment")
    n = len(await segment_ids(session, seller, segment))
    if message.text:   # متن: یک تأیید و ارسال
        await message.reply(t["bc_confirm"].format(n=n), reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t["btn_bc_send"].format(n=n), callback_data=f"bcgo:{message.message_id}")],
            [InlineKeyboardButton(text=t["btn_cancel"], callback_data="bcgo:x")]]))
        return
    draft = await new_draft(session, message, bot, db_user.id)
    if isinstance(draft, str):
        await message.reply(t[draft])
        return
    await message.reply(t["bc_ppv_choose"].format(n=n), reply_markup=ppv_markup(
        draft.id, "b", await price_cap(session, bot.id), db_user.language))


@router.callback_query(F.data.startswith("bcgo:"))
async def broadcast_go(callback: CallbackQuery, session: AsyncSession, db_user: User, bot: Bot, seller: Seller,
                       state: FSMContext, webapp_url: str | None = None):
    t = T(db_user.language)
    if seller.owner_id != db_user.id:
        await callback.answer()
        return
    await callback.answer()
    segment = (await state.get_data()).get("segment")
    await state.clear()
    ref = callback.data[5:]
    if ref == "x" or not ref.isdigit() or segment not in SEGMENTS:
        await callback.message.edit_text(t["canceled"])
        return
    await callback.message.edit_reply_markup(reply_markup=None)
    await start_broadcast(callback.message, session, db_user, bot, seller, segment, message_id=int(ref),
                          webapp_url=webapp_url)


async def start_broadcast(where: Message, session: AsyncSession, db_user: User, bot: Bot, seller: Seller, segment: str,
                          message_id: int | None = None, content: Content | None = None, price: int = 0,
                          webapp_url: str | None = None) -> None:
    t = T(db_user.language)
    if await broadcasts_today(session, bot.id) >= BROADCASTS_PER_DAY:
        await where.answer(t["bc_limit"].format(n=BROADCASTS_PER_DAY))
        return
    ids = await segment_ids(session, seller, segment)
    if content is not None:
        if price:
            await publish(bot, where.chat.id, content, price, db_user.language)
        else:
            content.is_draft, content.is_active, content.price_stars = False, True, 0
    row = Broadcast(bot_id=bot.id, segment=segment, content_id=content.id if content else None, total=len(ids))
    session.add(row)
    await session.commit()
    await where.answer(t["bc_started"].format(n=len(ids)), disable_notification=True)
    spawn(run_broadcast(bot, seller.owner_id, row.id, ids, message_id, content.id if content else None,
                        webapp_url, db_user.language))


async def run_broadcast(bot: Bot, owner_id: int, broadcast_id: int, ids: list[int], message_id: int | None,
                        content_id: int | None, webapp_url: str | None, owner_lang: str) -> int:
    from app.payments import send_offer
    sent = 0
    async with SessionLocal() as session:
        content = await session.get(Content, content_id) if content_id else None
        langs = dict((await session.execute(select(User.id, User.language).where(User.id.in_(ids or [0])))).all())
        for uid in ids:
            lang = langs.get(uid, "fa")
            try:
                if content is None:
                    await bot.copy_message(chat_id=uid, from_chat_id=owner_id, message_id=message_id,
                                           protect_content=True, disable_notification=True)
                elif content.price_stars:
                    await bot.send_message(uid, T(lang)["ppv_intro"], disable_notification=True)
                    await send_offer(bot, uid, content, lang, store_url(webapp_url, bot.id))
                else:
                    await deliver(bot, uid, content, session, lang)
                sent += 1
            except Exception:
                pass   # فن ربات را بلاک کرده
            await asyncio.sleep(SEND_GAP)
        row = await session.get(Broadcast, broadcast_id)
        if row:
            row.sent = sent
        await session.commit()
    try:
        await bot.send_message(owner_id, T(owner_lang)["bc_done"].format(sent=sent, total=len(ids)),
                               disable_notification=True)
    except Exception:
        pass
    return sent


# ---------------- خبر «پست تازه» و پست زمان‌بندی‌شده ----------------
async def post_audience(session: AsyncSession, seller: Seller, c: Content) -> tuple[list[int], str | None]:
    """مشترکین فعال ویترین‌هایی که این پست را دارند؛ اگر در ویترین اصلی است، همه‌ی فن‌ها و فالوورها."""
    now = utcnow()
    sc_rows = (await session.execute(select(Showcase.id, Showcase.code).join(
        ShowcaseItem, ShowcaseItem.showcase_id == Showcase.id).where(
        ShowcaseItem.content_id == c.id, Showcase.is_active.is_(True), Showcase.archived.is_(False)))).all()
    ids: set[int] = set()
    if sc_rows:
        ids |= await _ids(session, select(Membership.user_id).where(
            Membership.showcase_id.in_([r[0] for r in sc_rows]), Membership.refunded.is_(False),
            or_(Membership.expires_at.is_(None), Membership.expires_at > now)))
    if c.in_store:
        ids |= (await fan_sets(session, seller.bot_id))["all"]
    code = None if c.in_store or not sc_rows else sc_rows[0][1]
    return sorted(ids - await excluded(session, seller)), code


async def notify_new_post(bot: Bot, seller: Seller, c: Content, webapp_url: str | None) -> int:
    """یک بار برای هر پست؛ بی‌صدا. خروجی: تعداد گیرنده‌ها."""
    async with SessionLocal() as session:
        ids, code = await post_audience(session, seller, c)
        owner = await session.get(User, seller.owner_id)
        langs = dict((await session.execute(select(User.id, User.language).where(User.id.in_(ids or [0])))).all())
    name = html.escape((owner.first_name if owner else "") or f"@{seller.bot_username}")
    title = html.escape(c.title or "")
    url = store_url(webapp_url, seller.bot_id, code)

    async def run():
        for uid in ids:
            t = T(langs.get(uid, "fa"))
            markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
                text=t["btn_see_post"], web_app=WebAppInfo(url=url))]]) if url else None
            try:
                await bot.send_message(uid, t["new_post"].format(name=name, title=title), reply_markup=markup,
                                       disable_notification=True)
            except Exception:
                pass
            await asyncio.sleep(SEND_GAP)
    spawn(run())
    return len(ids)


async def publish_due(manager) -> int:
    """پیش‌نویس‌هایی که زمان انتشارشان رسیده منتشر می‌شوند (پیش‌نمایش موقع زمان‌بندی ساخته شده)."""
    now = utcnow()
    async with SessionLocal() as session:
        rows = (await session.scalars(select(Content).where(
            Content.is_draft.is_(True), Content.publish_at.is_not(None), Content.publish_at <= now))).all()
        done = []
        for c in rows:
            c.is_draft, c.is_active, c.publish_at = False, True, None
            done.append(c)
        await session.commit()
        for c in done:
            seller = await session.scalar(select(Seller).where(Seller.bot_id == c.bot_id))
            owner = await session.get(User, c.owner_id)
            bot = manager.get(c.bot_id) if manager else None
            if bot is None or seller is None:
                continue
            try:
                await bot.send_message(c.owner_id, T(owner.language if owner else "fa")["scheduled_live"].format(
                    title=html.escape(c.title or c.file_name or "")), disable_notification=True)
            except Exception:
                pass
    return len(done)


# ---------------- واترمارک ----------------
def watermark_photo(raw: bytes, text: str) -> bytes:
    """یوزرنیم/شناسه‌ی خریدار کم‌رنگ و مورب روی کل عکس؛ اگر عکس پخش شود، معلوم است از کیست."""
    im = PILImage.open(io.BytesIO(raw)).convert("RGBA")
    layer = PILImage.new("RGBA", im.size, (0, 0, 0, 0))
    size = max(14, min(im.size) // 18)
    try:
        font = ImageFont.load_default(size=size)
    except TypeError:
        font = ImageFont.load_default()
    d = ImageDraw.Draw(layer)
    step_x, step_y = size * (len(text) // 2 + 6), size * 5
    for y in range(-im.size[1], im.size[1] * 2, step_y):
        for x in range(-im.size[0], im.size[0] * 2, step_x):
            d.text((x + (y // step_y % 2) * step_x // 2, y), text, font=font, fill=(255, 255, 255, 70),
                   stroke_width=1, stroke_fill=(0, 0, 0, 50))
    layer = layer.rotate(25, resample=PILImage.BICUBIC, center=(im.size[0] / 2, im.size[1] / 2))
    out = io.BytesIO()
    PILImage.alpha_composite(im, layer).convert("RGB").save(out, "JPEG", quality=88)
    return out.getvalue()


async def send_watermarked(bot: Bot, chat_id: int, c: Content, mark: str) -> int | None:
    """عکس با واترمارک؛ اگر نشد None (فرستنده همان عکس عادی را می‌فرستد)."""
    if c.kind != "photo" or not c.file_id or (c.file_size or 0) > 20 * 1024 * 1024:
        return None
    try:
        raw = (await bot.download(c.file_id)).read()
        data = await asyncio.to_thread(watermark_photo, raw, mark)
        m = await bot.send_photo(chat_id, BufferedInputFile(data, "photo.jpg"), caption=c.text,
                                 protect_content=True)
        return m.message_id
    except Exception:
        log.warning("Watermark failed for content %s", c.id)
        return None


def mark_for(user: User) -> str:
    return f"@{user.username}" if user.username else f"id {user.id}"
