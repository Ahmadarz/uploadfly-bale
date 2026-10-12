"""تست خودکار جریان‌های ربات با یک «تلگرام ساختگی».

هیچ پیامی واقعاً به تلگرام فرستاده نمی‌شود: MockSession هر درخواست ربات را ثبت می‌کند و جواب ساختگی برمی‌گرداند.
دیتابیس هم یک فایل SQLite موقت است، پس دیتابیس واقعی دست نمی‌خورد.
اجرا: .venv/bin/python -m pytest -q
"""
import itertools
import os
import re
import tempfile

from cryptography.fernet import Fernet

# قبل از import کردن app: تنظیمات آزمایشی (load_dotenv مقدارهای موجود را عوض نمی‌کند)
_tmp = tempfile.mkdtemp(prefix="uploadfly-test-")
# پیش‌فرض SQLite موقت؛ برای تست روی PostgreSQL: TEST_DATABASE_URL=postgresql+asyncpg://...
os.environ["DATABASE_URL"] = os.getenv("TEST_DATABASE_URL") or f"sqlite+aiosqlite:///{_tmp}/test.db"
os.environ["BOT_TOKEN"] = "1000001:" + "A" * 35
os.environ["ENCRYPTION_KEY"] = Fernet.generate_key().decode()
os.environ["WEBAPP_URL"] = "https://app.example"
os.environ["PRICE_UNIT"] = "1"  # قیمت‌های تست کوچک می‌مانند (در اجرای واقعی واحد ۱۰۰۰ تومان است)
os.environ["REFUNDS"] = "1"  # مسیر بازپرداخت در تست‌ها روشن است؛ حالت خاموش تست جدا دارد
os.environ["ADMIN_IDS"] = "501"  # OWNER در تست‌ها مدیر است

import pytest  # noqa: E402
from aiogram import Bot  # noqa: E402
from aiogram.client.default import DefaultBotProperties  # noqa: E402
from aiogram.client.session.base import BaseSession  # noqa: E402
from aiogram.exceptions import TelegramBadRequest  # noqa: E402
from aiogram.enums import ParseMode  # noqa: E402
from aiogram.types import File, Message, StarAmount, Update, User as TgUser  # noqa: E402

from app import preview  # noqa: E402
from app.crypto import encrypt  # noqa: E402
from app.db import Base, SessionLocal, Seller, User, engine, init_db  # noqa: E402

MAIN_ID, SHOP_ID = 1000001, 2000002
OWNER, BUYER, STRANGER = 501, 502, 503
_ids = itertools.count(1000)


_TAG = re.compile(r"<(/?)([^\s>/]*)[^>]*>")
_ALLOWED_TAGS = {"b", "strong", "i", "em", "u", "ins", "s", "strike", "del", "a", "code", "pre",
                 "blockquote", "tg-spoiler", "span", "tg-emoji", "br"}


def check_html(text: str, method) -> None:
    """همان قاعده‌ی تلگرام: هر «<» باید شروع یک تگ مجاز باشد."""
    for m in re.finditer(r"<", text):
        tag = _TAG.match(text, m.start())
        if tag is None or tag.group(2).lower() not in _ALLOWED_TAGS:
            raise TelegramBadRequest(method=method, message=f"can't parse entities: unsupported tag at {m.start()}")


