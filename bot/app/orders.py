"""کالای فیزیکی در بازوی فروشنده: کارت محصول، فرم سفارش (نام، موبایل، نشانی، کد پستی)، فاکتور،
خبر به فروشنده، ثبت ارسال و کد رهگیری، فهرست سفارش‌ها و موجودی.

تفاوت با محتوای دیجیتال: چیزی در چت «تحویل» نمی‌شود؛ خریدار نشانی می‌دهد و فروشنده پست می‌کند. پول مثل
همیشه مستقیم به کیف پول بله‌ی خود فروشنده می‌رود، پس ما نمی‌توانیم پولی را نگه داریم یا برگردانیم: حفاظت خریدار
همان سقف قیمت تدریجی، امتیاز خریدارهای قبلی و گزارش («کالا نرسیده») است که مدیر بررسی می‌کند.
هر سفارش یک Purchase هم می‌سازد (مبلغ کل) تا آمار فروش، کیف پول، امتیاز و گزارش همان مسیر همیشگی را بروند.
"""
import html
import logging
import re
from datetime import datetime, timezone

from aiogram import Bot, F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Content, Order, Purchase, Seller, User, cb_id, is_id
from app.middlewares import seller_bot
from app.money import toman
from app.products import display_title
from app.texts import T

log = logging.getLogger(__name__)

router = Router()
router.message.filter(F.chat.type == "private", seller_bot)
router.callback_query.filter(seller_bot)

NAME_MIN, NAME_MAX = 3, 80
ADDRESS_MIN, ADDRESS_MAX = 10, 500
TRACKING_MAX = 64
STOCK_MAX = 100_000
CAPTION_MAX = 1000          # سقف کپشن عکس در بله/تلگرام ۱۰۲۴ است
_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


class OrderForm(StatesGroup):
    name = State()
    phone = State()
    address = State()
    postal = State()


class ShipForm(StatesGroup):
    tracking = State()


class StockForm(StatesGroup):
    amount = State()


FORM_STATES = (OrderForm.name, OrderForm.phone, OrderForm.address, OrderForm.postal, ShipForm.tracking,
               StockForm.amount)


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def latin_digits(text: str) -> str:
    return (text or "").translate(_DIGITS)


def clean_phone(text: str) -> str | None:
    """موبایل ایران به شکل 09xxxxxxxxx (با رقم فارسی، فاصله، خط تیره، +98 یا 0098 هم پذیرفته می‌شود)."""
    p = re.sub(r"[\s\-()]", "", latin_digits(text))
    p = re.sub(r"^(?:\+98|0098|98)(?=9\d{9}$)", "0", p)
    return p if re.fullmatch(r"09\d{9}", p) else None


def clean_postal(text: str) -> str | None:
    p = re.sub(r"[\s\-]", "", latin_digits(text))
    return p if re.fullmatch(r"\d{10}", p) else None


def in_stock(c: Content) -> bool:
    return c.stock is None or c.stock > 0


def order_total(c: Content, seller: Seller) -> int:
    return c.price_stars + (seller.shipping_fee or 0)


def stock_label(c: Content, t: dict) -> str:
    return t["stock_unlimited"] if c.stock is None else str(c.stock)


# ---------------- کارت محصول ----------------
def card_text(c: Content, seller: Seller, lang: str) -> str:
    t = T(lang)
    lines = [f"<b>{html.escape(display_title(c, lang))}</b>"]
    about = c.description and html.escape(c.description) or (c.text if c.kind != "text" else None)
    if about:
        lines.append(about)
    lines.append("")
    lines.append(t["pc_price"].format(price=c.price_stars))
    fee = seller.shipping_fee or 0
    lines.append(t["pc_ship"].format(fee=fee) if fee else t["pc_ship_free"])
    if not c.is_active or not in_stock(c):
        lines.append(t["pc_out"])
    elif c.stock is not None:
        lines.append(t["pc_stock"].format(n=c.stock))
    text = "\n".join(lines)
    return text if len(text) <= CAPTION_MAX else text[:CAPTION_MAX - 1] + "…"


