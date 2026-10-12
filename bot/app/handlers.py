import html
import re
import secrets
from urllib.parse import quote

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import creator, preview, showcases
from app.bots import set_user_menu
from app.connect import Connect, active_seller, create_shop_markup
from app.content import deliver, extract_content
from app.trust import is_blacklisted, price_cap
from app.products import MAX_PRICE, PRICE_PRESETS, build_link, link_keyboard, publish
from app.config import settings
from app.db import Content, Seller, User, cb_id, is_id
from app.payments import get_purchase, open_purchase, send_offer, send_pending
from app.texts import LANGUAGES, T, format_specs

router = Router()
router.message.filter(F.chat.type == "private")



# لینک یک ربات: t.me/Bot ، t.me/Bot?start= ، t.me/Bot?start=CODE (کد اختیاری)
OWN_LINK = re.compile(r"(?:https?://)?(?:t\.me|telegram\.me)/(\w+)/?(?:\?start=([\w-]*))?", re.IGNORECASE)


class Pricing(StatesGroup):
    waiting_price = State()


async def new_code(session: AsyncSession) -> str:
    while True:
        code = secrets.token_urlsafe(6)  # حدود ۸ کاراکتر، قابل حدس نیست
        exists = await session.scalar(select(Content.id).where(Content.code == code))
        if not exists:
            return code


def price_keyboard(content: Content, lang: str, cap: int) -> InlineKeyboardMarkup:
    t = T(lang)
    content_id = content.id
    # فقط قیمت‌های زیر سقف اعتماد فعلی فروشنده
    presets = [InlineKeyboardButton(text=f"{p} ⭐", callback_data=f"price:{content_id}:{p}")
               for p in PRICE_PRESETS if p <= cap]
    sensitive = t["btn_sensitive_on"] if content.is_sensitive else t["btn_sensitive_off"]
    save = t["btn_save_on"] if content.allow_save else t["btn_save_off"]
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=sensitive, callback_data=f"sens:{content_id}")],
        [InlineKeyboardButton(text=save, callback_data=f"save:{content_id}")],
        [InlineKeyboardButton(text=t["btn_free"], callback_data=f"price:{content_id}:0")],
        presets[:3], presets[3:],
        [InlineKeyboardButton(text=t["btn_custom_price"], callback_data=f"price:{content_id}:custom")],
    ])


# --- باز کردن لینک: /start <code> ---
def clean_source(tag: str) -> str:
    """برچسب منبع: فقط حروف کوچک انگلیسی، عدد و _ (حداکثر ۲۸)؛ بقیه = other."""
    tag = tag.lower()[:28]
    return f"src_{tag}" if re.fullmatch(r"[a-z0-9_]+", tag) else "src_other"


