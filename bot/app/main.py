import asyncio
import logging

from aiogram import Dispatcher, F
from aiogram.exceptions import TelegramNetworkError
from aiogram.types import MenuButtonWebApp, WebAppInfo

from app import admin, connect, creator, handlers, orders, payments, shop
from app.bale import invoice_failed
from app.bots import BotManager, make_bot, setup_commands
from app.config import settings
from app.db import init_db
from app.middlewares import DbMiddleware
from app.tunnel import start_tunnel
from app.web import start_web


def build_dispatcher() -> Dispatcher:
    """Dispatcher مشترک همه‌ی ربات‌ها؛ تست‌ها هم از همین استفاده می‌کنند."""
    dp = Dispatcher()
    dp.update.outer_middleware(DbMiddleware())
    # ترتیب مهم است: اول اتصال ربات و پرداخت، بعد هندلرهای عمومی (که هر پیامی را آپلود حساب می‌کنند)
    # orders قبل از creator: متن‌های فرم سفارش (نام، نشانی...) نباید «پیام به فروشنده» حساب شوند
    dp.include_routers(admin.router, connect.router, shop.router, payments.router, orders.router, creator.router,
                       handlers.router)
    # فاکتوری که ساخته نشد (کیف پول ثبت نشده یا باطل): خریدار پیام می‌گیرد و صاحب فروشگاه خبردار می‌شود
    dp.errors.register(payments.pay_unavailable, F.exception.func(invoice_failed))
    return dp


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    await init_db()

    bot = make_bot(settings.bot_token)
    while True:  # قطعی کوتاه اینترنت هنگام شروع نباید برنامه را ببندد
        try:
            me = await bot.me()
            break
        except TelegramNetworkError:
            logging.warning("Telegram unreachable at startup, retrying in 5s")
            await asyncio.sleep(5)

    dp = build_dispatcher()

    manager = BotManager(dp, bot)
    dp["manager"] = manager
    dp["main_bot_id"] = bot.id
    dp["main_username"] = me.username

    # منوی دستورها به زبان کاربر (پیش‌فرض فارسی؛ زبان متفاوت → منوی شخصی در /start و /lang)
    try:
        await setup_commands(bot, seller=False)
    except TelegramNetworkError:
        logging.warning("Could not update the command menu; it will be retried on next start")

    dp["webapp_url"] = await start_mini_app(bot, manager, me.username)

    logging.info("UploadFly is running as @%s", me.username)
    await manager.run_forever()


async def start_mini_app(bot, manager: BotManager, username: str) -> str | None:
    """وب‌سرور Mini App + آدرس HTTPS (ثابت روی سرور، تونل موقت روی مک) + دکمه‌ی منوی تلگرام."""
    await start_web(manager, username, settings.webapp_port)
    url = settings.webapp_url
    if not url:
        tunnel = await start_tunnel(settings.webapp_port)
        url = tunnel[1] if tunnel else None
    if url:
        try:
            await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(text="UploadFly", web_app=WebAppInfo(url=url)))
        except TelegramNetworkError:
            logging.warning("Could not set the Mini App menu button")
    return url


if __name__ == "__main__":
    asyncio.run(main())