async def send_card(bot: Bot, chat_id: int, c: Content, seller: Seller, lang: str, owner_view: bool) -> None:
    """عکس واقعی محصول (نه پیش‌نمایش تار) + قیمت، هزینه‌ی ارسال، موجودی و دکمه‌ی سفارش."""
    t = T(lang)
    if owner_view:
        rows = [[InlineKeyboardButton(text=t["btn_stock"].format(stock=stock_label(c, t)), callback_data=f"stock:{c.id}")]]
    elif seller.is_suspended or not c.is_active or not in_stock(c):
        rows = []
    else:
        rows = [[InlineKeyboardButton(text=t["btn_order"], callback_data=f"order:{c.id}")]]
    markup = InlineKeyboardMarkup(inline_keyboard=rows) if rows else None
    text = card_text(c, seller, lang)
    if owner_view:
        text += "\n\n" + t["pc_owner_note"]
    if c.kind == "photo":
        await bot.send_photo(chat_id, c.file_id, caption=text, reply_markup=markup)
    elif c.kind == "video":
        await bot.send_video(chat_id, c.file_id, caption=text, reply_markup=markup)
    elif c.kind == "animation":
        await bot.send_animation(chat_id, c.file_id, caption=text, reply_markup=markup)
    else:  # متن (توضیح محصول همان متن است) یا هر نوع دیگر: کارت متنی
        body = text if c.kind != "text" else f"{c.text}\n\n{text}"
        await bot.send_message(chat_id, body[:4000], reply_markup=markup)


async def orderable(session: AsyncSession, content_id: int, bot: Bot, seller: Seller, user: User) -> Content | None:
    c = await session.get(Content, content_id)
    if c is None or c.bot_id != bot.id or not c.is_physical or c.is_draft or not c.is_active or not in_stock(c) \
            or c.price_stars <= 0 or seller.is_suspended or c.owner_id == user.id:
        return None
    return c


# ---------------- فرم سفارش ----------------
def address_lines(o) -> str:
    return (f"👤 {html.escape(o['name'])}\n📞 {o['phone']}\n📍 {html.escape(o['address'])}\n"
            f"📮 {o.get('postal') or '—'}")


@router.callback_query(F.data.startswith("order:"))
async def order_start(callback: CallbackQuery, session: AsyncSession, db_user: User, bot: Bot, seller: Seller,
                      state: FSMContext):
    t = T(db_user.language)
    c = await orderable(session, cb_id(callback.data), bot, seller, db_user)
    await callback.answer()
    if c is None:
        mine = seller.owner_id == db_user.id   # فروشنده روی کارت محصول خودش زده
        await callback.message.answer(t["order_own" if mine else "order_unavailable"])
        return
    await state.clear()
    last = await session.scalar(select(Order).where(Order.buyer_id == db_user.id, Order.status != "pending")
                                .order_by(Order.id.desc()))
    if last is not None:   # نشانی سفارش قبلی خود همین خریدار (در هر فروشگاهی)
        await state.update_data(content_id=c.id, name=last.name, phone=last.phone, address=last.address,
                                postal=last.postal_code)
        info = address_lines({"name": last.name, "phone": last.phone, "address": last.address, "postal": last.postal_code})
        await callback.message.answer(t["of_reuse"].format(info=info), reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t["btn_same_address"], callback_data=f"ordersame:{c.id}")],
            [InlineKeyboardButton(text=t["btn_new_address"], callback_data=f"ordernew:{c.id}")]]))
        return
    await state.update_data(content_id=c.id)
    await state.set_state(OrderForm.name)
    await callback.message.answer(t["of_name"].format(title=html.escape(display_title(c, db_user.language))))


