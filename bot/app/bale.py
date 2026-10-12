"""اتصال به پیام‌رسان بله (Bot API بله شبیه تلگرام است، با چند تفاوت).

- آدرس API: tapi.bale.ai (همان aiogram، فقط سرور دیگر).
- بله HTML نمی‌فهمد و هر متنی را Markdown ساده می‌خواند (*پررنگ*، _کج_، [متن](لینک)). متن‌های برنامه HTML
  نوشته شده‌اند؛ همین‌جا، درست قبل از فرستادن، تبدیل می‌شوند تا بقیه‌ی کد دست نخورد.
- چند متد در بله نیست (توضیح بازو، دکمه‌ی منو)؛ بی‌صدا رد می‌شوند تا برنامه به‌خاطرشان نایستد.
"""
import html
import re

from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.session.middlewares.base import BaseRequestMiddleware
from aiogram.client.telegram import TelegramAPIServer

API = TelegramAPIServer.from_base("https://tapi.bale.ai")
LINK_HOST = "ble.ir"

# بررسی‌شده روی بازوی واقعی (2026-10-12): این متدها «Not Implemented» یا «handler not found» برمی‌گردانند
UNSUPPORTED = {"SetMyDescription", "SetMyShortDescription", "SetMyName", "SetChatMenuButton"}

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


def make_bale_bot(token: str) -> Bot:
    session = AiohttpSession(api=API)
    session.middleware(BaleMiddleware())
    return Bot(token=token, session=session)
