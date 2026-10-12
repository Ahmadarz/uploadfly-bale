from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db import SessionLocal, Seller, User
from app.texts import detect_language


class DbMiddleware(BaseMiddleware):
    """برای هر آپدیت یک اتصال دیتابیس باز می‌کند، کاربر را ثبت/به‌روز می‌کند و کاربر مسدود را نادیده می‌گیرد.
    اگر آپدیت از ربات یک فروشنده آمده باشد، رکورد آن فروشنده را در data["seller"] می‌گذارد (برای ربات اصلی None)."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with SessionLocal() as session:
            tg_user = data.get("event_from_user")
            if tg_user is None:
                return None

            user = await session.get(User, tg_user.id)
            created = user is None
            if user is None:
                session.add(User(id=tg_user.id, username=tg_user.username,
                                 first_name=tg_user.first_name,
                                 language=detect_language(tg_user.language_code)))
                try:
                    await session.commit()
                except IntegrityError:
                    # دو پیام هم‌زمان از یک کاربر جدید: پیام دیگر زودتر او را ثبت کرده است
                    await session.rollback()
                user = await session.get(User, tg_user.id)
            else:
                user.username = tg_user.username
                user.first_name = tg_user.first_name
                await session.flush()

            if user.is_banned:
                await session.commit()
                return None

            seller = None
            if data["bot"].id != data["main_bot_id"]:
                seller = await session.scalar(select(Seller).where(Seller.bot_id == data["bot"].id))
                if seller is None or not seller.is_active:
                    return None

            if created and seller is not None and user.source is None:
                user.source = "shop"  # اولین آشنایی از ویترین/ربات یک فروشنده (حلقه‌ی رشد)
            if seller is not None and user.id != seller.owner_id:
                from app.creator import record_follower
                try:   # فالوور سازنده (برای پیام گروهی و آمار)
                    await record_follower(session, seller, user.id)
                    await session.commit()
                except IntegrityError:
                    await session.rollback()
                    user = await session.get(User, tg_user.id)
            data["session"] = session
            data["db_user"] = user
            data["seller"] = seller
            data["new_user"] = created
            result = await handler(event, data)
            await session.commit()
            return result


def main_bot(_: Any, seller: Seller | None = None) -> bool:
    """فیلتر: فقط در ربات اصلی UploadFly."""
    return seller is None


def seller_bot(_: Any, seller: Seller | None = None) -> bool:
    """فیلتر: فقط در ربات یک فروشنده."""
    return seller is not None
