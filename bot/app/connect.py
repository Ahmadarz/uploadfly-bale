"""اتصال بازوی شخصی فروشنده به UploadFly (فقط در بازوی اصلی).

بله ساخت بازو از طریق برنامه ندارد؛ فروشنده خودش در @botfather بله بازو می‌سازد و دو چیز به ما می‌دهد:
۱) توکن بازو (تا بازو را برایش اجرا کنیم)  ۲) توکن کیف پول همان بازو (تا فاکتورها مستقیم به کیف پول خودش بروند).
بدون توکن کیف پول، فروشگاه فقط محتوای رایگان می‌پذیرد.
"""
import logging
import re

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice, Message
from aiogram.utils.token import TokenValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bale import NoWallet, bot_link, set_wallet
from app.bots import BotManager, make_bot
from app.crypto import decrypt, encrypt
from app.db import Seller, User
from app.middlewares import main_bot
from app.money import MIN_PRICE
from app.texts import T

log = logging.getLogger(__name__)

router = Router()
router.message.filter(F.chat.type == "private", main_bot)

BOTFATHER = "botfather"
WALLET_TOKEN = re.compile(r"[A-Za-z0-9_:\-]{8,128}")


class Connect(StatesGroup):
    waiting_token = State()
    waiting_wallet = State()


def shop_button(t: dict) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t["btn_open_shop"],
                                                                       callback_data="shop:home")]])


def create_bot_link(main_username: str, user: User) -> str:
    """لینک شروع ساخت فروشگاه (از Mini App): راهنمای قدم‌به‌قدم در چت بازوی اصلی."""
    return bot_link(main_username, "connect")


def botfather_markup(t: dict) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
        text=t["btn_create_bot"], url=bot_link(BOTFATHER))]])


def create_shop_markup(t: dict, main_username: str, user: User) -> InlineKeyboardMarkup:
    return botfather_markup(t)


def upload_button(t: dict, username: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
        text=t["btn_upload_first"], url=bot_link(username, "upload"))]])


async def attach_bot(session: AsyncSession, manager: BotManager, user: User, token: str, bot_id: int,
                     username: str) -> str | None:
    """بازو را به‌عنوان فروشگاه کاربر وصل و روشن می‌کند. خروجی: کلید متن خطا، یا None اگر موفق بود."""
    existing = await session.scalar(select(Seller).where(Seller.bot_id == bot_id))
    if existing and existing.owner_id != user.id:
        return "bot_taken"
    current = await active_seller(session, user)
    if current and current.bot_id != bot_id:
        return "already_has_shop"  # هر کاربر یک فروشگاه
    if existing:
        existing.token_enc, existing.bot_username, existing.is_active = encrypt(token), username, True
        set_wallet(bot_id, decrypt(existing.wallet_enc) if existing.wallet_enc else None)
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
    await state.set_state(Connect.waiting_token)
    await message.answer(t["connect_quick"], reply_markup=create_shop_markup(t, main_username, db_user))


@router.message(StateFilter(Connect.waiting_token, Connect.waiting_wallet), Command("cancel"))
async def connect_cancel(message: Message, db_user: User, state: FSMContext):
    await state.clear()
    await message.answer(T(db_user.language)["cancelled"])


@router.message(StateFilter(Connect.waiting_token), F.text, ~F.text.startswith("/"))
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
    except TelegramAPIError:  # بله برای توکن اشتباه «Token not found» می‌دهد
        await message.answer(t["bad_token"])
        return
    finally:
        await seller_bot.session.close()

    error = await attach_bot(session, manager, db_user, token, seller_bot.id, me.username)
    if error:
        await state.clear()
        await message.answer(t[error].format(bot=me.username))
        return
    await message.answer(t["connected"].format(bot=me.username))
    seller = await active_seller(session, db_user)
    if seller.wallet_enc:  # اتصال دوباره‌ی همان بازو: کیف پول قبلی سر جایش است
        await state.clear()
        await message.answer(t["wallet_saved"].format(bot=me.username), reply_markup=upload_button(t, me.username))
        return
    await state.set_state(Connect.waiting_wallet)
    await message.answer(t["wallet_ask"].format(bot=me.username), reply_markup=botfather_markup(t))


@router.message(StateFilter(Connect.waiting_token), ~F.text.startswith("/"))
async def connect_not_text(message: Message, db_user: User):
    await message.answer(T(db_user.language)["connect_howto"])


# --- کیف پول فروشگاه ---
@router.message(Command("wallet"))
async def wallet_cmd(message: Message, session: AsyncSession, db_user: User, state: FSMContext):
    t = T(db_user.language)
    seller = await active_seller(session, db_user)
    if seller is None:
        await message.answer(t["wallet_no_shop"])
        return
    await state.set_state(Connect.waiting_wallet)
    await message.answer(t["wallet_ask"].format(bot=seller.bot_username), reply_markup=botfather_markup(t))


@router.message(StateFilter(Connect.waiting_wallet), Command("skip"))
async def wallet_skip(message: Message, session: AsyncSession, db_user: User, state: FSMContext):
    await state.clear()
    seller = await active_seller(session, db_user)
    await message.answer(T(db_user.language)["wallet_skipped"].format(bot=seller.bot_username if seller else "?"))


async def wallet_works(seller_bot: Bot, bot_id: int, token: str, old: str | None) -> bool:
    """توکن کیف پول را با ساختن یک فاکتور آزمایشی (که به کسی نشان داده نمی‌شود) می‌سنجد."""
    set_wallet(bot_id, token)
    try:
        await seller_bot.create_invoice_link(title="UploadFly", description="wallet check", payload="check",
                                             currency="XTR", prices=[LabeledPrice(label="check", amount=MIN_PRICE)])
        return True
    except (TelegramAPIError, NoWallet):
        set_wallet(bot_id, old)
        return False


@router.message(StateFilter(Connect.waiting_wallet), F.text, ~F.text.startswith("/"))
async def wallet_token(message: Message, session: AsyncSession, db_user: User, state: FSMContext,
                       manager: BotManager):
    t = T(db_user.language)
    token = message.text.strip()
    try:
        await message.delete()  # توکن کیف پول هم نباید در چت بماند
    except Exception:
        pass
    seller = await active_seller(session, db_user)
    if seller is None:
        await state.clear()
        await message.answer(t["wallet_no_shop"])
        return
    seller_bot = manager.get(seller.bot_id)
    old = decrypt(seller.wallet_enc) if seller.wallet_enc else None
    if not WALLET_TOKEN.fullmatch(token) or seller_bot is None \
            or not await wallet_works(seller_bot, seller.bot_id, token, old):
        await message.answer(t["wallet_bad"].format(bot=seller.bot_username))
        return
    seller.wallet_enc = encrypt(token)
    await session.commit()
    await state.clear()
    log.info("Wallet token set for seller bot %s", seller.bot_id)
    await message.answer(t["wallet_saved"].format(bot=seller.bot_username),
                         reply_markup=upload_button(t, seller.bot_username))


@router.message(StateFilter(Connect.waiting_wallet), ~F.text.startswith("/"))
async def wallet_not_text(message: Message, session: AsyncSession, db_user: User):
    seller = await active_seller(session, db_user)
    await message.answer(T(db_user.language)["wallet_bad"].format(bot=seller.bot_username if seller else "?"))


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
