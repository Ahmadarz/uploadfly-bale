"""اجرای هم‌زمان ربات اصلی و ربات‌های فروشنده‌ها در یک برنامه.

هر ربات حلقه‌ی دریافت پیام (polling) خودش را دارد و همه‌ی پیام‌ها به یک Dispatcher مشترک می‌روند.
ربات فروشنده‌ی جدید بدون ری‌استارت برنامه اضافه یا حذف می‌شود.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramNetworkError, TelegramUnauthorizedError
from aiogram.types import BotCommand, BotCommandScopeChat
from sqlalchemy import delete, select

from app.bale import make_bale_bot
from app.crypto import decrypt
from app.db import DeleteJob, SessionLocal, Seller, User
from app.texts import COMMANDS, MAIN_COMMANDS, MENU_LANG_CODES, SELLER_COMMANDS, T

log = logging.getLogger(__name__)


def retry_delay(failures: int) -> float:
    """ثانیه‌های صبر بعد از n تلاش ناموفق پشت سر هم: ۲، ۴، ۸، ۱۶، ۳۲، ۶۰، ۶۰ ..."""
    return min(2 ** failures, 60)


RESET_AFTER = 3  # بعد از چند تلاش ناموفق پشت سر هم، اتصال از نو ساخته شود


async def reset_session(bot: Bot) -> None:
    try:
        await bot.session.close()
    except Exception:  # noqa: BLE001  بستن اتصال خراب نباید حلقه را بشکند
        log.debug("Closing a broken session failed", exc_info=True)


def make_bot(token: str) -> Bot:
    return make_bale_bot(token)  # سرور بله + تبدیل متن HTML به Markdown بله (app/bale.py)


class BotManager:
    def __init__(self, dp: Dispatcher, main_bot: Bot):
        self.dp = dp
        self.main_bot = main_bot
        self._polls: dict[int, tuple[Bot, asyncio.Task]] = {}
        self._handling: set[asyncio.Task] = set()

    def is_running(self, bot_id: int) -> bool:
        return bot_id in self._polls

    def get(self, bot_id: int) -> Bot | None:
        item = self._polls.get(bot_id)
        return item[0] if item else None

    async def start(self, bot: Bot) -> None:
        if self.is_running(bot.id):
            return
        if bot.id != self.main_bot.id:
            try:
                await setup_seller_bot(bot)
            except TelegramNetworkError:
                log.warning("Could not set up seller bot %s menu; polling anyway", bot.id)
        self._polls[bot.id] = (bot, asyncio.create_task(self._poll(bot)))

    async def stop(self, bot_id: int) -> None:
        item = self._polls.pop(bot_id, None)
        if item is None:
            return
        bot, task = item
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        if bot is not self.main_bot:
            await bot.session.close()

    async def start_sellers(self) -> None:
        async with SessionLocal() as session:
            sellers = (await session.scalars(select(Seller).where(Seller.is_active.is_(True)))).all()
        for s in sellers:
            try:
                await self.start(make_bot(decrypt(s.token_enc)))
            except Exception:
                log.exception("Could not start seller bot @%s", s.bot_username)

    async def run_forever(self) -> None:
        await self.start(self.main_bot)
        await self.start_sellers()
        deleter = asyncio.create_task(self._delete_loop())
        subscriptions = asyncio.create_task(self._subscription_loop())
        scheduled = asyncio.create_task(self._scheduled_loop())
        try:
            await asyncio.Event().wait()
        finally:
            deleter.cancel()
            subscriptions.cancel()
            scheduled.cancel()
            for bot_id in list(self._polls):
                await self.stop(bot_id)
            await self.main_bot.session.close()

    async def _subscription_loop(self) -> None:
        """هر ۳۰ دقیقه: یادآوری تمدید و پیام پایان اشتراک‌های ماهانه‌ی ویترین‌ها."""
        from app import showcases
        while True:
            try:
                await showcases.subscription_tick(self, self.dp.workflow_data.get("webapp_url"))
                await showcases.expire_tick(self)
                from app import looks
                async with SessionLocal() as session:
                    await looks.cleanup_orphans(session)  # عکس‌های آپلودشده‌ای که هیچ‌جا استفاده نشدند
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("Subscription loop failed")
            await asyncio.sleep(1800)

    async def _scheduled_loop(self) -> None:
        """هر دقیقه: پست‌های زمان‌بندی‌شده‌ای که وقتشان رسیده منتشر می‌شوند."""
        from app import creator
        while True:
            try:
                await creator.publish_due(self)
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("Scheduled posts loop failed")
            await asyncio.sleep(60)

    async def _delete_loop(self) -> None:
        """هر ۱۰ ثانیه پیام‌های حساسی که زمان نمایششان تمام شده را پاک می‌کند."""
        while True:
            try:
                await self._delete_due()
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("Delete loop failed")
            await asyncio.sleep(10)

    async def _delete_due(self) -> None:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        async with SessionLocal() as session:
            jobs = (await session.scalars(
                select(DeleteJob).where(DeleteJob.delete_at <= now).order_by(DeleteJob.delete_at).limit(100)
            )).all()
            done = []
            for job in jobs:
                item = self._polls.get(job.bot_id)
                if item is None:
                    # ربات فروشنده فعلاً وصل نیست؛ تلگرام فقط تا ۴۸ ساعت اجازه‌ی حذف می‌دهد
                    if now - job.delete_at > timedelta(hours=47):
                        done.append(job.id)
                    continue
                try:
                    await item[0].delete_message(job.chat_id, job.message_id)
                except (TelegramBadRequest, TelegramForbiddenError):
                    pass  # قبلاً پاک شده یا کاربر ربات را بلاک کرده
                except TelegramNetworkError:
                    continue  # دفعه‌ی بعد دوباره تلاش می‌شود
                done.append(job.id)
            if done:
                await session.execute(delete(DeleteJob).where(DeleteJob.id.in_(done)))
                await session.commit()

    async def _poll(self, bot: Bot) -> None:
        offset, failures = None, 0
        allowed = self.dp.resolve_used_update_types()
        while True:
            try:
                updates = await bot.get_updates(offset=offset, timeout=30, allowed_updates=allowed)
            except TelegramUnauthorizedError:
                # فروشنده توکن را در BotFather عوض یا ربات را حذف کرده
                await self._on_revoked(bot)
                return
            except asyncio.CancelledError:
                raise
            except Exception as e:
                # قطعی اینترنت: یک بار گزارش، بعد صبر فزاینده (۲، ۴، ۸ ... تا ۶۰ ثانیه) به‌جای تلاش هر ۵ ثانیه
                failures += 1
                if failures == 1:
                    log.warning("Lost connection to Telegram for bot %s: %s", bot.id, type(e).__name__)
                elif failures % 10 == 0:
                    log.warning("Still no connection to Telegram for bot %s (%s attempts)", bot.id, failures)
                if failures % RESET_AFTER == 0:
                    # بعد از قطع و وصل اینترنت ممکن است اتصال‌های قدیمی خراب بمانند (دیده شد: ۷ دقیقه بی‌پاسخ
                    # تا ری‌استارت). اتصال تازه: aiogram خودش در درخواست بعدی یک session نو می‌سازد
                    await reset_session(bot)
                await asyncio.sleep(retry_delay(failures))
                continue
            if failures:
                log.info("Connection to Telegram restored for bot %s after %s failed attempts", bot.id, failures)
                failures = 0
            for update in updates:
                offset = update.update_id + 1
                task = asyncio.create_task(self._handle(bot, update))
                self._handling.add(task)
                task.add_done_callback(self._handling.discard)

    async def _handle(self, bot: Bot, update) -> None:
        try:
            await self.dp.feed_update(bot, update)
        except Exception:
            log.exception("Update %s failed", update.update_id)

    async def _on_revoked(self, bot: Bot) -> None:
        log.warning("Seller bot %s token revoked; disconnecting", bot.id)
        self._polls.pop(bot.id, None)
        await bot.session.close()
        if bot.id == self.main_bot.id:
            raise SystemExit("Main BOT_TOKEN is invalid  |  توکن ربات اصلی نامعتبر است.")
        async with SessionLocal() as session:
            seller = await session.scalar(select(Seller).where(Seller.bot_id == bot.id))
            if seller is None:
                return
            seller.is_active = False
            await session.commit()
            owner = await session.get(User, seller.owner_id)
            lang = owner.language if owner else "fa"
        try:
            await self.main_bot.send_message(seller.owner_id, T(lang)["seller_revoked"].format(bot=seller.bot_username))
        except Exception:
            pass


async def setup_seller_bot(bot: Bot) -> None:
    """منوی دستورهای ربات فروشنده. وب‌هوک قبلی (اگر ربات جای دیگری اجرا می‌شد) برداشته می‌شود."""
    await bot.delete_webhook(drop_pending_updates=False)
    await setup_commands(bot, seller=True)


def command_list(lang: str, seller: bool) -> list[BotCommand]:
    names = COMMANDS.get(lang, COMMANDS["en"])
    return [BotCommand(command=c, description=names[c]) for c in (SELLER_COMMANDS if seller else MAIN_COMMANDS)]


def menu_lang(tg_code: str | None) -> str:
    """زبانی که تلگرام خودش برای این کاربر از منوهای پیش‌فرض نشان می‌دهد."""
    return MENU_LANG_CODES.get((tg_code or "")[:2].lower(), "fa")


async def setup_commands(bot: Bot, seller: bool) -> None:
    """منوی پیش‌فرض فارسی + منوی روسی/عربی/چینی بر اساس زبان تلگرام کاربر."""
    await bot.set_my_commands(command_list("fa", seller))
    for code, lang in MENU_LANG_CODES.items():
        await bot.set_my_commands(command_list(lang, seller), language_code=code)
    for code in ("fa", "en"):  # منوهای قدیمی دوزبانه
        await bot.delete_my_commands(language_code=code)


async def set_user_menu(bot: Bot, user_id: int, lang: str, tg_code: str | None, seller: bool,
                        force: bool = False) -> None:
    """اگر زبان انتخابی کاربر با منوی پیش‌فرض تلگرامش فرق دارد، منوی مخصوص خودش را می‌گذارد.
    force: بعد از عوض کردن زبان؛ منوی شخصی قبلی را هم پاک می‌کند اگر دیگر لازم نیست."""
    scope = BotCommandScopeChat(chat_id=user_id)
    try:
        if lang != menu_lang(tg_code):
            await bot.set_my_commands(command_list(lang, seller), scope=scope)
        elif force:
            await bot.delete_my_commands(scope=scope)
    except Exception:  # منو فقط ظاهری است؛ نباید جلوی کار اصلی را بگیرد
        log.warning("Could not set the command menu for a user", exc_info=True)
