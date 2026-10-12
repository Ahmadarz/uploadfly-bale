import os
import re
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    bot_token: str
    database_url: str
    encryption_key: str
    webapp_url: str | None  # آدرس ثابت HTTPS روی سرور؛ خالی = تونل موقت روی مک
    webapp_port: int
    webapp_host: str  # روی مک 127.0.0.1؛ داخل Docker 0.0.0.0 تا Caddy به آن برسد
    admin_ids: frozenset[int]  # مدیران UploadFly (دستورهای اضطراری)؛ در .env با ADMIN_IDS
    support_username: str | None  # حساب تلگرام پشتیبانی (بدون @)؛ خالی = دکمه‌ی چت پنهان
    support_email: str | None     # ایمیل پشتیبانی؛ خالی = پنهان


def load_settings() -> Settings:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token or token == "PUT_YOUR_TOKEN_HERE":
        raise SystemExit("BOT_TOKEN is not set in .env  |  توکن ربات در فایل .env وارد نشده است.")
    key = os.getenv("ENCRYPTION_KEY", "").strip()
    if not key or key == "PUT_GENERATED_KEY_HERE":
        raise SystemExit("ENCRYPTION_KEY is not set in .env  |  کلید رمزنگاری در فایل .env وارد نشده است.")
    return Settings(
        bot_token=token,
        database_url=os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./uploadfly.db"),
        encryption_key=key,
        webapp_url=os.getenv("WEBAPP_URL", "").strip().rstrip("/") or None,
        webapp_port=int(os.getenv("WEBAPP_PORT", "8080")),
        webapp_host=os.getenv("WEBAPP_HOST", "127.0.0.1"),
        admin_ids=frozenset(int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x.isdigit()),
        support_username=clean_username(os.getenv("SUPPORT_USERNAME", "")),
        support_email=clean_email(os.getenv("SUPPORT_EMAIL", "")),
    )


def clean_username(value: str) -> str | None:
    value = value.strip().lstrip("@")
    return value if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{3,31}", value) else None


def clean_email(value: str) -> str | None:
    value = value.strip()
    return value if re.fullmatch(r"[^@\s<>\"']+@[^@\s<>\"']+\.[A-Za-z]{2,}", value) else None


settings = load_settings()