@router.callback_query(F.data.startswith("ordernew:"))
async def order_new_address(callback: CallbackQuery, session: AsyncSession, db_user: User, bot: Bot, seller: Seller,
                            state: FSMContext):
    t = T(db_user.language)
    c = await orderable(session, cb_id(callback.data), bot, seller, db_user)
    await callback.answer()
    if c is None:
        await callback.message.answer(t["order_unavailable"])
        return
    await state.clear()
    await state.update_data(content_id=c.id)
    await state.set_state(OrderForm.name)
    await callback.message.answer(t["of_name"].format(title=html.escape(display_title(c, db_user.language))))


@router.callback_query(F.data.startswith("ordersame:"))
async def order_same_address(callback: CallbackQuery, session: AsyncSession, db_user: User, bot: Bot, seller: Seller,
                             state: FSMContext):
    data = await state.get_data()
    await callback.answer()
    if data.get("content_id") != cb_id(callback.data) or not data.get("address"):
        await callback.message.answer(T(db_user.language)["order_unavailable"])
        return
    await finish_form(callback.message, session, db_user, bot, seller, state)


@router.message(StateFilter(*FORM_STATES), Command("cancel"))
async def form_cancel(message: Message, db_user: User, state: FSMContext):
    await state.clear()
    await message.answer(T(db_user.language)["of_cancelled"])


@router.message(StateFilter(OrderForm.name), F.text, ~F.text.startswith("/"))
async def form_name(message: Message, db_user: User, state: FSMContext):
    t = T(db_user.language)
    name = " ".join(message.text.split())
    if not NAME_MIN <= len(name) <= NAME_MAX:
        await message.answer(t["of_bad_name"])
        return
    await state.update_data(name=name)
    await state.set_state(OrderForm.phone)
    await message.answer(t["of_phone"])


@router.message(StateFilter(OrderForm.phone), F.text, ~F.text.startswith("/"))
async def form_phone(message: Message, db_user: User, state: FSMContext):
    t = T(db_user.language)
    phone = clean_phone(message.text)
    if phone is None:
        await message.answer(t["of_bad_phone"])
        return
    await state.update_data(phone=phone)
    await state.set_state(OrderForm.address)
    await message.answer(t["of_address"])


@router.message(StateFilter(OrderForm.address), F.text, ~F.text.startswith("/"))
async def form_address(message: Message, db_user: User, state: FSMContext):
    t = T(db_user.language)
    address = " ".join(message.text.split())
    if not ADDRESS_MIN <= len(address) <= ADDRESS_MAX:
        await message.answer(t["of_bad_address"])
        return
    await state.update_data(address=address)
    await state.set_state(OrderForm.postal)
    await message.answer(t["of_postal"], reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t["btn_no_postal"], callback_data="ordernopostal")]]))


@router.message(StateFilter(OrderForm.postal), F.text, ~F.text.startswith("/"))
async def form_postal(message: Message, session: AsyncSession, db_user: User, bot: Bot, seller: Seller,
                      state: FSMContext):
    postal = clean_postal(message.text)
    if postal is None:
        await message.answer(T(db_user.language)["of_bad_postal"])
        return
    await state.update_data(postal=postal)
    await finish_form(message, session, db_user, bot, seller, state)


@router.callback_query(StateFilter(OrderForm.postal), F.data == "ordernopostal")
async def form_no_postal(callback: CallbackQuery, session: AsyncSession, db_user: User, bot: Bot, seller: Seller,
                         state: FSMContext):
    await callback.answer()
    await state.update_data(postal=None)
    await finish_form(callback.message, session, db_user, bot, seller, state)


@router.message(StateFilter(OrderForm.name, OrderForm.phone, OrderForm.address, OrderForm.postal),
                ~F.text.startswith("/"))
async def form_not_text(message: Message, db_user: User):
    await message.answer(T(db_user.language)["of_text_only"])