class MockSession(BaseSession):
    """به‌جای تلگرام: درخواست‌ها را ثبت می‌کند و جواب ساختگی معتبر برمی‌گرداند."""
    star_balance = 10  # موجودی استارز هر ربات ساختگی؛ تست‌ها می‌توانند عوضش کنند

    def __init__(self, calls: list):
        super().__init__()
        self.calls = calls

    async def close(self):
        pass

    async def stream_content(self, *args, **kwargs):
        yield _JPEG  # هر دانلودی یک عکس کوچک برمی‌گرداند

    async def make_request(self, bot, method, timeout=None):
        name = type(method).__name__
        params = method.model_dump(exclude_none=True)
        # مثل تلگرام واقعی: متن HTML نامعتبر رد می‌شود (مثلاً «<لینک>» که تگ نیست).
        # parse_mode پیش‌فرض ربات HTML است؛ فقط وقتی صریحاً چیز دیگری باشد بررسی نمی‌شود
        pm = params.get("parse_mode")
        if not isinstance(pm, str) or pm.upper() == "HTML":
            for field in ("text", "caption"):
                if isinstance(params.get(field), str):
                    check_html(params[field], method)
        self.calls.append((bot.id, name, params))  # فقط درخواست‌های موفق ثبت می‌شوند
        chat_id = params.get("chat_id", 1)
        base = {"message_id": next(_ids), "date": 0, "chat": {"id": chat_id, "type": "private"}}
        if name == "GetMe":
            return TgUser(id=bot.id, is_bot=True, first_name="Bot",
                          username="Uploadfly_Bot" if bot.id == MAIN_ID else f"bot{bot.id}")
        if name == "SendPhoto":
            return Message.model_validate(context={"bot": bot}, obj={**base, "photo": [{"file_id": f"ph{next(_ids)}", "file_unique_id": "u",
                                                              "width": 10, "height": 10}]})
        if name == "SendVoice":
            return Message.model_validate(context={"bot": bot}, obj={**base, "voice": {"file_id": f"vo{next(_ids)}", "file_unique_id": "u",
                                                             "duration": 15}})
        if name == "SendMediaGroup":
            return [Message.model_validate(context={"bot": bot}, obj={**base, "message_id": next(_ids), "photo": [
                {"file_id": f"ph{next(_ids)}", "file_unique_id": "u", "width": 10, "height": 10}]})
                for _ in params["media"]]
        if name.startswith(("Send", "Edit")) or name == "CopyMessage":
            return Message.model_validate(base, context={"bot": bot})
        if name == "GetFile":
            return File(file_id=params["file_id"], file_unique_id="u", file_path=f"files/{params['file_id']}.jpg")
        if name == "CreateInvoiceLink":
            return "https://ble.ir/$test_invoice"
        if name == "GetMyStarBalance":
            return StarAmount(amount=self.star_balance)
        if name == "GetManagedBotToken":
            return f"{params['user_id']}:" + "B" * 35
        return True  # delete/answer/set*/refund/...


