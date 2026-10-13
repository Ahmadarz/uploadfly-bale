"""اتصال به پیام‌رسان بله (Bot API بله شبیه تلگرام است، با چند تفاوت).

- آدرس API: tapi.bale.ai (همان aiogram، فقط سرور دیگر).
- بله HTML نمی‌فهمد و هر متنی را Markdown ساده می‌خواند (*پررنگ*، _کج_، [متن](لینک)). متن‌های برنامه HTML
  نوشته شده‌اند؛ همین‌جا، درست قبل از فرستادن، تبدیل می‌شوند تا بقیه‌ی کد دست نخورد.
- چند متد در بله نیست (توضیح بازو، دکمه‌ی منو)؛ بی‌صدا رد می‌شوند تا برنامه به‌خاطرشان نایستد.
- پول: داخل برنامه همه‌ی مبلغ‌ها «تومان» است (ستون‌های price_stars/amount و برچسب داخلی "XTR" از نسخه‌ی تلگرام
  مانده‌اند و فقط نام‌اند). بله ریال می‌خواهد و هر فاکتور باید توکن کیف پول صاحب همان بازو را داشته باشد؛ هر دو
  همین‌جا، در مرز برنامه و بله، تبدیل می‌شوند: فاکتور خروجی (تومان ← ریال + توکن کیف پول) و پرداخت ورودی (ریال ← تومان).
"""
import html
import re

from aiogram import Bot
from aiohttp import FormData
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.session.middlewares.base import BaseRequestMiddleware
from aiogram.client.telegram import TelegramAPIServer
from aiogram.exceptions import TelegramAPIError
from aiogram.types import Update

API = TelegramAPIServer.from_base("https://tapi.bale.ai")
LINK_HOST = "ble.ir"

# بررسی‌شده روی بازوی واقعی (2026-10-12): این متدها «Not Implemented» یا «handler not found» برمی‌گردانند
UNSUPPORTED = {"SetMyDescription", "SetMyShortDescription", "SetMyName", "SetChatMenuButton"}

INTERNAL_CURRENCY = "XTR"   # برچسب داخلی برنامه برای «تومان» (نام قدیمی؛ به بله فرستاده نمی‌شود)
BALE_CURRENCY = "IRR"
RIALS_PER_TOMAN = 10
INVOICE_METHODS = ("SendInvoice", "CreateInvoiceLink")
TEST_WALLET = "WALLET-TEST-1111111111111111"  # توکن آزمایشی بله: مثل واقعی رفتار می‌کند ولی پولی جابه‌جا نمی‌شود

# توکن کیف پول هر بازو (شناسه‌ی بازو ← توکن)؛ هنگام روشن شدن بازو و تغییر کیف پول پر می‌شود
_wallets: dict[int, str] = {}


class NoWallet(Exception):
    """بازویی که هنوز توکن کیف پول ندارد نمی‌تواند فاکتور بسازد."""


def is_test_wallet(token: str | None) -> bool:
    return bool(token) and token.strip().upper().startswith("WALLET-TEST")


def set_wallet(bot_id: int, token: str | None) -> None:
    """توکن کیف پول یک بازو را در حافظه می‌گذارد. توکن آزمایشی بله فقط وقتی ALLOW_TEST_WALLET روشن است پذیرفته
    می‌شود؛ وگرنه آن بازو «بدون کیف پول» حساب می‌شود (فاکتور نمی‌سازد و صاحبش خبردار می‌شود)."""
    from app.config import settings
    if token and (settings.allow_test_wallet or not is_test_wallet(token)):
        _wallets[bot_id] = token
    else:
        _wallets.pop(bot_id, None)


def invoice_failed(exc: BaseException) -> bool:
    """خطایی که یعنی «فاکتور ساخته نشد»: کیف پول ثبت نشده، یا بله فاکتور را نپذیرفته (مثلاً توکن کیف پول باطل شده)."""
    return isinstance(exc, NoWallet) or (
        isinstance(exc, TelegramAPIError) and type(getattr(exc, "method", None)).__name__ in INVOICE_METHODS)