async def finish_form(message: Message, session: AsyncSession, db_user: User, bot: Bot, seller: Seller,
                      state: FSMContext) -> None:
    """سفارش «در انتظار پرداخت» ساخته می‌شود و خلاصه + فاکتور (قیمت + هزینه‌ی ارسال) برای خریدار می‌رود."""
    t = T(db_user.language)
    data = await state.get_data()
    await state.clear()
    c = await orderable(session, data.get("content_id") or 0, bot, seller, db_user)
    if c is None or not data.get("name") or not data.get("phone") or not data.get("address"):
        await message.answer(t["order_unavailable"])
        return
    fee = seller.shipping_fee or 0
    order = Order(content_id=c.id, bot_id=bot.id, buyer_id=db_user.id, amount=c.price_stars + fee, shipping_fee=fee,
                  name=data["name"], phone=data["phone"], address=data["address"], postal_code=data.get("postal"))
    session.add(order)
    await session.commit()
    title = display_title(c, db_user.language)
    await bot.send_message(db_user.id, t["of_summary"].format(
        title=html.escape(title), price=c.price_stars, ship=toman(fee) if fee else t["ship_free_word"],
        total=order.amount, info=address_lines(data)))
    prices = [LabeledPrice(label=t["invoice_label"], amount=c.price_stars)]
    if fee:
        prices.append(LabeledPrice(label=t["ship_label"], amount=fee))
    await bot.send_invoice(chat_id=db_user.id, title=title[:32],
                           description=t["order_invoice_desc"].format(id=order.id, title=title)[:255],
                           payload=f"o:{order.id}", currency="XTR", prices=prices)


# ---------------- پرداخت ----------------
async def order_from_payload(session: AsyncSession, payload: str, bot_id: int) -> Order | None:
    if not payload.startswith("o:") or not is_id(payload[2:]):
        return None
    order = await session.get(Order, int(payload[2:]))
    return order if order is not None and order.bot_id == bot_id else None


async def check_order(session: AsyncSession, payload: str, bot: Bot, seller: Seller, user: User, amount: int) -> bool:
    """آخرین بررسی قبل از کم شدن پول: سفارش مال همین خریدار است، محصول هنوز هست و قیمت/هزینه‌ی ارسال عوض نشده."""
    order = await order_from_payload(session, payload, bot.id)
    if order is None or order.status != "pending" or order.buyer_id != user.id or order.amount != amount:
        return False
    c = await orderable(session, order.content_id, bot, seller, user)
    return c is not None and order_total(c, seller) == order.amount


async def order_paid(message: Message, session: AsyncSession, db_user: User, bot: Bot, seller: Seller) -> None:
    p = message.successful_payment
    t = T(db_user.language)
    order = await order_from_payload(session, p.invoice_payload, bot.id)
    if order is None:
        log.error("Payment for an unknown order payload %s", p.invoice_payload)
        return
    c = await session.get(Content, order.content_id)
    now = utcnow()
    purchase = Purchase(content_id=order.content_id, buyer_id=db_user.id, bot_id=bot.id, amount=p.total_amount,
                        charge_id=p.telegram_payment_charge_id, opened_at=now)   # opened_at: امتیاز و گزارش فعال
    session.add(purchase)
    await session.flush()
    order.status, order.paid_at, order.purchase_id, order.charge_id = "paid", now, purchase.id, p.telegram_payment_charge_id
    if c is not None and c.stock is not None:
        c.stock = max(0, c.stock - 1)
    await session.commit()   # قبل از هر پیامی ثبت شود
    title = html.escape(display_title(c, db_user.language)) if c else "?"
    await message.answer(t["order_confirmed"].format(id=order.id, title=title), reply_markup=InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=t["btn_report"], callback_data=f"report:{purchase.id}")]]))
    owner = await session.get(User, seller.owner_id)
    ot = T(owner.language if owner else "fa")
    info = address_lines({"name": order.name, "phone": order.phone, "address": order.address, "postal": order.postal_code})
    try:
        await bot.send_message(seller.owner_id, ot["order_new"].format(id=order.id, title=title, total=order.amount,
                                                                       info=info), reply_markup=ship_markup(order, ot))
        if c is not None and c.stock == 0:
            await bot.send_message(seller.owner_id, ot["stock_finished"].format(title=title), disable_notification=True)
    except Exception:
        pass  # فروشنده بازوی خودش را مسدود کرده؛ سفارش در /orders می‌ماند


