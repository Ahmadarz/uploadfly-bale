"""اتصال ربات شخصی فروشنده به UploadFly (فقط در ربات اصلی)."""
import logging
import re

from aiogram import Bot, Dispatcher, F, Router
from aiogram.exceptions import TelegramUnauthorizedError
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ManagedBotUpdated, Message, WebAppInfo
from aiogram.utils.token import TokenValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots import BotManager, make_bot
from app.crypto import encrypt
from app.db import Seller, User
from app.middlewares import main_bot
from app.texts import LANGUAGES, T

log = logging.getLogger(__name__)

router = Router()
router.message.filter(F.chat.type == "private", main_bot)
router.managed_bot.filter(main_bot)


class Connect(StatesGroup):
    waiting_token = State()


def shop_button(t: dict) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t["btn_open_shop"],
                                                                       callback_data="shop:home")]])


def create_bot_link(main_username: str, user: User) -> str:
    """لینک «ساخت ربات» خود تلگرام (Managed Bots، Bot API 9.6): فروشنده فقط اسم می‌نویسد و Create می‌زند."""
    base = re.sub(r"[^A-Za-z0-9_]", "", user.username or "") or f"uf{user.id}"
    return f"https://t.me/newbot/{main_username}/{base[:22]}_shop_bot"


def create_shop_markup(t: dict, main_username: str, user: User) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
        text=t["btn_create_bot"], url=create_bot_link(main_username, user))]])


async def attach_bot(session: AsyncSession, manager: BotManager, user: User, token: str, bot_id: int,
                     username: str) -> str | None:
    """ربات را به‌عنوان فروشگاه کاربر وصل و روشن می‌کند. خروجی: کلید متن خطا، یا None اگر موفق بود."""
    existing = await session.scalar(select(Seller).where(Seller.bot_id == bot_id))
    if existing and existing.owner_id != user.id:
        return "bot_taken"
    current = await active_seller(session, user)
    if current and current.bot_id != bot_id:
        return "already_has_shop"  # هر کاربر یک فروشگاه
    if existing:
        existing.token_enc, existing.bot_username, existing.is_active = encrypt(token), username, True
    else:
        session.add(Seller(owner_id=user.id, bot_id=bot_id, bot_username=username, token_enc=encrypt(token)))
    await session.commit()
    await manager.stop(bot_id)
    await manager.start(make_bot(token))
    log.info("Seller bot @%s connected by user %s", username, user.id)
    return None


async def active_seller(session: AsyncSession, user: User) -> Seller | None:
    return await session.scalar(select(Seller).where(Seller.owner_id == user.id, Seller.is_active.is_(True)))


@router.message(Command("connect"))
async def connect_cmd(message: Message, session: AsyncSession, db_user: User, state: FSMContext,
                      main_username: str):
    t = T(db_user.language)
    seller = await active_seller(session, db_user)
    if seller:
        await message.answer(t["already_connected"].format(bot=seller.bot_username), reply_markup=shop_button(t))
        return
    await state.set_state(Connect.waiting_token)  # روش دستی (توکن) هم همچنان کار می‌کند
    await message.answer(t["connect_quick"], reply_markup=create_shop_markup(t, main_username, db_user))


@router.message(StateFilter(Connect.waiting_token), Command("cancel"))
async def connect_cancel(message: Message, db_user: User, state: FSMContext):
    await state.clear()
    await message.answer(T(db_user.language)["cancelled"])


@router.message(StateFilter(Connect.waiting_token), F.text)
async def connect_token(message: Message, session: AsyncSession, db_user: User, state: FSMContext,
                        bot: Bot, manager: BotManager):
    t = T(db_user.language)
    token = message.text.strip()
    try:
        await message.delete()  # توکن نباید در تاریخچه‌ی چت بماند
    except Exception:
        pass

    try:
        seller_bot = make_bot(token)
    except TokenValidationError:
        await message.answer(t["bad_token"])
        return
    try:
        if seller_bot.id == bot.id:
            await message.answer(t["bad_token"])
            return
        me = await seller_bot.get_me()
    except TelegramUnauthorizedError:
        await message.answer(t["bad_token"])
        return
    finally:
        await seller_bot.session.close()

    await state.clear()
    error = await attach_bot(session, manager, db_user, token, seller_bot.id, me.username)
    if error:
        await message.answer(t[error].format(bot=me.username))
        return
    await message.answer(t["connected"].format(bot=me.username), reply_markup=shop_button(t))