@router.message(CommandStart(deep_link=True))
async def open_link(message: Message, command: CommandObject, session: AsyncSession, db_user: User, bot: Bot,
                    seller: Seller | None, state: FSMContext, main_username: str, webapp_url: str | None = None,
                    new_user: bool = False):
    code = (command.args or "").strip()
    if code == "support":  # از سایت یا ربات فروشگاه: پشتیبانی
        await support_cmd(message, db_user, main_username, seller, webapp_url)
        return
    if seller is None and code.startswith("ref_"):  # دعوت سازنده توسط سازنده: t.me/Uploadfly_Bot?start=ref_<id>
        ref = code[4:]
        if new_user and db_user.source is None:
            db_user.source = "ref"
            if is_id(ref, big=True) and int(ref) != db_user.id and await session.get(User, int(ref)):
                db_user.referrer_id = int(ref)
        await start(message, db_user, bot, seller, main_username, webapp_url)
        return
    if code == "broadcast" and seller is not None:  # از دکمه‌ی «پیام گروهی» در Mini App
        await creator.broadcast_menu(message, session, db_user, bot, seller)
        return
    if code in ("donate", "tip") and seller is not None:  # دکمه‌ی دونیت
        await creator.tip_cmd(message, db_user, seller)
        return
    if seller is None and code.startswith("src_"):  # لینک تبلیغ: t.me/Uploadfly_Bot?start=src_<کانال>
        if new_user and db_user.source is None:
            db_user.source = clean_source(code[4:])
        await start(message, db_user, bot, seller, main_username, webapp_url)
        return
    if seller is None and new_user and db_user.source is None:
        db_user.source = "link"  # با لینک رایگان کسی آمده (حلقه‌ی رشد لینک‌ها)
    if code == "store" and seller is not None:  # لینک اشتراکی ویترین: t.me/<shop_bot>?start=store
        await send_store_button(message, db_user, seller, bot, webapp_url, main_username)
        return
    if code.startswith("sc_") and seller is not None:  # لینک یک ویترین (مثلاً در بایوی اینستاگرام)
        await send_showcase_button(message, session, db_user, bot, code[3:], webapp_url)
        return
    if code == "upload" and seller is not None:  # از دکمه‌ی «آپلود محصول» در Mini App یا ربات اصلی
        t = T(db_user.language)
        await message.answer(t["upload_prompt"] if seller.owner_id == db_user.id else t["seller_only_owner"])
        return
    if code == "connect" and seller is None:  # از دکمه‌ی «ساخت فروشگاه» در Mini App
        t = T(db_user.language)
        await state.set_state(Connect.waiting_token)
        await message.answer(t["connect_quick"], reply_markup=create_shop_markup(t, main_username, db_user))
        return
    content = await session.scalar(select(Content).where(Content.code == code, Content.bot_id == bot.id))
    if content is not None and not content.is_active:
        # آرشیوشده: فقط کسی که قبلاً خریده هنوز دسترسی دارد؛ محتوای حذف‌شده به‌خاطر تخلف هرگز
        allowed = content.owner_id == db_user.id or await get_purchase(session, db_user, content)
        if not allowed or content.is_draft or await is_blacklisted(session, content.file_unique_id):
            content = None
    if content is None:
        await message.answer(T(db_user.language)["not_found"])
        return

    if content.is_sensitive and content.owner_id != db_user.id and not db_user.adult_ok:
        t = T(db_user.language)   # محتوای حساس: یک بار تأیید ۱۸+
        await message.answer(t["adult_confirm"], reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=t["btn_adult_yes"], callback_data=f"adult:{content.code}")]]))
        return
    content.views += 1
    purchase = None
    if content.price_stars > 0 and content.owner_id != db_user.id:
        purchase = await get_purchase(session, db_user, content)
        if purchase is None:
            if seller is not None and seller.is_suspended:
                await message.answer(T(db_user.language)["shop_suspended_buyer"])
            else:
                await send_offer(bot, message.chat.id, content, db_user.language, store_url(webapp_url, bot.id))
            return
    if purchase is None:
        await deliver(bot, message.chat.id, content, session, db_user.language)
    elif purchase.opened_at is None:
        await send_pending(bot, message.chat.id, purchase, db_user.language)  # هنوز بین نمایش و بازپرداخت انتخاب نکرده
    else:
        await open_purchase(bot, message.chat.id, purchase, content, session, db_user.language)


async def send_showcase_button(message: Message, session: AsyncSession, db_user: User, bot: Bot, code: str,
                               webapp_url: str | None) -> None:
    t = T(db_user.language)
    sc = await showcases.by_code(session, code)
    if sc is None or sc.bot_id != bot.id:
        await message.answer(t["not_found"])
        return
    badge = {"free": t["sc_free"], "once": t["sc_once"].format(price=sc.price),
             "monthly": t["sc_monthly"].format(price=sc.price)}[sc.access]
    text = f"<b>{html.escape(sc.title)}</b>\n{badge}"
    if sc.description:
        text += f"\n\n{html.escape(sc.description)}"
    url = f"{store_url(webapp_url, bot.id)}&sc={sc.code}" if webapp_url else None
    markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
        text=t["btn_open_showcase"], web_app=WebAppInfo(url=url))]]) if url else None
    await message.answer(text, reply_markup=markup)


def store_url(webapp_url: str | None, bot_id: int) -> str | None:
    """ویترین در Mini App؛ از ربات فروشنده باز می‌شود تا خرید و تحویل در همان ربات باشد."""
    return f"{webapp_url}/?store={bot_id}&bot={bot_id}" if webapp_url else None


async def send_store_button(message: Message, db_user: User, seller: Seller, bot: Bot, webapp_url: str | None,
                            main_username: str) -> None:
    t = T(db_user.language)
    name = html.escape(message.from_user.first_name or "")
    url = store_url(webapp_url, bot.id)
    markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
        text=t["btn_open_store"], web_app=WebAppInfo(url=url))]]) if url else None
    if seller.owner_id == db_user.id:
        await message.answer(t["seller_welcome_owner"].format(name=name), reply_markup=markup)
    else:
        await message.answer(t["seller_welcome_buyer"].format(name=name, main=main_username), reply_markup=markup)