# ---------------- ارسال و کد رهگیری ----------------
def ship_markup(order: Order, t: dict) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
        text=t["btn_ship"].format(id=order.id), callback_data=f"ship:{order.id}")]])


async def own_open_order(session: AsyncSession, order_id: int, bot: Bot, seller: Seller, user: User) -> Order | None:
    order = await session.get(Order, order_id) if order_id else None
    if order is None or order.bot_id != bot.id or seller.owner_id != user.id or order.status != "paid":
        return None
    return order


@router.callback_query(F.data.startswith("ship:"))
async def ship_start(callback: CallbackQuery, session: AsyncSession, db_user: User, bot: Bot, seller: Seller,
                     state: FSMContext):
    t = T(db_user.language)
    order = await own_open_order(session, cb_id(callback.data), bot, seller, db_user)
    await callback.answer()
    if order is None:
        return
    await state.set_state(ShipForm.tracking)
    await state.update_data(order_id=order.id)
    await callback.message.answer(t["ship_ask"].format(id=order.id), reply_markup=InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=t["btn_no_tracking"], callback_data=f"shipnow:{order.id}")]]))


@router.message(StateFilter(ShipForm.tracking), F.text, ~F.text.startswith("/"))
async def ship_tracking(message: Message, session: AsyncSession, db_user: User, bot: Bot, seller: Seller,
                        state: FSMContext):
    t = T(db_user.language)
    code = latin_digits(" ".join(message.text.split()))
    if not 4 <= len(code) <= TRACKING_MAX:
        await message.answer(t["bad_tracking"])
        return
    order = await own_open_order(session, (await state.get_data()).get("order_id") or 0, bot, seller, db_user)
    await state.clear()
    if order is not None:
        await mark_shipped(message, session, bot, order, code, t)


@router.callback_query(F.data.startswith("shipnow:"))
async def ship_without_tracking(callback: CallbackQuery, session: AsyncSession, db_user: User, bot: Bot, seller: Seller,
                                state: FSMContext):
    order = await own_open_order(session, cb_id(callback.data), bot, seller, db_user)
    await callback.answer()
    await state.clear()
    if order is not None:
        await mark_shipped(callback.message, session, bot, order, None, T(db_user.language))


async def mark_shipped(reply_to: Message, session: AsyncSession, bot: Bot, order: Order, tracking: str | None,
                       t: dict) -> None:
    from app.payments import rating_markup
    order.status, order.tracking, order.shipped_at = "shipped", tracking, utcnow()
    await session.commit()
    c = await session.get(Content, order.content_id)
    buyer = await session.get(User, order.buyer_id)
    bt = T(buyer.language if buyer else "fa")
    title = html.escape(display_title(c, "fa")) if c else "?"
    line = bt["tracking_line"].format(code=html.escape(tracking)) if tracking else bt["no_tracking_line"]
    try:   # خبر به خریدار + امتیاز به فروشنده
        await bot.send_message(order.buyer_id, bt["order_shipped"].format(id=order.id, title=title, tracking=line),
                               reply_markup=rating_markup(order.purchase_id, buyer.language if buyer else "fa")
                               if order.purchase_id else None)
    except Exception:
        pass  # خریدار بازو را مسدود کرده
    await reply_to.answer(t["ship_done_seller"].format(id=order.id))