def to_toman(update: Update) -> Update:
    """پرداخت ورودی بله (ریال) ← واحد داخلی برنامه (تومان)."""
    q = update.pre_checkout_query
    if q is not None and q.currency == BALE_CURRENCY:
        return update.model_copy(update={"pre_checkout_query": q.model_copy(update={
            "currency": INTERNAL_CURRENCY, "total_amount": q.total_amount // RIALS_PER_TOMAN})})
    m = update.message
    p = m.successful_payment if m is not None else None
    if p is not None and p.currency == BALE_CURRENCY:
        paid = p.model_copy(update={"currency": INTERNAL_CURRENCY, "total_amount": p.total_amount // RIALS_PER_TOMAN})
        return update.model_copy(update={"message": m.model_copy(update={"successful_payment": paid})})
    return update


_LINK = re.compile(r'<a\s+href="([^"]*)"\s*>(.*?)</a>', re.IGNORECASE | re.DOTALL)
_BOLD = re.compile(r"</?(?:b|strong)>", re.IGNORECASE)
_ITALIC = re.compile(r"</?(?:i|em)>", re.IGNORECASE)
_BREAK = re.compile(r"<br\s*/?>", re.IGNORECASE)
_TAG = re.compile(r"</?(?:u|ins|s|strike|del|code|pre|blockquote|tg-spoiler|span|tg-emoji)(?:\s[^>]*)?>", re.IGNORECASE)


def bot_link(username: str, start: str | None = None) -> str:
    return f"https://{LINK_HOST}/{username}" + (f"?start={start}" if start else "")


def to_bale(text: str) -> str:
    """HTML تلگرام ← Markdown بله. تگ‌هایی که بله معادل ندارد (کد، زیرخط، نقل‌قول) فقط برداشته می‌شوند."""
    text = _LINK.sub(lambda m: f"[{m.group(2)}]({html.unescape(m.group(1))})", text)
    text = _BOLD.sub("*", text)
    text = _ITALIC.sub("_", text)
    text = _BREAK.sub("\n", text)
    text = _TAG.sub("", text)
    return html.unescape(text)


class BaleMiddleware(BaseRequestMiddleware):
    async def __call__(self, make_request, bot, method):
        name = type(method).__name__
        if name in UNSUPPORTED:
            return True
        update = {}
        if name in INVOICE_METHODS:
            token = _wallets.get(bot.id)
            if not token:
                raise NoWallet(f"bot {bot.id} has no wallet token")
            update.update(provider_token=token, currency=BALE_CURRENCY, prices=[
                p.model_copy(update={"amount": p.amount * RIALS_PER_TOMAN}) for p in method.prices])
            if getattr(method, "subscription_period", None):
                update["subscription_period"] = None  # بله اشتراک با تمدید خودکار ندارد
        for field in ("text", "caption"):
            value = getattr(method, field, None)
            if isinstance(value, str) and name != "AnswerCallbackQuery":
                update[field] = to_bale(value)
        if hasattr(method, "parse_mode"):
            update["parse_mode"] = None
        media = getattr(method, "media", None)
        if isinstance(media, list):  # آلبوم: کپشن هر عکس
            update["media"] = [m.model_copy(update={"caption": to_bale(m.caption), "parse_mode": None})
                               if isinstance(getattr(m, "caption", None), str) else m for m in media]
        if update:
            method = method.model_copy(update=update)
        return await make_request(bot, method)


class BaleSession(AiohttpSession):
    """آپلود فایل به روش بله. aiogram فایل را در یک بخش جدا می‌گذارد و در خود فیلد می‌نویسد «attach://نام»؛
    بله این را نمی‌فهمد (آن را آدرس اینترنتی حساب می‌کند: «failed to get HTTP URL content»، دیده‌شده 2026-10-12)
    و فایل را مستقیم در همان فیلد (photo، document، voice ...) می‌خواهد."""

    def build_form_data(self, bot, method):
        form = FormData(quote_fields=False)
        files: dict = {}
        for key, value in method.model_dump(warnings=False).items():
            value = self.prepare_value(value, bot=bot, files=files)
            if not value:
                continue
            name = value[len("attach://"):] if isinstance(value, str) and value.startswith("attach://") else None
            if name in files:   # فایلِ خود همین فیلد: مستقیم در همین فیلد
                file = files.pop(name)
                form.add_field(key, file.read(bot), filename=file.filename or key)
            else:
                form.add_field(key, value)
        for key, value in files.items():   # فایل‌های داخل آلبوم (media) به همان شکل استاندارد می‌مانند
            form.add_field(key, value.read(bot), filename=value.filename or key)
        return form


def make_bale_bot(token: str) -> Bot:
    session = BaleSession(api=API)
    session.middleware(BaleMiddleware())
    return Bot(token=token, session=session)