@router.message(StateFilter(Connect.waiting_token), ~F.managed_bot_created)
async def connect_not_text(message: Message, db_user: User):
    await message.answer(T(db_user.language)["connect_howto"])


# --- ساخت فروشگاه با یک ضربه (Managed Bots) ---
@router.message(F.managed_bot_created)
async def managed_bot_created_message(message: Message):
    """پیام سرویسی «ربات ساخته شد» در چت؛ کار اصلی در managed_bot_event انجام می‌شود."""


@router.managed_bot()
async def managed_bot_event(event: ManagedBotUpdated, session: AsyncSession, db_user: User, bot: Bot,
                            manager: BotManager, dispatcher: Dispatcher, main_username: str,
                            webapp_url: str | None = None):
    """تلگرام خبر می‌دهد کاربر رباتی ساخته (یا توکن/مالکش عوض شده). توکن را می‌گیریم و فروشگاه را وصل می‌کنیم."""
    t = T(db_user.language)
    new_bot = event.bot_user
    existing = await session.scalar(select(Seller).where(Seller.bot_id == new_bot.id))
    if existing and existing.owner_id != db_user.id:
        # مالکیت ربات به کس دیگری منتقل شده؛ فروشگاه قبلی قطع می‌شود تا محصولات کسی دست دیگری نیفتد
        existing.is_active = False
        await session.commit()
        await manager.stop(new_bot.id)
        log.warning("Managed bot %s changed owner; shop disconnected", new_bot.id)
        return
    token = await bot.get_managed_bot_token(user_id=new_bot.id)
    first_time = existing is None
    error = await attach_bot(session, manager, db_user, token, new_bot.id, new_bot.username)
    # این رویداد چت ندارد؛ حالت «منتظر توکن» را دستی پاک می‌کنیم
    await dispatcher.fsm.get_context(bot=bot, chat_id=db_user.id, user_id=db_user.id).clear()
    if error:
        await bot.send_message(db_user.id, t[error].format(bot=new_bot.username))
        return
    if first_time:
        try:  # توضیح ربات تازه برای رشد: هر خریدار می‌بیند فروشگاه با UploadFly ساخته شده
            seller_bot, main = manager.get(new_bot.id), main_username
            await seller_bot.set_my_short_description(t["shop_short_description"].format(main=main))
            await seller_bot.set_my_description(t["shop_description"].format(main=main))
            # خریدار قبل از /start توضیح را به زبان تلگرام خودش می‌بیند
            for code in LANGUAGES:
                await seller_bot.set_my_short_description(T(code)["shop_short_description"].format(main=main),
                                                          language_code=code)
                await seller_bot.set_my_description(T(code)["shop_description"].format(main=main), language_code=code)
        except Exception:
            log.warning("Could not set description of managed bot %s", new_bot.id)
    rows = [[InlineKeyboardButton(text=t["btn_upload_first"], url=f"https://t.me/{new_bot.username}?start=upload")]]
    if webapp_url:
        rows.append([InlineKeyboardButton(text=t["btn_open_dashboard"], web_app=WebAppInfo(url=webapp_url))])
    await bot.send_message(db_user.id, t["managed_connected"].format(bot=new_bot.username),
                           reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@router.message(Command("disconnect"))
async def disconnect_cmd(message: Message, session: AsyncSession, db_user: User, manager: BotManager):
    t = T(db_user.language)
    seller = await active_seller(session, db_user)
    if seller is None:
        await message.answer(t["not_connected"])
        return
    seller.is_active = False
    await session.commit()
    await manager.stop(seller.bot_id)
    await message.answer(t["disconnected"].format(bot=seller.bot_username))