@router.message(Command("orders"))
async def orders_cmd(message: Message, session: AsyncSession, db_user: User, bot: Bot, seller: Seller):
    """فروشنده: سفارش‌های منتظر ارسال. خریدار: سفارش‌های خودش در همین فروشگاه."""
    t = T(db_user.language)
    if seller.owner_id == db_user.id:
        rows = (await session.execute(select(Order, Content).join(Content, Content.id == Order.content_id).where(
            Order.bot_id == bot.id, Order.status == "paid").order_by(Order.id).limit(10))).all()
        waiting = await session.scalar(select(func.count(Order.id)).where(Order.bot_id == bot.id, Order.status == "paid"))
        if not rows:
            await message.answer(t["orders_seller_empty"])
            return
        lines = [t["orders_seller_head"].format(n=waiting)]
        for o, c in rows:
            lines.append(t["order_line_seller"].format(
                id=o.id, title=html.escape(display_title(c, db_user.language)), total=o.amount,
                info=address_lines({"name": o.name, "phone": o.phone, "address": o.address, "postal": o.postal_code})))
        await message.answer("\n\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t["btn_ship"].format(id=o.id), callback_data=f"ship:{o.id}")] for o, _ in rows]))
        return
    rows = (await session.execute(select(Order, Content).join(Content, Content.id == Order.content_id).where(
        Order.bot_id == bot.id, Order.buyer_id == db_user.id, Order.status != "pending")
        .order_by(Order.id.desc()).limit(10))).all()
    if not rows:
        await message.answer(t["orders_buyer_empty"])
        return
    lines = [t["orders_buyer_head"]]
    for o, c in rows:
        status = t["order_status_shipped"] if o.status == "shipped" else t["order_status_paid"]
        track = "\n   " + t["tracking_line"].format(code=html.escape(o.tracking)) if o.tracking else ""
        lines.append(t["order_line_buyer"].format(id=o.id, title=html.escape(display_title(c, db_user.language)),
                                                  status=status) + track)
    await message.answer("\n".join(lines))


# ---------------- موجودی ----------------
async def own_product(session: AsyncSession, content_id: int, bot: Bot, seller: Seller, user: User) -> Content | None:
    c = await session.get(Content, content_id) if content_id else None
    return c if c is not None and c.bot_id == bot.id and c.is_physical and seller.owner_id == user.id else None


@router.callback_query(F.data.startswith("stock:"))
async def stock_start(callback: CallbackQuery, session: AsyncSession, db_user: User, bot: Bot, seller: Seller,
                      state: FSMContext):
    t = T(db_user.language)
    c = await own_product(session, cb_id(callback.data), bot, seller, db_user)
    await callback.answer()
    if c is None:
        return
    await state.set_state(StockForm.amount)
    await state.update_data(content_id=c.id)
    await callback.message.answer(t["stock_ask"].format(title=html.escape(display_title(c, db_user.language))),
                                  reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
                                      text=t["btn_stock_inf"], callback_data=f"stockinf:{c.id}")]]))


@router.message(StateFilter(StockForm.amount), F.text, ~F.text.startswith("/"))
async def stock_typed(message: Message, session: AsyncSession, db_user: User, bot: Bot, seller: Seller,
                      state: FSMContext):
    t = T(db_user.language)
    text = latin_digits(message.text.strip())
    if not text.isdigit() or int(text) > STOCK_MAX:
        await message.answer(t["bad_stock"])
        return
    c = await own_product(session, (await state.get_data()).get("content_id") or 0, bot, seller, db_user)
    await state.clear()
    if c is None:
        return
    c.stock = int(text)
    await session.commit()
    await message.answer(t["stock_set"].format(stock=stock_label(c, t)))


@router.callback_query(F.data.startswith("stockinf:"))
async def stock_unlimited(callback: CallbackQuery, session: AsyncSession, db_user: User, bot: Bot, seller: Seller,
                          state: FSMContext):
    t = T(db_user.language)
    c = await own_product(session, cb_id(callback.data), bot, seller, db_user)
    await callback.answer()
    await state.clear()
    if c is None:
        return
    c.stock = None
    await session.commit()
    await callback.message.answer(t["stock_set"].format(stock=stock_label(c, t)))