@router.message(CommandStart())
async def start(message: Message, db_user: User, bot: Bot, seller: Seller | None, main_username: str,
                webapp_url: str | None = None, new_user: bool = False):
    if new_user and db_user.source is None:
        db_user.source = "direct"
    t = T(db_user.language)
    name = html.escape(message.from_user.first_name or "")
    await set_user_menu(bot, db_user.id, db_user.language, message.from_user.language_code, seller is not None)
    if seller is None:
        await message.answer(t["welcome"].format(name=name), reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=t["btn_open_shop"], callback_data="shop:home")]]))
    else:
        await send_store_button(message, db_user, seller, bot, webapp_url, main_username)


@router.message(Command("help"))
async def help_cmd(message: Message, db_user: User, seller: Seller | None):
    t = T(db_user.language)
    await message.answer(t["help"] if seller is None else t["seller_help"])


@router.message(Command("paysupport"))
async def paysupport_cmd(message: Message, session: AsyncSession, db_user: User, seller: Seller | None,
                         main_username: str):
    """پشتیبانی پرداخت (تلگرام برای ربات‌هایی که با Stars می‌فروشند لازم می‌داند)."""
    t = T(db_user.language)
    if seller is None:
        await message.answer(t["paysupport_main"])
        return
    owner = await session.get(User, seller.owner_id)
    contact = t["paysupport_contact"].format(user=owner.username) if owner and owner.username else ""
    await message.answer(t["paysupport"].format(shop=f"@{seller.bot_username}", contact=contact)
                         + t["paysupport_escalate"].format(main=main_username))


@router.message(Command("stars"))
async def stars_cmd(message: Message, db_user: User):
    """راهنمای خرید استارز (لینکش زیر هر پیشنهاد خرید هست)."""
    t = T(db_user.language)
    user = f"@{message.from_user.username}" if message.from_user.username else t["stars_no_user"]
    await message.answer(t["stars_guide"].format(user=html.escape(user)))


@router.message(Command("support"))
async def support_cmd(message: Message, db_user: User, main_username: str, seller: Seller | None,
                      webapp_url: str | None = None):
    """سؤالات متداول + چت مستقیم با حساب پشتیبانی + ایمیل (حساب و ایمیل از .env)."""
    t = T(db_user.language)
    email = t["support_email_line"].format(email=html.escape(settings.support_email)) if settings.support_email else ""
    rows = []
    if webapp_url and seller is None:  # Mini App از ربات اصلی باز می‌شود
        rows.append([InlineKeyboardButton(text=t["btn_support_faq"], web_app=WebAppInfo(url=f"{webapp_url}/?page=support"))])
    elif seller is not None:
        rows.append([InlineKeyboardButton(text=t["btn_support_faq"], url=f"https://t.me/{main_username}?start=support")])
    if settings.support_username:
        rows.append([InlineKeyboardButton(text=t["btn_support_chat"], url=f"https://t.me/{settings.support_username}")])
    await message.answer(t["support_text"].format(email=email, id=db_user.id),
                         reply_markup=InlineKeyboardMarkup(inline_keyboard=rows) if rows else None)


@router.message(Command("terms"))
async def terms_cmd(message: Message, db_user: User):
    await message.answer(T(db_user.language)["terms"], disable_web_page_preview=True)


@router.message(Command("lang"))
async def lang_cmd(message: Message, db_user: User):
    names = {"fa": "فارسی", "en": "English", "ru": "Русский", "ar": "العربية", "zh": "中文"}
    buttons = [InlineKeyboardButton(text=("✅ " if code == db_user.language else "") + names[code],
                                    callback_data=f"lang:{code}") for code in LANGUAGES]
    await message.answer(T(db_user.language)["lang_choose"], reply_markup=InlineKeyboardMarkup(
        inline_keyboard=[buttons[i:i + 2] for i in range(0, len(buttons), 2)]))


@router.callback_query(F.data.in_({f"lang:{code}" for code in LANGUAGES}))
async def lang_set(callback: CallbackQuery, db_user: User, bot: Bot, seller: Seller | None):
    db_user.language = callback.data.split(":")[1]
    await set_user_menu(bot, db_user.id, db_user.language, callback.from_user.language_code, seller is not None,
                        force=True)
    await callback.message.edit_text(T(db_user.language)["lang_set"])
    await callback.answer()


