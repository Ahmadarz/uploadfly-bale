import asyncio
import logging

from aiogram import Dispatcher
from PIL import Image
from aiogram.exceptions import TelegramNetworkError
from aiogram.types import MenuButtonWebApp, WebAppInfo

from app import admin, connect, creator, handlers, payments, shop
from app.bots import BotManager, make_bot, setup_commands
from app.config import settings
from app.db import init_db
from app.middlewares import DbMiddleware
from app.tunnel import start_tunnel
from app.web import WEBAPP_DIR, start_web


def build_dispatcher() -> Dispatcher:
    """Dispatcher مشترک همه‌ی ربات‌ها؛ تست‌ها هم از همین استفاده می‌کنند."""
    dp = Dispatcher()
    dp.update.outer_middleware(DbMiddleware())
    # ترتیب مهم است: اول اتصال ربات و پرداخت، بعد هندلرهای عمومی (که هر پیامی را آپلود حساب می‌کنند)
    dp.include_routers(admin.router, connect.router, shop.router, payments.router, creator.router, handlers.router)
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
    await ensure_logo(bot)
    if url:
        try:
            await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(text="UploadFly", web_app=WebAppInfo(url=url)))
        except TelegramNetworkError:
            logging.warning("Could not set the Mini App menu button")
    return url


async def ensure_logo(bot) -> None:
    """لوگوی Mini App: اگر فایل لوگو نیست، عکس پروفایل خود ربات استفاده می‌شود."""
    logo = WEBAPP_DIR / "logo.jpg"
    if logo.exists():
        return
    try:
        photos = await bot.get_user_profile_photos(bot.id, limit=1)
        if photos.total_count:
            raw = await bot.download(photos.photos[0][-1].file_id)
            img = Image.open(raw).convert("RGB")
            img.thumbnail((256, 256))  # لوگوی کوچک: از تونل/اینترنت کند سریع می‌رسد
            img.save(logo, "JPEG", quality=85)
    except Exception:
        logging.warning("Could not fetch the bot's profile photo for the Mini App logo")


if __name__ == "__main__":
    asyncio.run(main())
