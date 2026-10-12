"""رمزنگاری توکن ربات فروشنده‌ها قبل از ذخیره در دیتابیس."""
from cryptography.fernet import Fernet

from app.config import settings

_fernet = Fernet(settings.encryption_key.encode())


def encrypt(value: str) -> str:
    return _fernet.encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    return _fernet.decrypt(value.encode()).decode()