@router.message(Command("mylinks"))
async def my_links(message: Message, session: AsyncSession, db_user: User, bot: Bot):
    t = T(db_user.language)
    rows = (await session.scalars(
        select(Content)
        .where(Content.owner_id == db_user.id, Content.bot_id == bot.id, Content.is_active.is_(True))
        .order_by(Content.id.desc())
        .limit(10)
    )).all()
    if not rows:
        await message.answer(t["mylinks_empty"])
        return

    lines = [t["mylinks_header"]]
    for c in rows:
        link = await build_link(bot, c.code)
        label = t["kinds"].get(c.kind, c.kind)
        if c.file_name:
            label += f" · {html.escape(c.file_name[:30])}"
        if c.price_stars:
            label += f" · {c.price_stars} ⭐"
        lines.append(f"• {label}\n   <code>{link}</code>  ({c.views} {t['views']})")
    await message.answer("\n".join(lines), disable_web_page_preview=True)


# --- قیمت‌گذاری در ربات فروشنده ---
@router.callback_query(F.data.startswith("sens:"))
async def sensitive_toggle(callback: CallbackQuery, session: AsyncSession, db_user: User, bot: Bot,
                           seller: Seller | None):
    content = await session.get(Content, cb_id(callback.data))
    if seller is None or content is None or content.owner_id != db_user.id or content.bot_id != bot.id \
            or not content.is_draft:
        await callback.answer()
        return
    content.is_sensitive = not content.is_sensitive
    if content.is_sensitive:
        content.allow_save = False  # محتوای حساس همیشه محافظت‌شده است
    await callback.message.edit_reply_markup(reply_markup=price_keyboard(content, db_user.language, await price_cap(session, bot.id)))
    await callback.answer()


@router.callback_query(F.data.startswith("save:"))
async def save_toggle(callback: CallbackQuery, session: AsyncSession, db_user: User, bot: Bot,
                      seller: Seller | None):
    content = await session.get(Content, cb_id(callback.data))
    if seller is None or content is None or content.owner_id != db_user.id or content.bot_id != bot.id \
            or not content.is_draft:
        await callback.answer()
        return
    if content.is_sensitive:
        await callback.answer(T(db_user.language)["save_not_sensitive"], show_alert=True)
        return
    content.allow_save = not content.allow_save
    await callback.message.edit_reply_markup(reply_markup=price_keyboard(content, db_user.language, await price_cap(session, bot.id)))
    await callback.answer()


@router.callback_query(F.data.startswith("price:"))
async def price_chosen(callback: CallbackQuery, session: AsyncSession, db_user: User, bot: Bot,
                       state: FSMContext, seller: Seller | None):
    t = T(db_user.language)
    _, content_id, value = (callback.data.split(":") + ["", ""])[:3]
    content = await session.get(Content, int(content_id)) if is_id(content_id) else None
    if seller is None or content is None or content.owner_id != db_user.id or content.bot_id != bot.id \
            or not content.is_draft:
        await callback.answer()
        return
    await callback.answer()  # زود جواب بده؛ ساخت پیش‌نمایش ممکن است چند ثانیه طول بکشد
    await callback.message.edit_reply_markup(reply_markup=None)
    if value == "custom":
        await state.set_state(Pricing.waiting_price)
        await state.update_data(content_id=content.id)
        await callback.message.answer(t["ask_price"].format(max=await price_cap(session, bot.id)))
    else:
        if int(value) > await price_cap(session, bot.id):  # دکمه‌ی قدیمی با قیمت بالاتر از سقف
            return
        await publish(bot, callback.message.chat.id, content, int(value), db_user.language)


@router.message(StateFilter(Pricing.waiting_price), F.text)
async def price_typed(message: Message, session: AsyncSession, db_user: User, bot: Bot, state: FSMContext):
    t = T(db_user.language)
    text = message.text.strip().translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))
    cap = await price_cap(session, bot.id)
    if not text.isdigit() or not 1 <= int(text) <= cap:
        await message.answer(t["ask_price"].format(max=cap) + "\n" + t["price_cap_hint"].format(cap=cap))
        return
    content = await session.get(Content, (await state.get_data())["content_id"])
    await state.clear()
    if content is None or not content.is_draft:  # در این فاصله از Mini App منتشر شده
        return
    await publish(bot, message.chat.id, content, int(text), db_user.language)


@router.callback_query(F.data.startswith("adult:"))
async def adult_ok(callback: CallbackQuery, session: AsyncSession, db_user: User, bot: Bot, seller: Seller | None,
                   state: FSMContext, main_username: str, webapp_url: str | None = None):
    db_user.adult_ok = True
    await session.commit()
    await callback.answer()
    try:
        await callback.message.delete()
    except Exception:
        pass
    code = callback.data[6:]
    fake = callback.message.model_copy(update={"from_user": callback.from_user}).as_(bot)
    await open_link(fake, CommandObject(prefix="/", command="start", args=code), session, db_user, bot, seller,
                    state, main_username, webapp_url)