class Telegram:
    """ربات‌های ساختگی + فهرست درخواست‌ها برای assert."""

    def __init__(self):
        self.calls: list = []
        self.bots: dict[int, Bot] = {}

    def bot(self, bot_id: int) -> Bot:
        if bot_id not in self.bots:
            self.bots[bot_id] = Bot(f"{bot_id}:" + "A" * 35, session=MockSession(self.calls),
                                    default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        return self.bots[bot_id]

    def sent(self, bot_id: int | None = None, method: str | None = None) -> list[dict]:
        return [p for b, m, p in self.calls if (bot_id is None or b == bot_id) and (method is None or m == method)]

    def texts(self, bot_id: int | None = None) -> str:
        return "\n".join(str(p.get("text", "")) + str(p.get("caption", "")) for p in self.sent(bot_id))

    def buttons(self, bot_id: int | None = None) -> list[dict]:
        out = []
        for p in self.sent(bot_id):
            for row in (p.get("reply_markup") or {}).get("inline_keyboard", []):
                out.extend(row)
        return out

    def clear(self):
        self.calls.clear()


class FakeManager:
    def __init__(self, tg: Telegram):
        self.tg = tg
        self.started: list[int] = []
        self.main_bot = tg.bot(MAIN_ID)

    def get(self, bot_id):
        return self.tg.bot(bot_id) if bot_id in (MAIN_ID, SHOP_ID) or bot_id in self.started else None

    def is_running(self, bot_id):
        return True

    async def start(self, bot):
        self.started.append(bot.id)

    async def stop(self, bot_id):
        pass


@pytest.fixture(scope="session")
def dispatcher():
    from app.main import build_dispatcher
    return build_dispatcher()


@pytest.fixture
async def env(dispatcher, monkeypatch, tmp_path):
    """دیتابیس خالی + یک فروشگاه آماده (OWNER صاحب SHOP_ID است) + تلگرام ساختگی."""
    import app.web
    # کش تصویرهای کوچک هر تست جداست (کش مشترک با برنامه‌ی واقعی یک باگ را پنهان کرده بود)
    monkeypatch.setattr(app.web, "THUMB_DIR", tmp_path / "thumbs")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await init_db()
    tg = Telegram()
    manager = FakeManager(tg)
    dispatcher["manager"] = manager
    dispatcher["main_bot_id"] = MAIN_ID
    dispatcher["main_username"] = "Uploadfly_Bot"
    dispatcher["webapp_url"] = "https://app.example"
    dispatcher.fsm.storage.storage.clear()   # حالت نیمه‌کاره‌ی گفت‌وگو (مثلاً «منتظر توکن») از تست قبلی نماند
    # اتصال فروشگاه با توکن: به‌جای بازوی واقعی بله، همان بازوی ساختگی
    import app.connect
    monkeypatch.setattr(app.connect, "make_bot", lambda token: tg.bot(int(token.split(":")[0])))

    async def fake_build(bot, c, workdir):  # ساخت پیش‌نمایش بدون ffmpeg و دانلود
        return {"text": preview.text_snippet(c)} if c.kind == "text" else {"photos": [_JPEG]}
    monkeypatch.setattr(preview, "build", fake_build)

    async with SessionLocal() as s:
        for uid, name in ((OWNER, "Owner"), (BUYER, "Buyer"), (STRANGER, "Stranger")):
            s.add(User(id=uid, first_name=name, username=name.lower(), language="fa"))
        await s.flush()  # اول کاربرها (PostgreSQL کلید خارجی را بررسی می‌کند، SQLite نه)
        s.add(Seller(owner_id=OWNER, bot_id=SHOP_ID, bot_username=f"bot{SHOP_ID}",
                     token_enc=encrypt(f"{SHOP_ID}:" + "A" * 35), wallet_enc=encrypt("WALLET-TEST-1111111111111111"), watermark=False))
        await s.commit()

    class Env:
        pass
    e = Env()
    e.tg, e.manager, e.dp = tg, manager, dispatcher
    e.main, e.shop = tg.bot(MAIN_ID), tg.bot(SHOP_ID)

    async def feed(bot, payload: dict):
        await dispatcher.feed_update(bot, Update.model_validate({"update_id": next(_ids), **payload},
                                                                context={"bot": bot}))
    e.feed = feed
    return e


def _jpeg() -> bytes:
    import io
    from PIL import Image
    out = io.BytesIO()
    Image.new("RGB", (40, 30), "white").save(out, "JPEG")
    return out.getvalue()


_JPEG = _jpeg()


def user(uid: int) -> dict:
    return {"id": uid, "is_bot": False, "first_name": f"U{uid}", "language_code": "fa"}


def message(uid: int, text: str | None = None, **extra) -> dict:
    m = {"message_id": next(_ids), "date": 0, "chat": {"id": uid, "type": "private"}, "from": user(uid), **extra}
    if text is not None:
        m["text"] = text
        if text.startswith("/"):
            m["entities"] = [{"type": "bot_command", "offset": 0, "length": len(text.split()[0])}]
    return {"message": m}


def photo_message(uid: int) -> dict:
    return message(uid, photo=[{"file_id": f"photo{next(_ids)}", "file_unique_id": f"u{next(_ids)}",
                                "width": 800, "height": 600, "file_size": 50000}])


def callback(uid: int, data: str, message_id: int = 1) -> dict:
    return {"callback_query": {"id": str(next(_ids)), "from": user(uid), "chat_instance": "x", "data": data,
                               "message": {"message_id": message_id, "date": 0,
                                           "chat": {"id": uid, "type": "private"}, "text": "x"}}}