@router.message(F.text.startswith("/"))
async def unknown_command(message: Message, db_user: User):
    await message.answer(T(db_user.language)["unknown_command"])


# --- هر پیام دیگری = آپلود محتوای جدید ---
@router.message()
async def save_content(message: Message, session: AsyncSession, db_user: User, bot: Bot, seller: Seller | None,
                       state: FSMContext, main_username: str, webapp_url: str | None = None):
    t = T(db_user.language)
    # کاربر لینک خود همین ربات را فرستاده (مثلاً کپی‌شده)؛ بازش کن، لینکِ لینک نساز
    if message.text and (m := OWN_LINK.fullmatch(message.text.strip())):
        target, code = m.group(1).lower(), m.group(2) or ""
        if target == (await bot.me()).username.lower():
            if code:
                await open_link(message, CommandObject(prefix="/", command="start", args=code), session, db_user,
                                bot, seller, state, main_username, webapp_url)
            else:  # لینک خالیِ همین ربات: مثل /start
                await start(message, db_user, bot, seller, main_username, webapp_url)
            return
        # لینک یکی دیگر از ربات‌های UploadFly (فروشگاه یا ربات اصلی): دکمه‌ی باز کردن همان‌جا
        is_ours = target == main_username.lower() or await session.scalar(select(Seller.id).where(
            func.lower(Seller.bot_username) == target, Seller.is_active.is_(True)))
        if is_ours:
            url = f"https://t.me/{m.group(1)}" + (f"?start={code}" if code else "")
            await message.reply(t["link_elsewhere"].format(bot=m.group(1)), reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text=t["btn_open_link"], url=url)]]))
            return
    if seller is not None and seller.owner_id != db_user.id:   # فن به سازنده پیام می‌دهد
        await creator.fan_message(message, session, db_user, bot, seller, webapp_url)
        return

    data = extract_content(message)
    if data is None:
        await message.reply(t["unsupported"])
        return
    if await is_blacklisted(session, data.get("file_unique_id")):
        await message.reply(t["file_blacklisted"])
        return

    # در ربات فروشنده محتوا تا انتخاب قیمت غیرفعال می‌ماند
    content = Content(code=await new_code(session), bot_id=bot.id, owner_id=db_user.id,
                      is_active=seller is None, is_draft=seller is not None, **data)
    session.add(content)
    await session.commit()  # قبل از دادن لینک حتماً ذخیره شود

    if seller is None:
        link = await build_link(bot, content.code)
        markup = link_keyboard(link, db_user.language)
        text = t["link_created"].format(specs=format_specs(content, db_user.language), link=link)
        own_shop = await active_seller(session, db_user)
        if own_shop:  # فروشنده اشتباهی در ربات اصلی آپلود کرده؛ راه فروش را نشانش بده
            text += "\n\n" + t["sell_hint"].format(bot=own_shop.bot_username)
            markup.inline_keyboard.append([InlineKeyboardButton(
                text=t["btn_sell_in_shop"], url=f"https://t.me/{own_shop.bot_username}?start=upload")])
        await message.reply(text, reply_markup=markup)
    else:
        await state.clear()
        if webapp_url:  # تنظیم محصول در Mini App؛ قیمت‌گذاری در چت فقط به‌عنوان راه دوم
            await message.reply(t["received"].format(specs=format_specs(content, db_user.language)),
                                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                    [InlineKeyboardButton(text=t["btn_setup_product"], web_app=WebAppInfo(
                                        url=f"{webapp_url}/?p={content.id}&bot={bot.id}"))],
                                    [InlineKeyboardButton(text=t["btn_price_in_chat"],
                                                          callback_data=f"chatprice:{content.id}")]]))
        else:
            await message.reply(t["choose_price"].format(specs=format_specs(content, db_user.language)),
                                reply_markup=price_keyboard(content, db_user.language, await price_cap(session, bot.id)))


@router.callback_query(F.data.startswith("chatprice:"))
async def price_in_chat(callback: CallbackQuery, session: AsyncSession, db_user: User, bot: Bot,
                        seller: Seller | None):
    content = await session.get(Content, cb_id(callback.data))
    if seller is None or content is None or content.owner_id != db_user.id or content.bot_id != bot.id \
            or not content.is_draft:
        await callback.answer()
        return
    await callback.message.edit_text(T(db_user.language)["choose_price"].format(
        specs=format_specs(content, db_user.language)), reply_markup=price_keyboard(content, db_user.language, await price_cap(session, bot.id)))
    await callback.answer()
